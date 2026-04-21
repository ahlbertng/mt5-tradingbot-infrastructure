"""
MT5 Connector - Handles all MetaTrader 5 platform interactions
"""

import MetaTrader5 as mt5
import pandas as pd
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class MT5Connector:
    """Handles connection and operations with MetaTrader 5"""
    
    def __init__(self, aws_integration=None):
        """Initialize MT5 connector"""
        self.aws = aws_integration
        self.connected = False
        self.account_info = None
        
    def connect(self) -> bool:
        """Connect to MT5 terminal"""
        try:
            # Get credentials from AWS Secrets Manager
            if self.aws:
                credentials = self.aws.get_mt5_credentials()
                login = int(credentials['mt5_login'])
                password = credentials['mt5_password']
                server = credentials['mt5_server']
            else:
                # Fallback to environment variables
                import os
                login_str = os.getenv('MT5_LOGIN')
                password = os.getenv('MT5_PASSWORD')
                server = os.getenv('MT5_SERVER')

                missing = []
                if not login_str:
                    missing.append('MT5_LOGIN')
                if not password:
                    missing.append('MT5_PASSWORD')
                if not server:
                    missing.append('MT5_SERVER')

                if missing:
                    logger.error(f"Missing MT5 credentials in environment: {', '.join(missing)}")
                    return False

                try:
                    login = int(login_str)
                except Exception:
                    logger.error(f"Invalid MT5_LOGIN value: {login_str}")
                    return False
            
            # Initialize MT5
            if not mt5.initialize():
                logger.error(f"MT5 initialize() failed, error code: {mt5.last_error()}")
                return False
            
            # Login to account
            if not mt5.login(login, password, server):
                logger.error(f"MT5 login failed, error code: {mt5.last_error()}")
                mt5.shutdown()
                return False
            
            self.connected = True
            acct = mt5.account_info()
            if acct is not None:
                try:
                    self.account_info = acct._asdict()
                    logger.info(f"Account balance: {self.account_info.get('balance')}")
                except Exception:
                    self.account_info = {}
                    logger.warning("Connected to MT5 but failed to parse account_info() result")
            else:
                self.account_info = {}
                logger.warning("Connected to MT5 but account_info() returned None")

            logger.info(f"Connected to MT5 account: {login} on {server}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to MT5: {e}", exc_info=True)
            return False
    
    def disconnect(self):
        """Disconnect from MT5"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            logger.info("Disconnected from MT5")
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get current account information"""
        try:
            account = mt5.account_info()
            if account is None:
                logger.error("Failed to get account info")
                return None
            
            positions = mt5.positions_get()
            open_positions = len(positions) if positions is not None else 0

            return {
                'balance': account.balance,
                'equity': account.equity,
                'profit': account.profit,
                'margin': account.margin,
                'margin_free': account.margin_free,
                'margin_level': account.margin_level if account.margin > 0 else 0,
                'open_positions': open_positions,
            }
            
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return None
    
    def get_market_data(self, symbol: str = "EURUSD", timeframe=mt5.TIMEFRAME_M5, bars: int = 100) -> Optional[pd.DataFrame]:
        """Get historical market data"""
        try:
            # Get bars
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
            
            if rates is None or len(rates) == 0:
                logger.error(f"Failed to get market data for {symbol}")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting market data: {e}")
            return None
    
    def is_market_open(self, symbol: str = "EURUSD") -> bool:
        """Check if market is open for trading"""
        try:
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)
            
            if symbol_info is None:
                return False
            
            # Check if trading is allowed
            return symbol_info.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL
            
        except Exception as e:
            logger.error(f"Error checking market status: {e}")
            return False
    
    def place_order(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        comment: str = "ML Trading Bot"
    ) -> Dict[str, Any]:
        """Place a market order"""
        try:
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                return {'success': False, 'error': 'Symbol not found'}
            
            # Get current price
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return {'success': False, 'error': 'Failed to get tick data'}
            
            # Determine order type
            if order_type == "BUY":
                order_type_mt5 = mt5.ORDER_TYPE_BUY
                price = tick.ask
            elif order_type == "SELL":
                order_type_mt5 = mt5.ORDER_TYPE_SELL
                price = tick.bid
            else:
                return {'success': False, 'error': 'Invalid order type'}
            
            # Prepare request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type_mt5,
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            if stop_loss is not None:
                request["sl"] = stop_loss
            if take_profit is not None:
                request["tp"] = take_profit

            _t0 = time.monotonic()
            result = mt5.order_send(request)
            latency_ms = (time.monotonic() - _t0) * 1000

            if result is None:
                return {'success': False, 'error': 'Order send failed', 'latency_ms': latency_ms}

            if not hasattr(result, 'retcode') or result.retcode != mt5.TRADE_RETCODE_DONE:
                return {
                    'success': False,
                    'error': f'Order failed with retcode: {getattr(result, "retcode", None)}',
                    'result': getattr(result, '_asdict', lambda: None)(),
                    'latency_ms': latency_ms,
                }

            logger.info(f"Order placed successfully: {result.order} ({latency_ms:.0f} ms)")

            return {
                'success': True,
                'order_id': result.order,
                'volume': result.volume,
                'price': result.price,
                'symbol': symbol,
                'type': order_type,
                'timestamp': datetime.now(),
                'latency_ms': latency_ms,
            }
            
        except Exception as e:
            logger.error(f"Error placing order: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions"""
        try:
            positions = mt5.positions_get()
            
            if positions is None:
                return []
            
            return [
                {
                    'ticket': pos.ticket,
                    'symbol': pos.symbol,
                    'type': 'BUY' if pos.type == mt5.ORDER_TYPE_BUY else 'SELL',
                    'volume': pos.volume,
                    'price_open': pos.price_open,
                    'price_current': pos.price_current,
                    'profit': pos.profit,
                    'time': datetime.fromtimestamp(pos.time)
                }
                for pos in positions
            ]
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    def close_position(self, ticket: int) -> bool:
        """Close a specific position"""
        try:
            position = mt5.positions_get(ticket=ticket)
            
            if position is None or len(position) == 0:
                logger.error(f"Position {ticket} not found")
                return False
            
            position = position[0]
            
            # Determine close type (opposite of open)
            if position.type == mt5.ORDER_TYPE_BUY:
                order_type = mt5.ORDER_TYPE_SELL
                tick = mt5.symbol_info_tick(position.symbol)
                if tick is None:
                    logger.error(f"Failed to get tick for {position.symbol}: {mt5.last_error()}")
                    return False
                price = tick.bid
            else:
                order_type = mt5.ORDER_TYPE_BUY
                tick = mt5.symbol_info_tick(position.symbol)
                if tick is None:
                    logger.error(f"Failed to get tick for {position.symbol}: {mt5.last_error()}")
                    return False
                price = tick.ask
            
            # Prepare close request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "volume": position.volume,
                "type": order_type,
                "position": ticket,
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": "Close by bot",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)

            if result is None:
                logger.error(f"Order send returned None when closing position {ticket}")
                return False

            if not hasattr(result, 'retcode'):
                logger.error(f"Order send returned unexpected result when closing position {ticket}: {result}")
                return False

            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"Position {ticket} closed successfully")
                return True
            else:
                logger.error(f"Failed to close position {ticket}: {result.retcode} - {getattr(result, '_asdict', lambda: None)()}" )
                return False
                
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return False
    
    def close_all_positions(self):
        """Close all open positions"""
        positions = self.get_open_positions()
        attempted = len(positions)
        succeeded = 0
        failed = []

        for position in positions:
            try:
                ok = self.close_position(position['ticket'])
                if ok:
                    succeeded += 1
                else:
                    failed.append(position['ticket'])
            except Exception as e:
                logger.error(f"Exception closing position {position['ticket']}: {e}")
                failed.append(position['ticket'])

        logger.info(f"Close positions summary: attempted={attempted}, succeeded={succeeded}, failed={len(failed)}")
        if failed:
            logger.info(f"Failed tickets: {failed}")
