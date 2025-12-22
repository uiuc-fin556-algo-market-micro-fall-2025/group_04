#pragma once

#ifndef _STRATEGY_STUDIO_LIB_EXAMPLES_VWAP_OFI_STRATEGY_H_
#define _STRATEGY_STUDIO_LIB_EXAMPLES_VWAP_OFI_STRATEGY_H_

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

#include <boost/date_time/posix_time/posix_time.hpp>

#include <deque>
#include <unordered_map>
#include <string>
#include <cstring>

using namespace RCM::StrategyStudio;

// -------------------- VWAP (rolling, trade-based) --------------------
struct VWAPTradeRecord2 {
    Utilities::TimeType timestamp;
    double price;
    int volume;

    VWAPTradeRecord2(Utilities::TimeType t, double p, int v)
        : timestamp(t), price(p), volume(v) {}
};

struct VWAPState2 {
    std::deque<VWAPTradeRecord2> window;
    double cumulative_pv = 0.0;
    long long cumulative_volume = 0;

    void Reset() {
        window.clear();
        cumulative_pv = 0.0;
        cumulative_volume = 0;
    }
};

// -------------------- OFI (top-of-book, Cont-Kukanov-Stoikov style) --------------------
struct OFIEventRecord2 {
    Utilities::TimeType timestamp;
    double ofi_increment;

    OFIEventRecord2(Utilities::TimeType t, double inc)
        : timestamp(t), ofi_increment(inc) {}
};

struct OFIState2 {
    bool initialized = false;

    double prev_bid = 0.0;
    double prev_ask = 0.0;
    int prev_bid_size = 0;
    int prev_ask_size = 0;

    std::deque<OFIEventRecord2> window;
    double cumulative_ofi = 0.0;

    void Reset() {
        initialized = false;
        prev_bid = prev_ask = 0.0;
        prev_bid_size = prev_ask_size = 0;
        window.clear();
        cumulative_ofi = 0.0;
    }
};

// -------------------- Combined Strategy --------------------
class VWAPOFIStrategy : public Strategy {
public:
    VWAPOFIStrategy(StrategyID strategyID, const std::string& strategyName, const std::string& groupName);
    ~VWAPOFIStrategy();

public: /* from IEventCallback */
    virtual void OnTrade(const TradeDataEventMsg& msg);
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
    // --- VWAP helpers ---
    void AddTradeToWindow(VWAPState2& state, double price, int volume, Utilities::TimeType timestamp);
    void PruneOldTrades(VWAPState2& state, Utilities::TimeType cutoff_time);
    double GetVWAP(const VWAPState2& state) const;
    bool IsVWAPReady(const VWAPState2& state) const;

    // --- OFI helpers ---
    bool IsQuoteValid(const MarketModels::Quote& top_quote) const;
    double ComputeOFIIncrement(const OFIState2& state, double bid, int bid_size, double ask, int ask_size) const;
    void AddEventToWindow(OFIState2& state, double ofi_increment, Utilities::TimeType timestamp);
    void PruneOldEvents(OFIState2& state, Utilities::TimeType cutoff_time);
    bool IsOFIReady(const OFIState2& state) const;
    double CalculateDepth(const MarketModels::Quote& top_quote) const;
    double CalculateSignal(const OFIState2& state, double depth) const;

    // --- Trading helpers ---
    double CalculateMidPrice(const MarketModels::Quote& top_quote) const;
    double CalculateDeviationBps(double mid, double vwap) const;

    void PlaceMakerLimit(const MarketModels::Instrument* instrument, int trade_size, double limit_price);
    void CancelIfFlipping(const MarketModels::Instrument* instrument, int trade_size);

private:
    // Per-instrument states
    std::unordered_map<const MarketModels::Instrument*, VWAPState2> vwap_state_;
    std::unordered_map<const MarketModels::Instrument*, OFIState2>  ofi_state_;

    // VWAP params
    int vwap_window_seconds_;
    double dev_threshold_bps_;

    // OFI params
    int ofi_window_seconds_;
    int min_events_required_;
    double ofi_threshold_;
    double impact_multiplier_;

    // Execution params
    int max_inventory_;
    int position_size_;
    double max_spread_bps_;
    bool debug_;
};

extern "C" {
    _STRATEGY_EXPORTS const char* GetType() {
        return "VWAPOFIStrategy";
    }

    _STRATEGY_EXPORTS IStrategy* CreateStrategy(const char* strategyType,
                                                unsigned strategyID,
                                                const char* strategyName,
                                                const char* groupName)
    {
        if (strcmp(strategyType, GetType()) == 0) {
            return *(new VWAPOFIStrategy(strategyID, strategyName, groupName));
        }
        return nullptr;
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
