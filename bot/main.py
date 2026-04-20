#!/usr/bin/env python3
"""
MT5 Trading Bot with Reinforcement Learning
Main entry point for the trading bot
"""

import os
import sys
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from bot.mt5_connector import MT5Connector
from bot.database import DatabaseManager
from bot.ml_agent import TradingAgent
from bot.risk_manager import RiskManager
from bot.aws_integration import AWSIntegration

# Configure logging with configurable path
LOG_PATH = os.path.join(os.environ.get("LOG_PATH", "/app/logs"), "trading_bot.log")
log_dir = os.path.dirname(LOG_PATH)
if log_dir and not os.path.exists(log_dir):
    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception:
        # If we cannot create the directory, fall back to stdout-only logging
        LOG_PATH = None

handlers = [logging.StreamHandler(sys.stdout)]
if LOG_PATH:
    handlers.insert(0, logging.FileHandler(LOG_PATH))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=handlers
)

logger = logging.getLogger(__name__)


class TradingBot:
    """Main trading bot orchestrator"""
    
    def __init__(self):
        """Initialize the trading bot"""
        logger.info("Initializing MT5 Trading Bot...")
        
        # Initialize components
        self.aws = AWSIntegration()
        self.mt5 = MT5Connector(aws_integration=self.aws)
        self.db = DatabaseManager()
        self.risk_manager = RiskManager()
        self.agent = TradingAgent(
            db_manager=self.db,
            aws_integration=self.aws
        )
        
        self.is_running = False
        self.trades_today = 0
        self.max_trades_per_day = 50
        self.current_trading_day = datetime.now().date()
        self.daily_start_equity = None
        
    def start(self):
        """Start the trading bot"""
        logger.info("Starting trading bot...")
        
        # Connect to MT5
        if not self.mt5.connect():
            logger.error("Failed to connect to MT5. Exiting.")
            return False
        
        # Connect to database
        if not self.db.connect():
            logger.error("Failed to connect to database. Exiting.")
            # Ensure MT5 is disconnected if DB connection fails
            try:
                self.mt5.disconnect()
            except Exception:
                pass
            return False
        
        # Initialize ML agent
        self.agent.initialize()
        
        self.is_running = True
        logger.info("Trading bot started successfully!")
        
        # Send startup notification
        self.aws.send_alert(
            subject="Trading Bot Started",
            message=f"MT5 Trading Bot started successfully at {datetime.now()}"
        )
        
        return True
    
    def stop(self):
        """Stop the trading bot"""
        logger.info("Stopping trading bot...")
        self.is_running = False
        
        # Close all open positions
        self.mt5.close_all_positions()
        
        # Save model
        self.agent.save_model()
        
        # Disconnect
        self.mt5.disconnect()
        self.db.disconnect()
        
        logger.info("Trading bot stopped.")
        
        # Send shutdown notification
        self.aws.send_alert(
            subject="Trading Bot Stopped",
            message=f"MT5 Trading Bot stopped at {datetime.now()}"
        )
    
    def run(self):
        """Main trading loop"""
        logger.info("Entering main trading loop...")
        
        while self.is_running:
            try:
                # Check if market is open
                if not self.mt5.is_market_open():
                    logger.info("Market is closed. Waiting...")
                    time.sleep(300)  # Wait 5 minutes
                    continue
                
                # Check daily trade limit
                if self.trades_today >= self.max_trades_per_day:
                    logger.warning("Daily trade limit reached. Waiting for next day...")
                    time.sleep(3600)  # Wait 1 hour
                    continue
                
                # Get current market data
                market_data = self.mt5.get_market_data()
                
                if market_data is None:
                    logger.warning("Failed to get market data. Retrying...")
                    time.sleep(60)
                    continue
                
                # Get account information
                account_info = self.mt5.get_account_info()

                if account_info is None:
                    logger.warning("Failed to get account info. Retrying...")
                    time.sleep(60)
                    continue

                # Reset daily counters when day rolls over
                today = datetime.now().date()
                if today != self.current_trading_day:
                    self.current_trading_day = today
                    self.trades_today = 0
                    self.daily_start_equity = account_info.get('equity')
                    self.risk_manager.reset_daily_metrics()
                    logger.info(f"New trading day {self.current_trading_day}, reset trades_today and daily_start_equity={self.daily_start_equity}")

                # Initialize daily start equity if not set
                if self.daily_start_equity is None:
                    self.daily_start_equity = account_info.get('equity')
                
                # Check risk limits
                if not self.risk_manager.check_risk_limits(account_info):
                    logger.warning("Risk limits exceeded. Pausing trading...")
                    time.sleep(300)
                    continue
                
                # Get trading signal from ML agent
                signal = self.agent.get_trading_signal(
                    market_data=market_data,
                    account_info=account_info
                )
                
                # Execute trade if signal is valid
                if signal['action'] != 'HOLD':
                    if signal['action'] == 'CLOSE':
                        # Agent requested explicit close of positions
                        logger.info("Agent requested CLOSE action: closing all positions")
                        self.mt5.close_all_positions()
                    else:
                        trade_result = self.execute_trade(signal, account_info)
                        if trade_result:
                            self.trades_today += 1
                            # Log trade to database
                            self.db.log_trade(trade_result)
                            # Provide feedback to agent for learning
                            self.agent.record_trade(trade_result)
                
                # Update metrics
                self.update_metrics(account_info)
                
                # Sleep before next iteration (adjust based on strategy)
                time.sleep(60)  # Check every minute
                
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received. Shutting down...")
                break
            
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                
                # Send error alert
                self.aws.send_alert(
                    subject="Trading Bot Error",
                    message=f"Error occurred: {str(e)}"
                )
                
                # Wait before retrying
                time.sleep(60)
        
        # Clean shutdown
        self.stop()
    
    def execute_trade(self, signal: Dict[str, Any], account_info: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a trade based on signal"""
        try:
            if account_info is None:
                logger.error("Cannot execute trade: account_info is None")
                return None

            logger.info(f"Executing trade: {signal}")
            # Calculate position size based on risk management using passed account_info
            position_size = self.risk_manager.calculate_position_size(
                account_balance=account_info.get('balance', 0),
                stop_loss_pips=signal.get('stop_loss_pips', 20)
            )

            # Place order
            result = self.mt5.place_order(
                symbol=signal['symbol'],
                order_type=signal['action'],
                volume=position_size,
                stop_loss=signal.get('stop_loss'),
                take_profit=signal.get('take_profit')
            )
            
            if result['success']:
                logger.info(f"Trade executed successfully: {result}")
                return result
            else:
                logger.error(f"Trade execution failed: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error executing trade: {e}", exc_info=True)
            return None
    
    def update_metrics(self, account_info: Dict[str, Any]):
        """Update CloudWatch metrics"""
        try:
            if account_info is None:
                logger.error("Cannot update metrics: account_info is None")
                return

            if self.daily_start_equity is None:
                self.daily_start_equity = account_info.get('equity')

            daily_pnl = account_info.get('equity', 0) - (self.daily_start_equity or 0)
            self.aws.publish_metrics([
                {'name': 'AccountBalance',  'value': account_info['balance']},
                {'name': 'AccountEquity',   'value': account_info['equity']},
                {'name': 'TradesExecuted',  'value': self.trades_today},
                {'name': 'DailyPnL',        'value': daily_pnl},
            ])

        except Exception as e:
            logger.error(f"Error updating metrics: {e}")


def main():
    """Main entry point"""
    logger.info("=" * 50)
    logger.info("MT5 TRADING BOT")
    logger.info("=" * 50)
    
    bot = TradingBot()
    
    try:
        if bot.start():
            bot.run()
        else:
            logger.error("Failed to start trading bot")
            sys.exit(1)
    
    except Exception as e:
        logger.critical(f"Critical error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
