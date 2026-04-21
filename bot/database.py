"""
Database Manager - Handles all database operations
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages PostgreSQL database connections and operations"""
    
    def __init__(self):
        """Initialize database manager"""
        self.conn = None
        # per-method cursors will be used instead of a shared cursor
        
        # Get database credentials from environment
        self.db_endpoint = os.getenv('DB_ENDPOINT', 'localhost')
        self.db_name = os.getenv('DB_NAME', 'trading_db')
        self.db_username = os.getenv('DB_USERNAME', 'trading_admin')
        self.db_password = os.getenv('DB_PASSWORD', '')
        self.db_connect_timeout = int(os.getenv('DB_CONNECT_TIMEOUT', '10'))
        
        # Parse endpoint to get host and port safely (handle IPv6 bracketed addresses)
        try:
            endpoint = self.db_endpoint.strip()
            if endpoint.startswith('['):
                # IPv6 like [::1]:5432 or [::1]
                end_bracket = endpoint.find(']')
                if end_bracket == -1:
                    raise ValueError('Invalid IPv6 endpoint')
                host_part = endpoint[1:end_bracket]
                rest = endpoint[end_bracket+1:]
                if rest.startswith(':'):
                    port_part = rest[1:]
                else:
                    port_part = ''
            else:
                # Split on last colon to avoid splitting IPv6 plain addresses
                host_part, sep, port_part = endpoint.rpartition(':')
                if sep == '':
                    host_part = endpoint
                    port_part = ''

            self.db_host = host_part or 'localhost'
            try:
                self.db_port = int(port_part) if port_part else 5432
            except Exception:
                logger.warning(f"Invalid DB port '{port_part}', defaulting to 5432")
                self.db_port = 5432
        except Exception as e:
            logger.error(f"Error parsing DB_ENDPOINT '{self.db_endpoint}': {e}")
            self.db_host = 'localhost'
            self.db_port = 5432
    
    def connect(self) -> bool:
        """Connect to PostgreSQL database"""
        try:
            self.conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_username,
                password=self.db_password,
                connect_timeout=self.db_connect_timeout,
            )
            logger.info(f"Connected to database: {self.db_name}@{self.db_host}")
            self._create_tables()
            return True

        except Exception as e:
            logger.error(f"Error connecting to database: {e}", exc_info=True)
            self.conn = None
            return False

    def _ensure_connected(self) -> bool:
        """Return True if the connection is alive, reconnect if not."""
        if self.conn is not None and self.conn.closed == 0:
            return True
        logger.warning("Database connection unavailable, reconnecting...")
        return self.connect()
    
    def disconnect(self):
        """Disconnect from database"""
        # No persistent cursor to close
        if self.conn:
            self.conn.close()
        
        logger.info("Disconnected from database")
    
    def _create_tables(self):
        """Create necessary database tables"""
        try:
            with self.conn.cursor() as cur:
                # Trades table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS trades (
                        id SERIAL PRIMARY KEY,
                        order_id BIGINT UNIQUE,
                        symbol VARCHAR(20),
                        order_type VARCHAR(10),
                        volume DECIMAL(10, 2),
                        open_price DECIMAL(10, 5),
                        close_price DECIMAL(10, 5),
                        stop_loss DECIMAL(10, 5),
                        take_profit DECIMAL(10, 5),
                        profit DECIMAL(10, 2),
                        open_time TIMESTAMP,
                        close_time TIMESTAMP,
                        status VARCHAR(20),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Account metrics table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS account_metrics (
                        id SERIAL PRIMARY KEY,
                        balance DECIMAL(10, 2),
                        equity DECIMAL(10, 2),
                        profit DECIMAL(10, 2),
                        margin DECIMAL(10, 2),
                        margin_free DECIMAL(10, 2),
                        margin_level DECIMAL(10, 2),
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # ML training history table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS training_history (
                        id SERIAL PRIMARY KEY,
                        model_version VARCHAR(50),
                        training_timesteps INTEGER,
                        final_reward DECIMAL(10, 4),
                        training_duration_seconds INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Market data cache table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS market_data_cache (
                        id SERIAL PRIMARY KEY,
                        symbol VARCHAR(20),
                        timeframe VARCHAR(10),
                        timestamp TIMESTAMP,
                        open DECIMAL(10, 5),
                        high DECIMAL(10, 5),
                        low DECIMAL(10, 5),
                        close DECIMAL(10, 5),
                        volume BIGINT,
                        UNIQUE(symbol, timeframe, timestamp)
                    )
                """)

                # Create indexes
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_trades_symbol 
                    ON trades(symbol)
                """)

                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_trades_open_time 
                    ON trades(open_time)
                """)

                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_account_metrics_timestamp 
                    ON account_metrics(timestamp)
                """)

            self.conn.commit()
            logger.info("Database tables created/verified successfully")
            
        except Exception as e:
            logger.error(f"Error creating tables: {e}", exc_info=True)
            self.conn.rollback()
    
    def log_trade(self, trade: Dict[str, Any]) -> bool:
        """Log a trade to the database"""
        if not self._ensure_connected():
            return False
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trades (
                        order_id, symbol, order_type, volume, open_price,
                        stop_loss, take_profit, open_time, status
                    ) VALUES (
                        %(order_id)s, %(symbol)s, %(type)s, %(volume)s, %(price)s,
                        %(stop_loss)s, %(take_profit)s, %(timestamp)s, 'OPEN'
                    )
                    ON CONFLICT (order_id) DO NOTHING
                    """,
                    {
                        'order_id': trade.get('order_id'),
                        'symbol': trade.get('symbol'),
                        'type': trade.get('type'),
                        'volume': trade.get('volume'),
                        'price': trade.get('price'),
                        'stop_loss': trade.get('stop_loss'),
                        'take_profit': trade.get('take_profit'),
                        'timestamp': trade.get('timestamp', datetime.now())
                    }
                )

                if cur.rowcount == 0:
                    logger.warning(f"Duplicate trade not logged: {trade.get('order_id')}")
                    self.conn.rollback()
                    return False

            self.conn.commit()
            logger.info(f"Trade logged: {trade.get('order_id')}")
            return True
            
        except Exception as e:
            logger.error(f"Error logging trade: {e}", exc_info=True)
            self.conn.rollback()
            return False
    
    def update_trade(self, order_id: int, close_price: float, profit: float, close_time: datetime) -> bool:
        """Update a trade with close information"""
        if not self._ensure_connected():
            return False
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE trades
                    SET close_price = %s, profit = %s, close_time = %s, status = 'CLOSED'
                    WHERE order_id = %s
                    """,
                    (close_price, profit, close_time, order_id)
                )

                if cur.rowcount == 0:
                    logger.warning(f"No trade updated (order_id not found): {order_id}")
                    self.conn.rollback()
                    return False

            self.conn.commit()
            logger.info(f"Trade updated: {order_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating trade: {e}", exc_info=True)
            self.conn.rollback()
            return False
    
    def log_account_metrics(self, metrics: Dict[str, Any]) -> bool:
        """Log account metrics"""
        if not self._ensure_connected():
            return False
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO account_metrics (
                        balance, equity, profit, margin, margin_free, margin_level
                    ) VALUES (
                        %(balance)s, %(equity)s, %(profit)s, 
                        %(margin)s, %(margin_free)s, %(margin_level)s
                    )
                """, metrics)

            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error logging metrics: {e}", exc_info=True)
            self.conn.rollback()
            return False
    
    def get_trade_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get trading statistics for the specified period"""
        if not self._ensure_connected():
            return {}
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as winning_trades,
                        SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losing_trades,
                        SUM(profit) as total_profit,
                        AVG(profit) as avg_profit,
                        MAX(profit) as max_profit,
                        MIN(profit) as min_profit
                    FROM trades
                    WHERE close_time >= NOW() - (%s::int * INTERVAL '1 day')
                    AND status = 'CLOSED'
                """, (days,))

                result = cur.fetchone()
                return dict(result) if result else {}
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}
    
    def get_recent_trades(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent trades"""
        if not self._ensure_connected():
            return []
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM trades
                    ORDER BY open_time DESC
                    LIMIT %s
                """, (limit,))

                return [dict(row) for row in cur.fetchall()]
            
        except Exception as e:
            logger.error(f"Error getting recent trades: {e}")
            return []
    
    def get_daily_pnl_history(self, days: int = 30) -> List[float]:
        """Return list of daily total P&L values (one per trading day) for the last N days."""
        if not self._ensure_connected():
            return []
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT SUM(profit)
                    FROM trades
                    WHERE close_time >= NOW() - (%s::int * INTERVAL '1 day')
                      AND status = 'CLOSED'
                      AND profit IS NOT NULL
                    GROUP BY DATE(close_time)
                    ORDER BY DATE(close_time)
                """, (days,))
                return [float(row[0]) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error getting daily P&L history: {e}")
            return []

    def cache_market_data(self, symbol: str, timeframe: str, data: List[Dict[str, Any]]) -> bool:
        """Cache market data to database"""
        if not self._ensure_connected():
            return False
        try:
            with self.conn.cursor() as cur:
                for bar in data:
                    cur.execute("""
                        INSERT INTO market_data_cache (
                            symbol, timeframe, timestamp, open, high, low, close, volume
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (symbol, timeframe, timestamp) DO UPDATE
                        SET open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume
                    """, (
                        symbol, timeframe, bar['timestamp'],
                        bar['open'], bar['high'], bar['low'], bar['close'], bar['volume']
                    ))

            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error caching market data: {e}")
            self.conn.rollback()
            return False
