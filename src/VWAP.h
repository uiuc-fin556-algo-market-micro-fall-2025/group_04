#pragma once

#ifndef _STRATEGY_STUDIO_LIB_EXAMPLES_VWAP_STRATEGY_H_
#define _STRATEGY_STUDIO_LIB_EXAMPLES_VWAP_STRATEGY_H_

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
#include <map>
#include <iostream>
#include <deque>

using namespace RCM::StrategyStudio;

// Structure to hold trade data for VWAP calculation
struct VWAPTradeRecord {
    Utilities::TimeType timestamp;
    double price;
    int volume;
    
    VWAPTradeRecord(Utilities::TimeType t, double p, int v) 
        : timestamp(t), price(p), volume(v) {}
};

class VWAPStrategy : public Strategy {
public:
    VWAPStrategy(StrategyID strategyID, const std::string& strategyName, const std::string& groupName);
    ~VWAPStrategy();

public: /* from IEventCallback */
    virtual void OnTrade(const TradeDataEventMsg& msg);
    virtual void OnTopQuote(const QuoteEventMsg& msg) {}
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
    // Helper methods for trading logic
    void AdjustPortfolio(const Instrument* instrument, int desired_position);
    void SendOrder(const Instrument* instrument, int trade_size);
    
    // VWAP calculation helpers
    void AddTradeToWindow(double price, int volume, Utilities::TimeType timestamp);
    void PruneOldTrades(Utilities::TimeType cutoff_time);
    double GetVWAP() const;
    bool IsVWAPReady() const;
    double CalculateMidPrice(const Instrument* instrument) const;
    double CalculateDeviation(double mid_price, double vwap) const;

private:
    // VWAP calculation
    std::deque<VWAPTradeRecord> vwap_window_;
    double cumulative_pv_;           // Sum of (price * volume)
    int cumulative_volume_;          // Sum of volume
    int vwap_window_seconds_;        // Rolling window size (default 300 = 5 min)
    
    // Strategy parameters
    double entry_threshold_bps_;     // Deviation threshold to enter (default 2.0)
    int max_inventory_;              // Maximum position size (default 5)
    int position_size_;              // Shares per order (default 1)
    bool debug_;                     // Enable debug logging
};

extern "C" {
    _STRATEGY_EXPORTS const char* GetType() {
        return "VWAPStrategy";
    }

    _STRATEGY_EXPORTS IStrategy* CreateStrategy(const char* strategyType, 
                                                unsigned strategyID, 
                                                const char* strategyName,
                                                const char* groupName)
    {
        if (strcmp(strategyType, GetType()) == 0) {
            return *(new VWAPStrategy(strategyID, strategyName, groupName));
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


