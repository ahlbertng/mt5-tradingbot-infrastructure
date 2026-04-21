# CloudWatch Alarms for MT5 Trading Bot

# EC2 CPU alarm removed: bot runs on Oracle Cloud VM, not EC2.
# CPU monitoring is handled by the CloudWatch agent pushing custom metrics.

# Alarm: Low Account Balance
resource "aws_cloudwatch_metric_alarm" "low_balance" {
  alarm_name          = "mt5-trading-bot-low-balance"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "AccountBalance"
  namespace           = "MT5TradingBot"
  period              = "300"
  statistic           = "Average"
  threshold           = "9000" # Alert if balance drops below $9,000 (10% loss)
  alarm_description   = "Alert when account balance is low"
  alarm_actions       = [aws_sns_topic.trading_alerts.arn]
  treat_missing_data  = "notBreaching"
}

# Alarm: High Daily Loss
# Period 300s so the alarm fires within ~5 minutes of a loss breach (SLO: alert within 60s
# is aspirational; 5 min is the CloudWatch minimum viable window for this metric frequency).
resource "aws_cloudwatch_metric_alarm" "high_daily_loss" {
  alarm_name          = "mt5-trading-bot-high-daily-loss"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "DailyPnL"
  namespace           = "MT5TradingBot"
  period              = "300"
  statistic           = "Average"
  threshold           = "-400"
  alarm_description   = "Daily loss exceeded $400 (4% of $10k account)"
  alarm_actions       = [aws_sns_topic.trading_alerts.arn]
  treat_missing_data  = "notBreaching"
}

# Alarm: No Metrics Received (Bot Down)
resource "aws_cloudwatch_metric_alarm" "no_metrics" {
  alarm_name          = "mt5-trading-bot-no-metrics"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "AccountBalance"
  namespace           = "MT5TradingBot"
  period              = "900" # 15 minutes
  statistic           = "SampleCount"
  threshold           = "1"
  alarm_description   = "Alert when bot stops sending metrics"
  alarm_actions       = [aws_sns_topic.trading_alerts.arn]
  # If metrics stop arriving, treat the missing data as breaching so the alarm
  # fires and indicates the bot or agent is not reporting.
  treat_missing_data = "breaching"
}

# Alarm: RDS High CPU
resource "aws_cloudwatch_metric_alarm" "rds_high_cpu" {
  alarm_name          = "mt5-rds-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "Alert when RDS CPU is high"
  alarm_actions       = [aws_sns_topic.trading_alerts.arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.trading_db.id
  }
}

# Alarm: RDS Low Storage
resource "aws_cloudwatch_metric_alarm" "rds_low_storage" {
  alarm_name          = "mt5-rds-low-storage"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "2000000000" # 2GB
  alarm_description   = "Alert when RDS storage is low"
  alarm_actions       = [aws_sns_topic.trading_alerts.arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.trading_db.id
  }
}

# EC2 status check alarm removed: bot runs on Oracle Cloud VM, not EC2.
# Bot liveness is covered by the no_metrics alarm above.

# Alarm: No Trades in 6 Hours
# The bot publishes a TradesExecuted count metric to the MT5TradingBot namespace
# (see bot/main.py and bot/aws_integration.py). If the sum of TradesExecuted
# over a 6-hour window is 0 (or missing), fire an alert. Missing data is
# treated as breaching so a silent bot / agent outage also triggers the alarm.
resource "aws_cloudwatch_metric_alarm" "no_trades_6h" {
  alarm_name          = "mt5-trading-bot-no-trades-6h"
  comparison_operator = "LessThanOrEqualToThreshold"
  evaluation_periods  = "1"
  metric_name         = "TradesExecuted"
  namespace           = "MT5TradingBot"
  period              = "21600"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "No trades executed in the last 6 hours"
  alarm_actions       = [aws_sns_topic.trading_alerts.arn]
  treat_missing_data  = "breaching"
}

# Alarm: Order Placement Latency SLO breach (> 2 seconds)
resource "aws_cloudwatch_metric_alarm" "order_latency_high" {
  alarm_name          = "mt5-trading-bot-order-latency-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "3"
  metric_name         = "OrderLatencyMs"
  namespace           = "MT5TradingBot"
  period              = "60"
  statistic           = "p99"
  threshold           = "2000"
  alarm_description   = "p99 order placement latency exceeded 2000 ms (SLO breach)"
  alarm_actions       = [aws_sns_topic.trading_alerts.arn]
  treat_missing_data  = "notBreaching"
}

# Alarm: Negative Sharpe Ratio (strategy losing edge)
resource "aws_cloudwatch_metric_alarm" "negative_sharpe" {
  alarm_name          = "mt5-trading-bot-negative-sharpe"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "SharpeRatio"
  namespace           = "MT5TradingBot"
  period              = "3600"
  statistic           = "Average"
  threshold           = "0"
  alarm_description   = "Annualised Sharpe ratio is negative for 2 consecutive hours — strategy may have lost edge"
  alarm_actions       = [aws_sns_topic.trading_alerts.arn]
  treat_missing_data  = "notBreaching"
}
