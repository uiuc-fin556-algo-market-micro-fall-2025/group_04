/*================================================================================                               
*     Source: ../RCM/StrategyStudio/examples/strategies/SimpleMomentumStrategy/SimpleMomentumStrategy.h                                                        
*     Last Update: 2013/06/1 13:55:14                                                                            
*     Contents:                                     
*     Distribution:          
*                                                                                                                
*                                                                                                                
*     Copyright (c) RCM-X, 2011 - 2013.                                                  
*     All rights reserved.                                                                                       
*                                                                                                                
*     This software is part of Licensed material, which is the property of RCM-X ("Company"), 
*     and constitutes Confidential Information of the Company.                                                  
*     Unauthorized use, modification, duplication or distribution is strictly prohibited by Federal law.         
*     No title to or ownership of this software is hereby transferred.                                          
*                                                                                                                
*     The software is provided "as is", and in no event shall the Company or any of its affiliates or successors be liable for any 
*     damages, including any lost profits or other incidental or consequential damages relating to the use of this software.       
*     The Company makes no representations or warranties, express or implied, with regards to this software.                        
/*================================================================================*/ 

#pragma once

#ifndef _STRATEGY_STUDIO_LIB_EXAMPLES_OFI_STRATEGY_H_
#define _STRATEGY_STUDIO_LIB_EXAMPLES_OFI_STRATEGY_H_

#ifdef _WIN32
    #define _STRATEGY_EXPORTS __declspec(dllexport)
#else
    #ifndef _STRATEGY_EXPORTS
        #define _STRATEGY_EXPORTS
    #endif
#endif

#include <Strategy.h>
#include <MarketModels/Instrument.h>
#include <Utilities/ParseConfig.h>

#include <deque>
#include <unordered_map>
#include <string>
#include <cstring>

using namespace RCM::StrategyStudio;

/**
 * Order Flow Imbalance (OFI) strategy (Cont, Kukanov, Stoikov, 2011).
 *
 * We compute OFI from successive TopQuote updates (best bid/ask price + size):
 *
 *   e_n =  1{Pb_n >= Pb_{n-1}} qB_n - 1{Pb_n <= Pb_{n-1}} qB_{n-1}
 *        -1{Pa_n <= Pa_{n-1}} qA_n + 1{Pa_n >= Pa_{n-1}} qA_{n-1}
 *
 * Then aggregate over a rolling time window:
 *   OFI(t) = sum_{events in window} e_n
 *
 * We form a normalized signal using current market depth:
 *   signal = impact_multiplier * OFI / (2 * depth),
 *   depth = (qB + qA) / 2
 *
 * Trading rule:
 *   - If signal >  entry_threshold -> increase long exposure
 *   - If signal < -entry_threshold -> increase short exposure
 *   - If holding long and signal <= 0, or holding short and signal >= 0 -> flatten
 *
 */

struct OFIEventRecord {
    Utilities::TimeType timestamp;
    double ofi_increment;

    OFIEventRecord(Utilities::TimeType t, double inc)
        : timestamp(t), ofi_increment(inc) {}
};

struct OFIInstrumentState {
    bool initialized = false;

    double prev_bid = 0.0;
    double prev_ask = 0.0;
    int prev_bid_size = 0;
    int prev_ask_size = 0;

    std::deque<OFIEventRecord> window;
    double cumulative_ofi = 0.0;

    void Reset()
    {
        initialized = false;
        prev_bid = prev_ask = 0.0;
        prev_bid_size = prev_ask_size = 0;
        window.clear();
        cumulative_ofi = 0.0;
    }
};

class OFIStrategy : public Strategy {
public:
    OFIStrategy(StrategyID strategyID, const std::string& strategyName, const std::string& groupName);
    ~OFIStrategy();

public: /* from IEventCallback */
    virtual void OnTrade(const TradeDataEventMsg& msg) {}
    virtual void OnTopQuote(const QuoteEventMsg& msg);
    virtual void OnQuote(const QuoteEventMsg& msg) {}
    virtual void OnDepth(const MarketDepthEventMsg& msg) {}
    virtual void OnBar(const BarEventMsg& msg) {}
    virtual void OnMarketState(const MarketStateEventMsg& msg) {}
    virtual void OnOrderUpdate(const OrderUpdateEventMsg& msg);
    virtual void OnStrategyControl(const StrategyStateControlEventMsg& msg) {}
    virtual void OnDataSubscription(const DataSubscriptionEventMsg& msg) {}
    virtual void OnStrategyCommand(const StrategyCommandEventMsg& msg);
    virtual void OnParamChanged(StrategyParam& param);

    virtual void OnResetStrategyState();

private:
    virtual void RegisterForStrategyEvents(StrategyEventRegister* eventRegister, DateType currDate);
    virtual void DefineStrategyParams();
    virtual void DefineStrategyCommands();

private:
    // Trading Helper Methods
    void AdjustPortfolio(const MarketModels::Instrument* instrument, int desired_position);
    void SendOrder(const MarketModels::Instrument* instrument, int trade_size);

    // OFI Computation Helpers
    bool IsQuoteValid(const MarketModels::Quote& top_quote) const;
    double ComputeOFIIncrement(const OFIInstrumentState& state,
                              double bid, int bid_size,
                              double ask, int ask_size) const;

    void AddEventToWindow(OFIInstrumentState& state, double ofi_increment, Utilities::TimeType timestamp);
    void PruneOldEvents(OFIInstrumentState& state, Utilities::TimeType cutoff_time);
    bool IsOFIReady(const OFIInstrumentState& state) const;

    double CalculateMidPrice(const MarketModels::Quote& top_quote) const;
    double CalculateSpreadBps(const MarketModels::Quote& top_quote) const;
    double CalculateDepth(const MarketModels::Quote& top_quote) const;
    double CalculateSignal(const OFIInstrumentState& state, double depth) const;

private:
    // Per-instrument OFI state
    std::unordered_map<const MarketModels::Instrument*, OFIInstrumentState> ofi_state_;

    // Strategy parameters 
    int ofi_window_seconds_;          // Rolling window length for OFI aggregation
    int min_events_required_;         // Require at least this many OFI events before trading
    double entry_threshold_;          // Threshold on normalized signal to enter
    double impact_multiplier_;        // Scales normalized OFI -> signal
    double max_spread_bps_;           // Skip trading if spread too wide
    int max_inventory_;               // Maximum absolute position
    int position_size_;               // Units to add/subtract per signal
    bool debug_;
};

extern "C" {
    _STRATEGY_EXPORTS const char* GetType() {
        return "OFIStrategy";
    }

    _STRATEGY_EXPORTS IStrategy* CreateStrategy(const char* strategyType,
                                                unsigned strategyID,
                                                const char* strategyName,
                                                const char* groupName)
    {
        if (strcmp(strategyType, GetType()) == 0) {
            return *(new OFIStrategy(strategyID, strategyName, groupName));
        } else {
            return nullptr;
        }
    }

    _STRATEGY_EXPORTS const char* GetAuthor() {
        return "dlariviere";
    }

    _STRATEGY_EXPORTS const char* GetAuthorGroup() {
        return "UIUC";
    }

    _STRATEGY_EXPORTS const char* GetReleaseVersion() {
        return Strategy::release_version();
    }
}

#endif
