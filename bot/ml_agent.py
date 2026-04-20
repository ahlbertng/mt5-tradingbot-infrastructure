"""
ML Agent - Reinforcement Learning agent for trading decisions
Uses Stable-Baselines3 with PPO algorithm
"""

import numpy as np
import pandas as pd
import logging
import gymnasium as gym
from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from typing import Dict, Any, Optional
import os

logger = logging.getLogger(__name__)


class TradingEnvironment(gym.Env):
    """Custom trading environment for RL agent"""
    
    def __init__(self, df: pd.DataFrame, initial_balance: float = 10000):
        """Initialize trading environment"""
        super(TradingEnvironment, self).__init__()
        
        self.df = df.reset_index(drop=True)
        self.initial_balance = initial_balance
        self.current_step = 0
        
        # Action space: 0 = Hold, 1 = Buy, 2 = Sell, 3 = Close
        self.action_space = spaces.Discrete(4)
        
        # Observation space: OHLCV + technical indicators + account state
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(10,),  # Features count
            dtype=np.float32
        )
        
        self.reset()
    
    def reset(self, seed=None, options=None):
        """Reset environment to initial state"""
        super().reset(seed=seed)
        
        self.current_step = 40  # Start after enough data for indicators
        self.balance = self.initial_balance
        self.position = 0  # 0 = no position, 1 = long, -1 = short
        self.entry_price = 0
        self.total_profit = 0
        self.trades_made = 0
        
        return self._get_observation(), {}
    
    def _get_observation(self) -> np.ndarray:
        """Get current observation (state)"""
        if self.current_step >= len(self.df):
            self.current_step = len(self.df) - 1
        
        row = self.df.iloc[self.current_step]
        
        # Calculate simple technical indicators using consistent z-score normalization
        window_start = max(0, self.current_step - 20)
        window = self.df['close'].iloc[window_start:self.current_step+1]

        sma_20 = window.mean() if len(window) > 0 else row['close']
        std_20 = window.std(ddof=0) if len(window) > 1 else 0.0

        def z(val, mean, std):
            return (val - mean) / std if std and std > 0 else 0.0

        price_close_z = z(row['close'], sma_20, std_20)
        price_open_z = z(row['open'], sma_20, std_20)
        price_high_z = z(row['high'], sma_20, std_20)
        price_low_z = z(row['low'], sma_20, std_20)

        # Volatility as z-score of recent std
        volatility = z(window.std(ddof=0) if len(window) > 1 else 0.0, sma_20, std_20)

        # Price change (relative) -- keep as ratio
        if self.current_step > 0:
            prev_close = self.df.iloc[self.current_step-1]['close']
            price_change = (row['close'] - prev_close) / prev_close if prev_close != 0 else 0.0
        else:
            price_change = 0.0

        # Normalize volume by z-score of recent volumes
        vol_window = self.df['tick_volume'].iloc[window_start:self.current_step+1]
        vol_mean = vol_window.mean() if len(vol_window) > 0 else 0.0
        vol_std = vol_window.std(ddof=0) if len(vol_window) > 1 else 0.0
        volume_z = z(row.get('tick_volume', 0), vol_mean, vol_std)

        obs = np.array([
            price_close_z,
            price_open_z,
            price_high_z,
            price_low_z,
            volume_z,
            price_close_z,  # price_to_sma-like feature
            volatility,
            price_change,
            float(self.position),  # Current position
            self.balance / self.initial_balance  # Normalized balance
        ], dtype=np.float32)
        
        return obs
    
    def step(self, action: int):
        """Execute action and return result"""
        # Use current step price for actions; ensure index in bounds
        if self.current_step >= len(self.df):
            self.current_step = len(self.df) - 1
        current_price = self.df.iloc[self.current_step]['close']
        reward = 0
        done = False
        
        # Execute action
        if action == 1 and self.position == 0:  # Buy
            self.position = 1
            self.entry_price = current_price
            self.trades_made += 1
            reward = -0.001  # Small penalty for trading costs
            
        elif action == 2 and self.position == 0:  # Sell
            self.position = -1
            self.entry_price = current_price
            self.trades_made += 1
            reward = -0.001  # Small penalty for trading costs
        elif action == 3 and self.position != 0:  # Close position (explicit)
            if self.position == 1:  # Close long
                profit = (current_price - self.entry_price) / self.entry_price
            else:  # Close short
                profit = (self.entry_price - current_price) / self.entry_price

            self.balance += self.balance * profit
            self.total_profit += profit
            reward = profit * 100  # Scale reward

            self.position = 0
            self.entry_price = 0
        
        # Move to next step
        self.current_step += 1
        
        # Check if episode is done
        if self.current_step >= len(self.df) - 1:
            done = True

            # Close any open position at the end using the final available price
            if self.position != 0:
                final_idx = min(self.current_step, len(self.df) - 1)
                final_price = self.df.iloc[final_idx]['close']
                if self.position == 1:
                    profit = (final_price - self.entry_price) / self.entry_price
                else:
                    profit = (self.entry_price - final_price) / self.entry_price

                self.balance += self.balance * profit
                reward += profit * 100
        
        # Penalize if balance drops too much
        if self.balance < self.initial_balance * 0.5:
            reward -= 10
            done = True
        
        observation = self._get_observation()
        info = {
            'balance': self.balance,
            'total_profit': self.total_profit,
            'trades': self.trades_made
        }
        
        return observation, reward, done, False, info
    
    def render(self):
        """Render environment (optional)"""
        pass


class TradingAgent:
    """ML Trading Agent using PPO"""
    
    def __init__(self, db_manager=None, aws_integration=None):
        """Initialize trading agent"""
        self.db = db_manager
        self.aws = aws_integration
        self.model = None
        self.env = None
        self.is_trained = False
        
        self.model_path = os.path.join(os.environ.get("MODEL_PATH", "/app/models"), "trading_model.zip")
        
    def initialize(self):
        """Initialize or load the model"""
        try:
            # Try to load existing model
            if os.path.exists(self.model_path):
                logger.info("Loading existing model...")
                self.model = PPO.load(self.model_path)
                self.is_trained = True
                logger.info("Model loaded successfully")
            else:
                logger.info("No existing model found. Will create new model.")
                self.is_trained = False
            
        except Exception as e:
            logger.error(f"Error initializing agent: {e}")
    
    def train(self, df: pd.DataFrame, timesteps: int = 100000):
        """Train the agent on historical data"""
        try:
            logger.info(f"Training agent for {timesteps} timesteps...")
            
            # Create environment
            env = TradingEnvironment(df)
            env = DummyVecEnv([lambda: env])
            
            # Create or update model
            if self.model is None:
                self.model = PPO(
                    "MlpPolicy",
                    env,
                    verbose=1,
                    learning_rate=0.0003,
                    n_steps=2048,
                    batch_size=64,
                    n_epochs=10,
                    gamma=0.99,
                    gae_lambda=0.95,
                    clip_range=0.2,
                    ent_coef=0.01
                )
            else:
                self.model.set_env(env)
            
            # Train
            self.model.learn(total_timesteps=timesteps)
            self.is_trained = True
            
            # Save model
            self.save_model()
            
            logger.info("Training completed successfully")
            
        except Exception as e:
            logger.error(f"Error training agent: {e}", exc_info=True)
    
    def get_trading_signal(
        self,
        market_data: pd.DataFrame,
        account_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get trading signal from the agent"""
        try:
            # If not trained, train on available data first
            if not self.is_trained:
                logger.info("Agent not trained. Training on current data...")
                self.train(market_data, timesteps=50000)
            
            # Create temporary environment for prediction
            env = TradingEnvironment(market_data, initial_balance=account_info['balance'])
            obs, _ = env.reset()

            # Advance environment to latest available observation (avoid using stale reset state)
            try:
                env.current_step = max(0, len(market_data) - 1)
                obs = env._get_observation()
            except Exception:
                # fallback to reset observation
                obs, _ = env.reset()

            # Ensure model is loaded
            if self.model is None:
                logger.warning("Model not loaded, returning HOLD signal")
                return {'action': 'HOLD', 'symbol': 'EURUSD', 'confidence': 0}

            # Get action from model
            action, _states = self.model.predict(obs, deterministic=True)
            
            # Convert action to signal
            if action == 1:
                signal = {
                    'action': 'BUY',
                    'symbol': 'EURUSD',
                    'confidence': 0.7,
                    'stop_loss_pips': 20,
                    'take_profit_pips': 40
                }
            elif action == 2:
                signal = {
                    'action': 'SELL',
                    'symbol': 'EURUSD',
                    'confidence': 0.7,
                    'stop_loss_pips': 20,
                    'take_profit_pips': 40
                }
            elif action == 3:
                signal = {
                    'action': 'CLOSE',
                    'symbol': 'EURUSD',
                    'confidence': 0.9
                }
            else:
                signal = {
                    'action': 'HOLD',
                    'symbol': 'EURUSD',
                    'confidence': 0.5
                }
            
            return signal
            
        except Exception as e:
            logger.error(f"Error getting trading signal: {e}", exc_info=True)
            return {'action': 'HOLD', 'symbol': 'EURUSD', 'confidence': 0}
    
    def record_trade(self, trade_result: Dict[str, Any]):
        """Record trade result for learning"""
        # In a more advanced implementation, this would store the trade
        # for periodic retraining
        pass
    
    def save_model(self):
        """Save model to disk and S3"""
        try:
            if self.model is not None:
                # Save locally
                dirpath = os.path.dirname(self.model_path)
                if dirpath:
                    os.makedirs(dirpath, exist_ok=True)

                self.model.save(self.model_path)
                logger.info(f"Model saved to {self.model_path}")

                # Upload to S3 with error handling
                if self.aws:
                    try:
                        ok = self.aws.upload_model(self.model_path)
                        if not ok:
                            logger.warning(f"Upload to S3 reported failure for {self.model_path}")
                    except Exception as e:
                        logger.error(f"S3 upload failed for {self.model_path}: {e}")
                
        except Exception as e:
            logger.error(f"Error saving model: {e}")
    
    def load_model(self):
        """Load model from disk or S3"""
        try:
            # Try to download from S3 first
            if self.aws:
                try:
                    ok = self.aws.download_model(self.model_path)
                    if not ok:
                        logger.warning(f"S3 download did not succeed, will try local file: {self.model_path}")
                except Exception as e:
                    logger.error(f"Error downloading model from S3: {e}")
            
            # Load model
            if os.path.exists(self.model_path):
                self.model = PPO.load(self.model_path)
                self.is_trained = True
                logger.info("Model loaded successfully")
                return True
            else:
                logger.warning("No model file found")
                return False
                
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False
