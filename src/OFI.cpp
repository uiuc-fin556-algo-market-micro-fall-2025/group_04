/*================================================================================                               
*     Source: ../RCM/StrategyStudio/examples/strategies/SimpleMomentumStrategy/SimpleMomentumStrategy.cpp                                                        
*     Last Update: 2013/6/1 13:55:14                                                                            
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

#ifdef _WIN32
    #include "stdafx.h"
#endif

#include "OFI.h"

#include "FillInfo.h"
#include "AllEventMsg.h"
#include "ExecutionTypes.h"
#include <Utilities/Cast.h>
#include <Utilities/utils.h>

#include <boost/date_time/posix_time/posix_time.hpp>

#include <cmath>
#include <iostream>
#include <sstream>
#include <cassert>
#include <algorithm>

using namespace RCM::StrategyStudio;
using namespace RCM::StrategyStudio::MarketModels;
using namespace RCM::StrategyStudio::Utilities;

using namespace std;


OFIStrategy::OFIStrategy(StrategyID strategyID, const std::string& strategyName, const std::string& groupName) :
    Strategy(strategyID, strategyName, groupName),
    ofi_state_(),
    ofi_window_seconds_(60),
    min_events_required_(10),
    entry_threshold_(0.25),
    impact_multiplier_(1.0),
    max_spread_bps_(25.0),
    max_inventory_(5),
    position_size_(1),
    debug_(true)
{
}

OFIStrategy::~OFIStrategy()
{
}

void OFIStrategy::OnResetStrategyState()
{
    for (auto& kv : ofi_state_) {
        kv.second.Reset();
    }
    ofi_state_.clear();
}

void OFIStrategy::DefineStrategyParams()
{
    params().CreateParam(CreateStrategyParamArgs("ofi_window_seconds", STRATEGY_PARAM_TYPE_STARTUP, VALUE_TYPE_INT, ofi_window_seconds_));
    params().CreateParam(CreateStrategyParamArgs("min_events_required", STRATEGY_PARAM_TYPE_STARTUP, VALUE_TYPE_INT, min_events_required_));
    params().CreateParam(CreateStrategyParamArgs("entry_threshold", STRATEGY_PARAM_TYPE_RUNTIME, VALUE_TYPE_DOUBLE, entry_threshold_));
    params().CreateParam(CreateStrategyParamArgs("impact_multiplier", STRATEGY_PARAM_TYPE_RUNTIME, VALUE_TYPE_DOUBLE, impact_multiplier_));
    params().CreateParam(CreateStrategyParamArgs("max_spread_bps", STRATEGY_PARAM_TYPE_RUNTIME, VALUE_TYPE_DOUBLE, max_spread_bps_));
    params().CreateParam(CreateStrategyParamArgs("max_inventory", STRATEGY_PARAM_TYPE_RUNTIME, VALUE_TYPE_INT, max_inventory_));
    params().CreateParam(CreateStrategyParamArgs("position_size", STRATEGY_PARAM_TYPE_RUNTIME, VALUE_TYPE_INT, position_size_));
    params().CreateParam(CreateStrategyParamArgs("debug", STRATEGY_PARAM_TYPE_RUNTIME, VALUE_TYPE_BOOL, debug_));
}

void OFIStrategy::DefineStrategyCommands()
{
    commands().AddCommand(StrategyCommand(1, "Cancel All Orders"));
    // commands().AddCommand(StrategyCommand(2, "Flatten (Cancel + Close)"));
}

void OFIStrategy::RegisterForStrategyEvents(StrategyEventRegister* eventRegister, DateType currDate)
{
    // We rely on TopQuote to compute OFI at the best bid/ask.
    // Register for each symbol configured for this strategy instance.
    for (auto it = symbols_begin(); it != symbols_end(); ++it) {
        eventRegister->RegisterForFutures(*it);
    }
}

void OFIStrategy::OnTopQuote(const QuoteEventMsg& msg)
{
    const Instrument* instr = &msg.instrument();
    const Quote& top_quote = instr->top_quote();

    if (!IsQuoteValid(top_quote)) {
        return;
    }

    // 1) Update OFI state for this instrument
    OFIInstrumentState& state = ofi_state_[instr];

    const double bid = top_quote.bid();
    const double ask = top_quote.ask();
    const int bid_size = top_quote.bid_size();
    const int ask_size = top_quote.ask_size();

    if (!state.initialized) {
        state.initialized = true;
        state.prev_bid = bid;
        state.prev_ask = ask;
        state.prev_bid_size = bid_size;
        state.prev_ask_size = ask_size;
        return;
    }

    // 2) Compute OFI increment from consecutive top-of-book snapshots
    const double ofi_inc = ComputeOFIIncrement(state, bid, bid_size, ask, ask_size);

    // 3) Add to rolling window + prune
    AddEventToWindow(state, ofi_inc, msg.event_time());

    boost::posix_time::time_duration window_duration = boost::posix_time::seconds(ofi_window_seconds_);
    Utilities::TimeType cutoff_time = msg.event_time() - window_duration;
    PruneOldEvents(state, cutoff_time);

    // 4) Update previous snapshot for next event
    state.prev_bid = bid;
    state.prev_ask = ask;
    state.prev_bid_size = bid_size;
    state.prev_ask_size = ask_size;

    // 5) Guardrails: window readiness and spread filter
    if (!IsOFIReady(state)) {
        if (debug_) {
            ostringstream oss;
            oss << instr->symbol() << " | OFI window not ready (n=" << state.window.size() << ")";
            logger().LogToClient(LOGLEVEL_DEBUG, oss.str());
        }
        return;
    }

    const double spread_bps = CalculateSpreadBps(top_quote);
    if (max_spread_bps_ > 0.0 && spread_bps > max_spread_bps_) {
        if (debug_) {
            ostringstream oss;
            oss << instr->symbol() << " | Skipping: spread=" << spread_bps << "bps > max_spread_bps=" << max_spread_bps_;
            logger().LogToClient(LOGLEVEL_DEBUG, oss.str());
        }
        return;
    }

    // 6) Build signal from normalized OFI
    const double depth = CalculateDepth(top_quote);
    const double signal = CalculateSignal(state, depth);
    const double mid = CalculateMidPrice(top_quote);

    const int current_position = portfolio().position(instr);

    if (debug_) {
        std::cout << instr->symbol()
                  << " | Mid=" << mid
                  << " | Bid=" << bid_size << "@" << bid
                  << " | Ask=" << ask_size << "@" << ask
                  << " | OFI=" << state.cumulative_ofi
                  << " | Depth=" << depth
                  << " | Signal=" << signal
                  << " | Pos=" << current_position
                  << std::endl;
    }

    int desired_position = current_position;

    // Exit logic: if we have a position and signal crossed zero against us
    if (current_position > 0 && signal <= 0.0) {
        desired_position = 0;
        if (debug_) {
            logger().LogToClient(LOGLEVEL_DEBUG, "EXIT LONG signal - OFI reverted / flipped");
        }
    }
    else if (current_position < 0 && signal >= 0.0) {
        desired_position = 0;
        if (debug_) {
            logger().LogToClient(LOGLEVEL_DEBUG, "EXIT SHORT signal - OFI reverted / flipped");
        }
    }
    // Entry / add logic
    else if (std::abs(current_position) < max_inventory_) {
        if (signal > entry_threshold_) {
            desired_position = std::min(max_inventory_, current_position + position_size_);
            if (debug_) {
                ostringstream oss;
                oss << "ENTRY/ADD LONG signal (signal=" << signal << " > " << entry_threshold_ << ")";
                logger().LogToClient(LOGLEVEL_DEBUG, oss.str());
            }
        }
        else if (signal < -entry_threshold_) {
            desired_position = std::max(-max_inventory_, current_position - position_size_);
            if (debug_) {
                ostringstream oss;
                oss << "ENTRY/ADD SHORT signal (signal=" << signal << " < -" << entry_threshold_ << ")";
                logger().LogToClient(LOGLEVEL_DEBUG, oss.str());
            }
        }
    }

    // 8) Adjust portfolio if desired differs from current
    if (desired_position != current_position) {
        AdjustPortfolio(instr, desired_position);
    }
}

void OFIStrategy::OnOrderUpdate(const OrderUpdateEventMsg& msg)
{
    // Minimal bookkeeping / logging 
    const Order& order = msg.order();

    if (debug_) {
        ostringstream oss;
        oss << "OrderUpdate: " << order.instrument()->symbol()
            << " | id=" << order.order_id()
            << " | side=" << (IsBuySide(order.order_side()) ? "BUY" : "SELL")
            << " | state=" << order.order_state();

        logger().LogToClient(LOGLEVEL_DEBUG, oss.str());
    }
}

void OFIStrategy::OnStrategyCommand(const StrategyCommandEventMsg& msg)
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

void OFIStrategy::OnParamChanged(StrategyParam& param)
{
    if (param.param_name() == "ofi_window_seconds") {
        if (!param.Get(&ofi_window_seconds_))
            throw StrategyStudioException("Could not get ofi_window_seconds");
    } else if (param.param_name() == "min_events_required") {
        if (!param.Get(&min_events_required_))
            throw StrategyStudioException("Could not get min_events_required");
    } else if (param.param_name() == "entry_threshold") {
        if (!param.Get(&entry_threshold_))
            throw StrategyStudioException("Could not get entry_threshold");
    } else if (param.param_name() == "impact_multiplier") {
        if (!param.Get(&impact_multiplier_))
            throw StrategyStudioException("Could not get impact_multiplier");
    } else if (param.param_name() == "max_spread_bps") {
        if (!param.Get(&max_spread_bps_))
            throw StrategyStudioException("Could not get max_spread_bps");
    } else if (param.param_name() == "max_inventory") {
        if (!param.Get(&max_inventory_))
            throw StrategyStudioException("Could not get max_inventory");
    } else if (param.param_name() == "position_size") {
        if (!param.Get(&position_size_))
            throw StrategyStudioException("Could not get position_size");
    } else if (param.param_name() == "debug") {
        if (!param.Get(&debug_))
            throw StrategyStudioException("Could not get debug");
    }
}

void OFIStrategy::AdjustPortfolio(const Instrument* instrument, int desired_position)
{
    int current_position = portfolio().position(instrument);
    int trade_size = desired_position - current_position;

    if (trade_size != 0) {
        if (orders().num_working_orders(instrument) == 0) {
            SendOrder(instrument, trade_size);
        } else {
            // If flipping direction, cancel first
            const Order* order = *orders().working_orders_begin(instrument);
            if (order && ((IsBuySide(order->order_side()) && trade_size < 0) ||
                          (IsSellSide(order->order_side()) && trade_size > 0))) {
                trade_actions()->SendCancelOrder(order->order_id());
            }
        }
    }
}

void OFIStrategy::SendOrder(const Instrument* instrument, int trade_size)
{
    if (trade_size == 0) {
        return;
    }

    const Quote& top_quote = instrument->top_quote();
    if (!IsQuoteValid(top_quote)) {
        return;
    }

    // Use mid as a reference price for logging; order type is MARKET for immediacy.
    const double price = (top_quote.bid() + top_quote.ask()) / 2.0;

    OrderParams params(*instrument,
                       std::abs(trade_size),
                       price,
                       (instrument->type() == INSTRUMENT_TYPE_EQUITY) ? MARKET_CENTER_ID_NASDAQ : MARKET_CENTER_ID_CME_GLOBEX,
                       (trade_size > 0) ? ORDER_SIDE_BUY : ORDER_SIDE_SELL,
                       ORDER_TIF_DAY,
                       ORDER_TYPE_MARKET);

    trade_actions()->SendNewOrder(params);

    if (debug_) {
        std::ostringstream oss;
        oss << "Sending MARKET " << ((trade_size > 0) ? "BUY" : "SELL")
            << " order for " << instrument->symbol()
            << " for " << std::abs(trade_size) << " units at ~" << price;
        logger().LogToClient(LOGLEVEL_DEBUG, oss.str());
    }
}

bool OFIStrategy::IsQuoteValid(const Quote& top_quote) const
{
    return (top_quote.bid() > 0.0 &&
            top_quote.ask() > 0.0 &&
            top_quote.ask() > top_quote.bid() &&
            top_quote.bid_size() > 0 &&
            top_quote.ask_size() > 0);
}

double OFIStrategy::ComputeOFIIncrement(const OFIInstrumentState& state,
                                       double bid, int bid_size,
                                       double ask, int ask_size) const
{
    // Implements the indicator form from Cont-Kukanov-Stoikov (2011):
    // e_n = 1{Pb_n >= Pb_{n-1}} qB_n - 1{Pb_n <= Pb_{n-1}} qB_{n-1}
    //     -1{Pa_n <= Pa_{n-1}} qA_n + 1{Pa_n >= Pa_{n-1}} qA_{n-1}
    double e = 0.0;

    if (bid >= state.prev_bid) {
        e += static_cast<double>(bid_size);
    }
    if (bid <= state.prev_bid) {
        e -= static_cast<double>(state.prev_bid_size);
    }

    if (ask <= state.prev_ask) {
        e -= static_cast<double>(ask_size);
    }
    if (ask >= state.prev_ask) {
        e += static_cast<double>(state.prev_ask_size);
    }

    return e;
}

void OFIStrategy::AddEventToWindow(OFIInstrumentState& state, double ofi_increment, Utilities::TimeType timestamp)
{
    state.window.emplace_back(timestamp, ofi_increment);
    state.cumulative_ofi += ofi_increment;

    if (debug_) {
        ostringstream oss;
        oss << "Added OFI event: inc=" << ofi_increment
            << " | OFI=" << state.cumulative_ofi
            << " | n=" << state.window.size();
        logger().LogToClient(LOGLEVEL_DEBUG, oss.str());
    }
}

void OFIStrategy::PruneOldEvents(OFIInstrumentState& state, Utilities::TimeType cutoff_time)
{
    int removed = 0;
    while (!state.window.empty() && state.window.front().timestamp < cutoff_time) {
        state.cumulative_ofi -= state.window.front().ofi_increment;
        state.window.pop_front();
        removed++;
    }

    if (debug_ && removed > 0) {
        ostringstream oss;
        oss << "Pruned " << removed << " OFI events | n=" << state.window.size()
            << " | OFI=" << state.cumulative_ofi;
        logger().LogToClient(LOGLEVEL_DEBUG, oss.str());
    }
}

bool OFIStrategy::IsOFIReady(const OFIInstrumentState& state) const
{
    return static_cast<int>(state.window.size()) >= min_events_required_;
}

double OFIStrategy::CalculateMidPrice(const Quote& top_quote) const
{
    return (top_quote.bid() + top_quote.ask()) / 2.0;
}

double OFIStrategy::CalculateSpreadBps(const Quote& top_quote) const
{
    const double mid = CalculateMidPrice(top_quote);
    if (mid <= 0.0) {
        return 0.0;
    }
    return ((top_quote.ask() - top_quote.bid()) / mid) * 10000.0;
}

double OFIStrategy::CalculateDepth(const Quote& top_quote) const
{
    return (static_cast<double>(top_quote.bid_size()) + static_cast<double>(top_quote.ask_size())) / 2.0;
}

double OFIStrategy::CalculateSignal(const OFIInstrumentState& state, double depth) const
{
    // Normalized signal: OFI / (2 * depth) (scaled by impact_multiplier)
    const double denom = std::max(1.0, 2.0 * depth);
    return impact_multiplier_ * (state.cumulative_ofi / denom);
}