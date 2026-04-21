#!/usr/bin/env python3
"""
Offline backtest runner — validates the PPO model against historical OHLCV data.

Usage:
    python -m bot.backtest --csv data/EURUSD_M5.csv --model data/models/trading_model.zip
    python -m bot.backtest --csv data/EURUSD_M5.csv  # model path from MODEL_PATH env var

CSV must have columns: time, open, high, low, close, tick_volume
"""

import argparse
import os
import sys
import math
import logging
from typing import List

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def _load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=['time'])
    required = {'open', 'high', 'low', 'close', 'tick_volume'}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing columns: {missing}")
    return df.sort_values('time').reset_index(drop=True)


def _sharpe(daily_returns: List[float]) -> float:
    if len(daily_returns) < 2:
        return 0.0
    mean = sum(daily_returns) / len(daily_returns)
    std = (sum((x - mean) ** 2 for x in daily_returns) / len(daily_returns)) ** 0.5
    return (mean / std) * math.sqrt(252) if std > 0 else 0.0


def _max_drawdown(equity_curve: List[float]) -> float:
    peak = equity_curve[0]
    max_dd = 0.0
    for v in equity_curve:
        peak = max(peak, v)
        dd = (peak - v) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
    return max_dd


def run_backtest(csv_path: str, model_path: str, initial_balance: float = 10_000.0) -> dict:
    from stable_baselines3 import PPO
    from bot.ml_agent import TradingEnvironment

    logger.info(f"Loading data from {csv_path}")
    df = _load_csv(csv_path)
    logger.info(f"Loaded {len(df)} bars")

    logger.info(f"Loading model from {model_path}")
    model = PPO.load(model_path)

    env = TradingEnvironment(df, initial_balance=initial_balance)
    obs, _ = env.reset()

    equity_curve = [initial_balance]
    trade_profits: List[float] = []
    step = 0

    while True:
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, done, truncated, info = env.step(int(action))
        equity_curve.append(info['balance'])

        # Record completed trade reward as a proxy for profit
        if reward != 0 and reward != -0.001:
            trade_profits.append(reward)

        step += 1
        if done or truncated:
            break

    final_balance = equity_curve[-1]
    total_return = (final_balance - initial_balance) / initial_balance

    # Daily P&L from equity curve (1 bar = 5 min → ~288 bars/day)
    bars_per_day = 288
    daily_returns = []
    for i in range(bars_per_day, len(equity_curve), bars_per_day):
        prev = equity_curve[i - bars_per_day]
        curr = equity_curve[i]
        if prev > 0:
            daily_returns.append((curr - prev) / prev)

    winning = [p for p in trade_profits if p > 0]
    losing  = [p for p in trade_profits if p < 0]
    win_rate = len(winning) / len(trade_profits) if trade_profits else 0.0
    profit_factor = (
        sum(winning) / abs(sum(losing))
        if losing and sum(winning) > 0
        else float('inf') if winning else 0.0
    )

    results = {
        'bars':           step,
        'initial_balance': initial_balance,
        'final_balance':  final_balance,
        'total_return':   total_return,
        'sharpe_ratio':   _sharpe(daily_returns),
        'max_drawdown':   _max_drawdown(equity_curve),
        'total_trades':   len(trade_profits),
        'win_rate':       win_rate,
        'profit_factor':  profit_factor,
    }
    return results


def _print_results(r: dict) -> None:
    print("\n" + "=" * 50)
    print("BACKTEST RESULTS")
    print("=" * 50)
    print(f"  Bars evaluated:   {r['bars']:,}")
    print(f"  Initial balance:  ${r['initial_balance']:,.2f}")
    print(f"  Final balance:    ${r['final_balance']:,.2f}")
    print(f"  Total return:     {r['total_return']:+.2%}")
    print(f"  Sharpe ratio:     {r['sharpe_ratio']:.3f}")
    print(f"  Max drawdown:     {r['max_drawdown']:.2%}")
    print(f"  Total trades:     {r['total_trades']}")
    print(f"  Win rate:         {r['win_rate']:.1%}")
    print(f"  Profit factor:    {r['profit_factor']:.2f}")
    print("=" * 50)


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline PPO backtest runner")
    parser.add_argument('--csv',     required=True, help="Path to OHLCV CSV file")
    parser.add_argument('--model',   default=os.environ.get('MODEL_PATH', '/app/models/trading_model.zip'),
                        help="Path to PPO model .zip (default: $MODEL_PATH)")
    parser.add_argument('--balance', type=float, default=10_000.0,
                        help="Starting balance (default: 10000)")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        logger.error(f"CSV not found: {args.csv}")
        sys.exit(1)
    if not os.path.exists(args.model):
        logger.error(f"Model not found: {args.model}")
        sys.exit(1)

    results = run_backtest(args.csv, args.model, args.balance)
    _print_results(results)

    # Non-zero exit if Sharpe < 0 or max drawdown > 30% (fail CI gate if wired up)
    if results['sharpe_ratio'] < 0 or results['max_drawdown'] > 0.30:
        logger.warning("Backtest failed quality gate (Sharpe < 0 or drawdown > 30%)")
        sys.exit(2)


if __name__ == '__main__':
    main()
