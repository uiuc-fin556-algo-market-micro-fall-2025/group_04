#ifdef _WIN32
    #include "stdafx.h"
#endif

#include "VWAPOFI.h"

#include "FillInfo.h"
#include "AllEventMsg.h"
#include "ExecutionTypes.h"
#include <Utilities/Cast.h>
#include <Utilities/utils.h>

#include <cmath>
#include <sstream>
#include <algorithm>
#include <iostream>

using namespace RCM::StrategyStudio;
using namespace RCM::StrategyStudio::MarketModels;
using namespace RCM::StrategyStudio::Utilities;

VWAPOFIStrategy::VWAPOFIStrategy(StrategyID strategyID,
                                 const std::string& strategyName,
                                 const std::string& groupName)
    : Strategy(strategyID, strategyName, groupName),
      vwap_state_(),
      ofi_state_(),
      vwap_window_seconds_(300),
      dev_threshold_bps_(2.0),
      ofi_window_seconds_(60),
      min_events_required_(10),
      ofi_threshold_(0.5),
      impact_multiplier_(1.0),
      max_inventory_(5),
      position_size_(1),
      max_spread_bps_(25.0),
      debug_(true)
{
}

VWAPOFIStrategy::~VWAPOFIStrategy() {}

void VWAPOFIStrategy::OnResetStrategyState()
{
    for (auto& kv : vwap_state_) kv.second.Reset();
    for (auto& kv : ofi_state_)  kv.second.Reset();
    vwap_state_.clear();
    ofi_state_.clear();
}

void VWAPOFIStrategy::DefineStrategyParams()
{
    params().CreateParam(CreateStrategyParamArgs("vwap_window_seconds", STRATEGY_PARAM_TYPE_STARTUP, VALUE_TYPE_INT, vwap_window_seconds_));
    params().CreateParam(CreateStrategyParamArgs("dev_threshold_bps", STRATEGY_PARAM_TYPE_RUNTIME, VALUE_TYPE_DOUBLE, dev_threshold_bps_));

    params().CreateParam(CreateStrategyParamArgs("ofi_window_seconds", STRATEGY_PARAM_TYPE_STARTUP, VALUE_TYPE_INT, ofi_window_seconds_));
    params().CreateParam(CreateStrategyParamArgs("min_events_required", STRATEGY_PARAM_TYPE_STARTUP, VALUE_TYPE_INT, min_events_required_));
    params().CreateParam(CreateStrategyParamArgs("ofi_threshold", STRATEGY_PARAM_TYPE_RUNTIME, VALUE_TYPE_DOUBLE, ofi_threshold_));
    params().CreateParam(CreateStrategyParamArgs("impact_multiplier", STRATEGY_PARAM_TYPE_RUNTIME, VALUE_TYPE_DOUBLE, impact_multiplier_));

    params().CreateParam(CreateStrategyParamArgs("max_spread_bps", STRATEGY_PARAM_TYPE_RUNTIME, VALUE_TYPE_DOUBLE, max_spread_bps_));
    params().CreateParam(CreateStrategyParamArgs("max_inventory", STRATEGY_PARAM_TYPE_RUNTIME, VALUE_TYPE_INT, max_inventory_));
    params().CreateParam(CreateStrategyParamArgs("position_size", STRATEGY_PARAM_TYPE_RUNTIME, VALUE_TYPE_INT, position_size_));
    params().CreateParam(CreateStrategyParamArgs("debug", STRATEGY_PARAM_TYPE_RUNTIME, VALUE_TYPE_BOOL, debug_));
}

void VWAPOFIStrategy::DefineStrategyCommands()
{
    commands().AddCommand(StrategyCommand(1, "Cancel All Orders"));
}

void VWAPOFIStrategy::RegisterForStrategyEvents(StrategyEventRegister* eventRegister, DateType /*currDate*/)
{
    // We need both Trade (VWAP) and TopQuote (OFI + pricing limits)
    for (auto it = symbols_begin(); it != symbols_end(); ++it) {
        eventRegister->RegisterForFutures(*it);
    }
}

bool VWAPOFIStrategy::IsQuoteValid(const Quote& top_quote) const
{
    return (top_quote.bid() > 0.0 &&
            top_quote.ask() > 0.0 &&
            top_quote.ask() > top_quote.bid() &&
            top_quote.bid_size() > 0 &&
            top_quote.ask_size() > 0);
}

double VWAPOFIStrategy::CalculateMidPrice(const Quote& top_quote) const
{
    return (top_quote.bid() + top_quote.ask()) / 2.0;
}

double VWAPOFIStrategy::CalculateDeviationBps(double mid, double vwap) const
{
    if (vwap <= 0.0) return 0.0;
    return ((mid - vwap) / vwap) * 10000.0;
}

// -------------------- VWAP helpers --------------------
void VWAPOFIStrategy::AddTradeToWindow(VWAPState2& state, double price, int volume, Utilities::TimeType timestamp)
{
    state.window.emplace_back(timestamp, price, volume);
    state.cumulative_pv += price * static_cast<double>(volume);
    state.cumulative_volume += volume;
}

void VWAPOFIStrategy::PruneOldTrades(VWAPState2& state, Utilities::TimeType cutoff_time)
{
    while (!state.window.empty() && state.window.front().timestamp < cutoff_time) {
        const auto& old = state.window.front();
        state.cumulative_pv -= old.price * static_cast<double>(old.volume);
        state.cumulative_volume -= old.volume;
        state.window.pop_front();
    }
}

double VWAPOFIStrategy::GetVWAP(const VWAPState2& state) const
{
    if (state.cumulative_volume <= 0) return 0.0;
    return state.cumulative_pv / static_cast<double>(state.cumulative_volume);
}

bool VWAPOFIStrategy::IsVWAPReady(const VWAPState2& state) const
{
    // Match your existing VWAP strategy behavior:
    // ready if >= 3 trades OR time-span >= window seconds.
    const int MIN_TRADE_REQUIRED = 3;
    if (static_cast<int>(state.window.size()) >= MIN_TRADE_REQUIRED) {
        return true;
    }
    if (state.window.size() < 2) {
        return false;
    }

    boost::posix_time::time_duration span = state.window.back().timestamp - state.window.front().timestamp;
    return span.total_seconds() >= vwap_window_seconds_;
}

// -------------------- OFI helpers --------------------
double VWAPOFIStrategy::ComputeOFIIncrement(const OFIState2& state,
                                           double bid, int bid_size,
                                           double ask, int ask_size) const
{
    // Same logic as your standalone OFI strategy
    double e = 0.0;
    if (bid >= state.prev_bid) e += static_cast<double>(bid_size);
    if (bid <= state.prev_bid) e -= static_cast<double>(state.prev_bid_size);

    if (ask <= state.prev_ask) e -= static_cast<double>(ask_size);
    if (ask >= state.prev_ask) e += static_cast<double>(state.prev_ask_size);

    return e;
}

void VWAPOFIStrategy::AddEventToWindow(OFIState2& state, double ofi_increment, Utilities::TimeType timestamp)
{
    state.window.emplace_back(timestamp, ofi_increment);
    state.cumulative_ofi += ofi_increment;
}

void VWAPOFIStrategy::PruneOldEvents(OFIState2& state, Utilities::TimeType cutoff_time)
{
    while (!state.window.empty() && state.window.front().timestamp < cutoff_time) {
        state.cumulative_ofi -= state.window.front().ofi_increment;
        state.window.pop_front();
    }
}

bool VWAPOFIStrategy::IsOFIReady(const OFIState2& state) const
{
    return static_cast<int>(state.window.size()) >= min_events_required_;
}

double VWAPOFIStrategy::CalculateDepth(const Quote& top_quote) const
{
    return (static_cast<double>(top_quote.bid_size()) + static_cast<double>(top_quote.ask_size())) / 2.0;
}

double VWAPOFIStrategy::CalculateSignal(const OFIState2& state, double depth) const
{
    const double denom = std::max(1.0, 2.0 * depth);
    return impact_multiplier_ * (state.cumulative_ofi / denom);
}

// -------------------- Event handlers --------------------
void VWAPOFIStrategy::OnTopQuote(const QuoteEventMsg& msg)
{
    const Instrument* instr = &msg.instrument();
    const Quote& top_quote = instr->top_quote();
    if (!IsQuoteValid(top_quote)) return;

    OFIState2& st = ofi_state_[instr];

    const double bid = top_quote.bid();
    const double ask = top_quote.ask();
    const int bid_sz = top_quote.bid_size();
    const int ask_sz = top_quote.ask_size();

    if (!st.initialized) {
        st.initialized = true;
        st.prev_bid = bid;
        st.prev_ask = ask;
        st.prev_bid_size = bid_sz;
        st.prev_ask_size = ask_sz;
        return;
    }

    const double inc = ComputeOFIIncrement(st, bid, bid_sz, ask, ask_sz);
    AddEventToWindow(st, inc, msg.event_time());

    boost::posix_time::time_duration dur = boost::posix_time::seconds(ofi_window_seconds_);
    Utilities::TimeType cutoff = msg.event_time() - dur;
    PruneOldEvents(st, cutoff);

    st.prev_bid = bid;
    st.prev_ask = ask;
    st.prev_bid_size = bid_sz;
    st.prev_ask_size = ask_sz;
}

void VWAPOFIStrategy::CancelIfFlipping(const Instrument* instrument, int trade_size)
{
    if (orders().num_working_orders(instrument) == 0) return;

    const Order* order = *orders().working_orders_begin(instrument);
    if (!order) return;

    const bool working_buy = IsBuySide(order->order_side());
    if ((working_buy && trade_size < 0) || (!working_buy && trade_size > 0)) {
        trade_actions()->SendCancelOrder(order->order_id());
    }
}

void VWAPOFIStrategy::PlaceMakerLimit(const Instrument* instrument, int trade_size, double limit_price)
{
    if (trade_size == 0) return;

    OrderParams params(*instrument,
                       std::abs(trade_size),
                       limit_price,
                       (instrument->type() == INSTRUMENT_TYPE_EQUITY) ? MARKET_CENTER_ID_NASDAQ : MARKET_CENTER_ID_CME_GLOBEX,
                       (trade_size > 0) ? ORDER_SIDE_BUY : ORDER_SIDE_SELL,
                       ORDER_TIF_DAY,
                       ORDER_TYPE_LIMIT);

    trade_actions()->SendNewOrder(params);

    if (debug_) {
        std::ostringstream oss;
        oss << "Sending LIMIT " << ((trade_size > 0) ? "BUY" : "SELL")
            << " " << instrument->symbol()
            << " qty=" << std::abs(trade_size)
            << " px=" << limit_price;
        logger().LogToClient(LOGLEVEL_DEBUG, oss.str());
    }
}

void VWAPOFIStrategy::OnTrade(const TradeDataEventMsg& msg)
{
    const Instrument* instr = &msg.instrument();
    const Quote& top_quote = instr->top_quote();

    // Update VWAP window
    VWAPState2& vw = vwap_state_[instr];
    AddTradeToWindow(vw, msg.trade().price(), msg.trade().size(), msg.event_time());

    boost::posix_time::time_duration vw_dur = boost::posix_time::seconds(vwap_window_seconds_);
    Utilities::TimeType vw_cutoff = msg.event_time() - vw_dur;
    PruneOldTrades(vw, vw_cutoff);

    if (!IsVWAPReady(vw)) return;
    if (!IsQuoteValid(top_quote)) return;

    // Guardrail: spread filter (same style as OFI)
    const double mid = CalculateMidPrice(top_quote);
    const double spread_bps = (mid > 0.0) ? ((top_quote.ask() - top_quote.bid()) / mid) * 10000.0 : 0.0;
    if (max_spread_bps_ > 0.0 && spread_bps > max_spread_bps_) return;

    // Need OFI state ready too
    auto it = ofi_state_.find(instr);
    if (it == ofi_state_.end()) return;
    const OFIState2& of = it->second;
    if (!IsOFIReady(of)) return;

    const double vwap = GetVWAP(vw);
    const double dev_bps = CalculateDeviationBps(mid, vwap);

    const double depth = CalculateDepth(top_quote);
    const double signal = CalculateSignal(of, depth);

    const int pos = portfolio().position(instr);

    if (debug_) {
        std::ostringstream oss;
        oss << instr->symbol()
            << " | trade=" << msg.trade().size() << "@" << msg.trade().price()
            << " | mid=" << mid
            << " | vwap=" << vwap
            << " | dev_bps=" << dev_bps
            << " | ofi_signal=" << signal
            << " | pos=" << pos
            << " | working=" << orders().num_working_orders(instr);
        logger().LogToClient(LOGLEVEL_DEBUG, oss.str());
    }

    // Liquidation priority: if we have position, only work the close.
    if (pos != 0) {
        if (orders().num_working_orders(instr) == 0) {
            // Close at the opposite side (maker)
            if (pos > 0) {
                PlaceMakerLimit(instr, -std::min(pos, position_size_), top_quote.ask());
            } else {
                PlaceMakerLimit(instr, +std::min(-pos, position_size_), top_quote.bid());
            }
        }
        return;
    }

    // Entry only when flat; strong-only gate
    const bool strong_buy  = (dev_bps < -dev_threshold_bps_) && (signal >  ofi_threshold_);
    const bool strong_sell = (dev_bps >  dev_threshold_bps_) && (signal < -ofi_threshold_);

    if (!strong_buy && !strong_sell) {
        return;
    }

    // If we already have a working order, only keep it if it matches direction
    if (orders().num_working_orders(instr) > 0) {
        // If it doesn't match, cancel; otherwise do nothing
        const Order* o = *orders().working_orders_begin(instr);
        if (o) {
            const bool want_buy = strong_buy;
            const bool working_buy = IsBuySide(o->order_side());
            if (want_buy != working_buy) {
                trade_actions()->SendCancelOrder(o->order_id());
            }
        }
        return;
    }

    // Place maker entry at best bid/ask
    if (strong_buy) {
        PlaceMakerLimit(instr, position_size_, top_quote.bid());
    } else if (strong_sell) {
        PlaceMakerLimit(instr, -position_size_, top_quote.ask());
    }
}

void VWAPOFIStrategy::OnOrderUpdate(const OrderUpdateEventMsg& msg)
{
    if (!debug_) return;

    const Order& order = msg.order();
    std::ostringstream oss;
    oss << "OrderUpdate: " << order.instrument()->symbol()
        << " | id=" << order.order_id()
        << " | side=" << (IsBuySide(order.order_side()) ? "BUY" : "SELL")
        << " | state=" << order.order_state();

    if (msg.fill_occurred() && msg.fill()) {
        oss << " | fill=" << msg.fill()->fill_size() << "@" << msg.fill()->price();
    }

    logger().LogToClient(LOGLEVEL_DEBUG, oss.str());
}

void VWAPOFIStrategy::OnStrategyCommand(const StrategyCommandEventMsg& msg)
{
    switch (msg.command_id()) {
        case 1:
            trade_actions()->SendCancelAll();
            logger().LogToClient(LOGLEVEL_DEBUG, "Cancelled all orders via command");
            break;
        default:
            logger().LogToClient(LOGLEVEL_DEBUG, "Unknown strategy command received");
            break;
    }
}

void VWAPOFIStrategy::OnParamChanged(StrategyParam& param)
{
    if (param.param_name() == "vwap_window_seconds") {
        if (!param.Get(&vwap_window_seconds_)) throw StrategyStudioException("Could not get vwap_window_seconds");
    } else if (param.param_name() == "dev_threshold_bps") {
        if (!param.Get(&dev_threshold_bps_)) throw StrategyStudioException("Could not get dev_threshold_bps");

    } else if (param.param_name() == "ofi_window_seconds") {
        if (!param.Get(&ofi_window_seconds_)) throw StrategyStudioException("Could not get ofi_window_seconds");
    } else if (param.param_name() == "min_events_required") {
        if (!param.Get(&min_events_required_)) throw StrategyStudioException("Could not get min_events_required");
    } else if (param.param_name() == "ofi_threshold") {
        if (!param.Get(&ofi_threshold_)) throw StrategyStudioException("Could not get ofi_threshold");
    } else if (param.param_name() == "impact_multiplier") {
        if (!param.Get(&impact_multiplier_)) throw StrategyStudioException("Could not get impact_multiplier");

    } else if (param.param_name() == "max_spread_bps") {
        if (!param.Get(&max_spread_bps_)) throw StrategyStudioException("Could not get max_spread_bps");
    } else if (param.param_name() == "max_inventory") {
        if (!param.Get(&max_inventory_)) throw StrategyStudioException("Could not get max_inventory");
    } else if (param.param_name() == "position_size") {
        if (!param.Get(&position_size_)) throw StrategyStudioException("Could not get position_size");
    } else if (param.param_name() == "debug") {
        if (!param.Get(&debug_)) throw StrategyStudioException("Could not get debug");
    }
}
