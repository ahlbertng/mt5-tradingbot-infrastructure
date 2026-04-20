"""
Risk Manager - Handles position sizing and risk management
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class RiskManager:
    """Manages trading risk and position sizing"""
    
    def __init__(
        self,
        max_risk_per_trade: float = 0.02,  # 2% per trade
        max_daily_loss: float = 0.05,      # 5% max daily loss
        max_positions: int = 3,             # Max concurrent positions
        max_leverage: float = 10.0          # Max leverage
    ):
        """Initialize risk manager"""
        self.max_risk_per_trade = max_risk_per_trade
        self.max_daily_loss = max_daily_loss
        self.max_positions = max_positions
        self.max_leverage = max_leverage
        
        self.daily_start_balance = None
        self.daily_losses = 0.0
        # Track per-position peak profit percentages for trailing stops
        # Keyed by position ticket or identifier
        self.position_peaks = {}
        
    def check_risk_limits(self, account_info: Dict[str, Any]) -> bool:
        """Check if risk limits are within acceptable ranges"""
        try:
            # Initialize daily start balance if not set
            if self.daily_start_balance is None:
                self.daily_start_balance = account_info['balance']
            
            # Check daily loss limit
            current_balance = account_info['balance']

            # Enforce max positions if caller provides current open positions
            open_positions = account_info.get('open_positions')
            if open_positions is not None:
                try:
                    if int(open_positions or 0) >= int(self.max_positions or 0):
                        logger.warning(f"Max positions reached: {open_positions} >= {self.max_positions}")
                        return False
                except Exception:
                    # If parsing fails, continue but log
                    logger.debug(f"Unable to parse open_positions from account_info: {open_positions}")

            # Guard division by zero
            if not self.daily_start_balance or self.daily_start_balance <= 0:
                logger.warning(f"Invalid daily_start_balance: {self.daily_start_balance}")
                return False

            daily_loss_pct = (self.daily_start_balance - current_balance) / self.daily_start_balance

            if daily_loss_pct >= self.max_daily_loss:
                logger.warning(f"Daily loss limit reached: {daily_loss_pct:.2%}")
                # Update daily_losses
                self.daily_losses += max(0.0, self.daily_start_balance - current_balance)
                return False
            
            # Check margin level
            if account_info.get('margin_level', 1000) < 200:  # 200% minimum
                logger.warning(f"Margin level too low: {account_info.get('margin_level'):.2f}%")
                return False
            
            # Check if account equity is sufficient
            if account_info['equity'] < account_info['balance'] * 0.8:
                logger.warning("Account equity dropped below 80% of balance")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking risk limits: {e}")
            return False
    
    def calculate_position_size(
        self,
        account_balance: float,
        stop_loss_pips: int,
        symbol: str = "EURUSD",
        pip_value: float = 0.0001
    ) -> float:
        """Calculate position size based on risk parameters"""
        try:
            # Calculate risk amount in dollars
            risk_amount = account_balance * self.max_risk_per_trade
            
            # Calculate pip value for standard lot (100,000 units)
            # Use provided pip_value parameter (pip value per unit) to compute pip value per lot
            # pip_value is the quote currency movement per pip for 1 unit; for standard lot (100,000 units):
            pip_value_per_lot = pip_value * 100000
            
            # Calculate position size
            # Position size (lots) = Risk Amount / (Stop Loss in Pips × Pip Value per Lot)
            if stop_loss_pips <= 0:
                raise ValueError("stop_loss_pips must be > 0")

            position_size = risk_amount / (stop_loss_pips * pip_value_per_lot)
            
            # Round to 2 decimal places (standard for lot sizes)
            position_size = round(position_size, 2)
            
            # Minimum position size
            if position_size < 0.01:
                position_size = 0.01
            
            # Maximum position size (limit to reasonable amount)
            max_position = account_balance / 100000 * self.max_leverage  # Max lots based on leverage
            if position_size > max_position:
                position_size = max_position
            
            logger.info(f"Calculated position size: {position_size} lots")
            
            return position_size
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0.01  # Default minimum
    
    def should_close_position(
        self,
        position: Dict[str, Any],
        current_price: float
    ) -> bool:
        """Determine if a position should be closed"""
        try:
            # Calculate current profit/loss percentage
            if position['type'] == 'BUY':
                pnl_pct = (current_price - position['price_open']) / position['price_open']
            else:
                pnl_pct = (position['price_open'] - current_price) / position['price_open']
            
            # Close if loss exceeds max risk per trade
            if pnl_pct <= -self.max_risk_per_trade:
                logger.info(f"Closing position due to stop loss: {pnl_pct:.2%}")
                # Update daily_losses on realized loss
                try:
                    loss_amount = max(0.0, position.get('volume', 0) * (position.get('price_open', 0) - current_price))
                    self.daily_losses += loss_amount
                except Exception:
                    pass
                return True
            
            # Implement trailing stop (close if price dropped 50% from peak profit)
            ticket = position.get('ticket')
            # Only start tracking after a small profit threshold
            profit_threshold = 0.02

            if pnl_pct > profit_threshold:
                # update peak
                if ticket is not None:
                    prev_peak = self.position_peaks.get(ticket, 0.0)
                    new_peak = max(prev_peak, pnl_pct)
                    self.position_peaks[ticket] = new_peak

            # if we have a recorded peak and current pnl has fallen to <=50% of peak, close
            if ticket is not None and ticket in self.position_peaks:
                peak = self.position_peaks.get(ticket, 0.0)
                if peak > 0 and pnl_pct <= peak * 0.5:
                    logger.info(f"Trailing stop triggered for ticket {ticket}: pnl={pnl_pct:.2%}, peak={peak:.2%}")
                    # clear peak to avoid repeated triggers
                    try:
                        del self.position_peaks[ticket]
                    except Exception:
                        pass
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking position closure: {e}")
            return False
    
    def get_stop_loss_price(
        self,
        entry_price: float,
        order_type: str,
        stop_loss_pips: int,
        pip_value: float = 0.0001
    ) -> float:
        """Calculate stop loss price"""
        if order_type == "BUY":
            return entry_price - (stop_loss_pips * pip_value)
        else:
            return entry_price + (stop_loss_pips * pip_value)
    
    def get_take_profit_price(
        self,
        entry_price: float,
        order_type: str,
        take_profit_pips: int,
        pip_value: float = 0.0001
    ) -> float:
        """Calculate take profit price"""
        if order_type == "BUY":
            return entry_price + (take_profit_pips * pip_value)
        else:
            return entry_price - (take_profit_pips * pip_value)
    
    def reset_daily_metrics(self):
        """Reset daily tracking metrics (call at start of each day)"""
        self.daily_start_balance = None
        self.daily_losses = 0.0
        # Reset any per-position peak tracking
        self.position_peaks = {}
        logger.info("Daily risk metrics reset")

    def clear_position_peak(self, ticket: Any):
        """Clear stored peak for a given position when it is closed externally"""
        try:
            if ticket in self.position_peaks:
                del self.position_peaks[ticket]
        except Exception:
            pass
