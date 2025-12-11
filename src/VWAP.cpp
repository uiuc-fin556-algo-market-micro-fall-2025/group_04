#ifdef _WIN32
    #include "stdafx.h"
#endif

#include "VWAP.h"

#include "FillInfo.h"
#include "AllEventMsg.h"
#include "ExecutionTypes.h"
#include <Utilities/Cast.h>
#include <Utilities/utils.h>

#include <math.h>
#include <iostream>
#include <cassert>

using namespace RCM::StrategyStudio;
using namespace RCM::StrategyStudio::MarketModels;
using namespace RCM::StrategyStudio::Utilities;
using namespace std;

VWAPStrategy::VWAPStrategy(StrategyID strategyID, const std::string& strategyName, const std::string& groupName):
    Strategy(strategyID, strategyName, groupName),
    vwap_window_(),
    cumulative_pv_(0.0),
    cumulative_volume_(0),
    vwap_window_seconds_(300),
    entry_threshold_bps_(0.1),
    max_inventory_(5),
    position_size_(1),
    debug_(true)
{
}

VWAPStrategy::~VWAPStrategy()
{
}

void VWAPStrategy::OnResetStrategyState()
{
    vwap_window_.clear();
    cumulative_pv_ = 0.0;
    cumulative_volume_ = 0;
}

void VWAPStrategy::DefineStrategyParams()
{
    params().CreateParam(CreateStrategyParamArgs("vwap_window_seconds", STRATEGY_PARAM_TYPE_STARTUP, VALUE_TYPE_INT, vwap_window_seconds_));
    params().CreateParam(CreateStrategyParamArgs("entry_threshold_bps", STRATEGY_PARAM_TYPE_RUNTIME, VALUE_TYPE_DOUBLE, entry_threshold_bps_));
    params().CreateParam(CreateStrategyParamArgs("max_inventory", STRATEGY_PARAM_TYPE_RUNTIME, VALUE_TYPE_INT, max_inventory_));
    params().CreateParam(CreateStrategyParamArgs("position_size", STRATEGY_PARAM_TYPE_RUNTIME, VALUE_TYPE_INT, position_size_));
    params().CreateParam(CreateStrategyParamArgs("debug", STRATEGY_PARAM_TYPE_RUNTIME, VALUE_TYPE_BOOL, debug_));
}

void VWAPStrategy::DefineStrategyCommands()
{
    commands().AddCommand(StrategyCommand(1, "Cancel All Orders"));
}

void VWAPStrategy::RegisterForStrategyEvents(StrategyEventRegister* eventRegister, DateType currDate)
{
    // VWAP strategy reacts to trade events
    // OnTrade is called automatically for all subscribed instruments
    for (auto it = symbols_begin(); it != symbols_end(); ++it) {
        eventRegister->RegisterForFutures(*it);
    }
}

void VWAPStrategy::OnTrade(const TradeDataEventMsg& msg)
{
    // 1. Add this trade to our VWAP window
    AddTradeToWindow(msg.trade().price(), msg.trade().size(), msg.event_time());
    
    // 2. Remove trades older than our window size
    boost::posix_time::time_duration window_duration = boost::posix_time::seconds(vwap_window_seconds_);
    Utilities::TimeType cutoff_time = msg.event_time() - window_duration;
    PruneOldTrades(cutoff_time);
    
    // 3. Skip trading logic if VWAP window not ready (need 5 minutes of data)
    if (!IsVWAPReady()) {
        if (debug_) {
            ostringstream str;
            str << "VWAP window not ready yet (size=" << vwap_window_.size() << ")";
            logger().LogToClient(LOGLEVEL_DEBUG, str.str());
        }
        std::cout << "Skipped" << std::endl;
        return;
    }
    
    // 4. Calculate current VWAP and mid-price
    double vwap = GetVWAP();
    const Instrument* instr = &msg.instrument();
    
    std::cout << "vwap" << std::endl;
    // Validate quote before proceeding
    if (!instr->top_quote().IsValid()) {
        if (debug_) {
            logger().LogToClient(LOGLEVEL_DEBUG, "Invalid quote, skipping");
        }
        return;
    }
    
    double mid_price = CalculateMidPrice(instr);
    double deviation_bps = CalculateDeviation(mid_price, vwap);
    
    // Get current position from portfolio tracker
    int current_position = portfolio().position(instr);
    
    // Debug logging
    if (debug_) {
        ostringstream str;
        str << instr->symbol() 
            << " | Trade: " << msg.trade().size() << "@" << msg.trade().price()
            << " | Mid=" << mid_price 
            << " | VWAP=" << vwap 
            << " | Dev=" << deviation_bps << "bps"
            << " | Pos=" << current_position;
        logger().LogToClient(LOGLEVEL_DEBUG, str.str());
    }
    std::cout << instr->symbol()
            << " | Trade: " << msg.trade().size() << "@" << msg.trade().price()
            << " | Mid=" << mid_price
            << " | VWAP=" << vwap
            << " | Dev=" << deviation_bps << "bps"
            << " | Pos=" << current_position << std::endl;
    
    // 5. Determine desired position based on VWAP deviation
    int desired_position = 0;
    
    // Exit logic: if we have a position and price has reverted to VWAP
    if (current_position > 0 && deviation_bps >= 0) {
        // Long position and price >= VWAP, exit to flat
        desired_position = 0;
        if (debug_) {
            logger().LogToClient(LOGLEVEL_DEBUG, "EXIT LONG signal - price reverted to VWAP");
        }
    }
    else if (current_position < 0 && deviation_bps <= 0) {
        // Short position and price <= VWAP, exit to flat
        desired_position = 0;
        if (debug_) {
            logger().LogToClient(LOGLEVEL_DEBUG, "EXIT SHORT signal - price reverted to VWAP");
        }
    }
    // Entry logic: only if not at max inventory
    else if (abs(current_position) < max_inventory_) {
        if (deviation_bps < -entry_threshold_bps_) {
            // BUY signal: price significantly below VWAP
            desired_position = current_position + position_size_;
            if (debug_) {
                ostringstream str;
                str << "ENTRY BUY signal (dev=" << deviation_bps << "bps)";
                logger().LogToClient(LOGLEVEL_DEBUG, str.str());
            }
        }
        else if (deviation_bps > entry_threshold_bps_) {
            // SELL signal: price significantly above VWAP
            desired_position = current_position - position_size_;
            if (debug_) {
                ostringstream str;
                str << "ENTRY SELL signal (dev=" << deviation_bps << "bps)";
                logger().LogToClient(LOGLEVEL_DEBUG, str.str());
            }
        }
    }
    
    // 6. Adjust portfolio if desired position differs from current
    AdjustPortfolio(instr, desired_position);
}

void VWAPStrategy::OnOrderUpdate(const OrderUpdateEventMsg& msg)
{
    if (debug_) {
        ostringstream str;
        str << "Order Update - OrderID: " << msg.order_id()
            << ", UpdateType: " << OrderUpdateTypeToString(msg.update_type())
            << ", Reason: " << msg.reason();

        // Log fill details if a fill occurred
        if (msg.fill_occurred() && msg.fill()) {
            str << ", Fill Quantity: " << msg.fill()->fill_size()
                << ", Fill Price: " << msg.fill()->price();
        }

        // Log if order is complete
        if (msg.completes_order()) {
            str << ", Order complete | Position: " << portfolio().position(msg.order().instrument());
        }

        logger().LogToClient(LOGLEVEL_DEBUG, str.str());
    }
}

void VWAPStrategy::AdjustPortfolio(const Instrument* instrument, int desired_position)
{
    int current_position = portfolio().position(instrument);
    int trade_size = desired_position - current_position;

    if (trade_size != 0) {
        // If no working order, send a new order
        if (orders().num_working_orders(instrument) == 0) {
            SendOrder(instrument, trade_size);
        } else {
            // If there is a working order, check if we need to cancel it if we are flipping sides
            const Order* order = *orders().working_orders_begin(instrument);
            if (order && ((IsBuySide(order->order_side()) && trade_size < 0) ||
                          (IsSellSide(order->order_side()) && trade_size > 0))) {
                trade_actions()->SendCancelOrder(order->order_id());
            }
        }
    } else {
        // If desired position matches current position, cancel any working orders
        if (orders().num_working_orders(instrument) > 0) {
            trade_actions()->SendCancelAll(instrument);
        }
    }
}

void VWAPStrategy::SendOrder(const Instrument* instrument, int trade_size)
{
    if (!instrument->top_quote().ask_side().IsValid() || !instrument->top_quote().bid_side().IsValid()) {
        std::stringstream ss;
        ss << "Skipping trade due to lack of two sided quote";
        logger().LogToClient(LOGLEVEL_DEBUG, ss.str());
        return;
    }

    // For market orders, price is indicative but order executes at best available
    // Use ask for buys (we'll pay the ask or better), bid for sells (we'll receive bid or better)
    double price = 0.0;
    if (trade_size > 0) {
        price = instrument->top_quote().ask();  // Market buy executes at ask or better
    } else {
        price = instrument->top_quote().bid();  // Market sell executes at bid or better
    }

    // Create MARKET order (not LIMIT)
    OrderParams params(*instrument,
                       abs(trade_size),
                       price,
                       (instrument->type() == INSTRUMENT_TYPE_EQUITY) ? MARKET_CENTER_ID_NASDAQ : MARKET_CENTER_ID_CME_GLOBEX,
                       (trade_size > 0) ? ORDER_SIDE_BUY : ORDER_SIDE_SELL,
                       ORDER_TIF_DAY,
                       ORDER_TYPE_MARKET);  // MARKET order for immediate execution

    trade_actions()->SendNewOrder(params);

    if (debug_) {
        std::ostringstream oss;
        oss << "Sending MARKET " << ((trade_size > 0) ? "BUY" : "SELL") << " order for " 
            << instrument->symbol() << " for " << abs(trade_size) << " units at ~" << price;
        logger().LogToClient(LOGLEVEL_DEBUG, oss.str());
    }
}

void VWAPStrategy::OnStrategyCommand(const StrategyCommandEventMsg& msg)
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

void VWAPStrategy::OnParamChanged(StrategyParam& param)
{
    if (param.param_name() == "vwap_window_seconds") {
        if (!param.Get(&vwap_window_seconds_))
            throw StrategyStudioException("Could not get vwap_window_seconds");
    } else if (param.param_name() == "entry_threshold_bps") {
        if (!param.Get(&entry_threshold_bps_))
            throw StrategyStudioException("Could not get entry_threshold_bps");
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

// VWAP Calculation Helper Methods

void VWAPStrategy::AddTradeToWindow(double price, int volume, Utilities::TimeType timestamp)
{
    VWAPTradeRecord record(timestamp, price, volume);
    vwap_window_.push_back(record);
    cumulative_pv_ += price * volume;
    cumulative_volume_ += volume;
    
    if (debug_) {
        ostringstream str;
        str << "Added trade: price=" << price << " vol=" << volume 
            << " | window_size=" << vwap_window_.size()
            << " | VWAP=" << GetVWAP();
        logger().LogToClient(LOGLEVEL_DEBUG, str.str());
    }
}

void VWAPStrategy::PruneOldTrades(Utilities::TimeType cutoff_time)
{
    int removed_count = 0;
    while (!vwap_window_.empty() && vwap_window_.front().timestamp < cutoff_time) {
        const VWAPTradeRecord& old_record = vwap_window_.front();
        cumulative_pv_ -= old_record.price * old_record.volume;
        cumulative_volume_ -= old_record.volume;
        vwap_window_.pop_front();
        removed_count++;
    }
    
    if (debug_ && removed_count > 0) {
        ostringstream str;
        str << "Pruned " << removed_count << " old trades | window_size=" << vwap_window_.size();
        logger().LogToClient(LOGLEVEL_DEBUG, str.str());
    }
}

double VWAPStrategy::GetVWAP() const
{
    if (cumulative_volume_ == 0) {
        return 0.0;
    }
    return cumulative_pv_ / cumulative_volume_;
}

bool VWAPStrategy::IsVWAPReady() const
{
    // VWAP is ready when we have at least the specified window duration of data
    const int MIN_TRADE_REQUIRED = 3;
    if (vwap_window_.size() >= MIN_TRADE_REQUIRED) {
        return true;
    }
    
    boost::posix_time::time_duration window_span = vwap_window_.back().timestamp - vwap_window_.front().timestamp;
    return window_span.total_seconds() >= vwap_window_seconds_;
}

double VWAPStrategy::CalculateMidPrice(const Instrument* instrument) const
{
    const Quote& top_quote = instrument->top_quote();
    return (top_quote.bid() + top_quote.ask()) / 2.0;
}

double VWAPStrategy::CalculateDeviation(double mid_price, double vwap) const
{
    if (vwap == 0.0) {
        return 0.0;
    }
    return ((mid_price - vwap) / vwap) * 10000.0;  // Convert to basis points
}

