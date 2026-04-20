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
  threshold           = "9000"  # Alert if balance drops below $9,000 (10% loss)
  alarm_description   = "Alert when account balance is low"
  alarm_actions       = [aws_sns_topic.trading_alerts.arn]
  treat_missing_data  = "notBreaching"
}

# Alarm: High Daily Loss
resource "aws_cloudwatch_metric_alarm" "high_daily_loss" {
  alarm_name          = "mt5-trading-bot-high-daily-loss"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "DailyPnL"
  namespace           = "MT5TradingBot"
  # Aggregate over a full UTC day to detect daily loss totals reliably
  period              = "86400"
  statistic           = "Sum"
  threshold           = "-400"  # Alert if daily loss exceeds $400 (4% of $10k)
  alarm_description   = "Alert when daily loss is too high"
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
  period              = "900"  # 15 minutes
  statistic           = "SampleCount"
  threshold           = "1"
  alarm_description   = "Alert when bot stops sending metrics"
  alarm_actions       = [aws_sns_topic.trading_alerts.arn]
  # If metrics stop arriving, treat the missing data as breaching so the alarm
  # fires and indicates the bot or agent is not reporting.
  treat_missing_data  = "breaching"
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
  threshold           = "2000000000"  # 2GB
  alarm_description   = "Alert when RDS storage is low"
  alarm_actions       = [aws_sns_topic.trading_alerts.arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.trading_db.id
  }
}

# EC2 status check alarm removed: bot runs on Oracle Cloud VM, not EC2.
# Bot liveness is covered by the no_metrics alarm above.
