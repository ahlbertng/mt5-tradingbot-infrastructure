"""
AWS Integration - Handles all AWS services interactions
"""

import boto3
import botocore.exceptions
import json
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class AWSIntegration:
    """Handles AWS services integration"""
    
    def __init__(self):
        """Initialize AWS clients"""
        self.region = os.getenv('AWS_REGION', 'us-east-1')
        
        # Initialize AWS clients
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.secrets_client = boto3.client('secretsmanager', region_name=self.region)
        self.sns_client = boto3.client('sns', region_name=self.region)
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=self.region)
        
        # Get configuration from environment
        self.s3_bucket = os.getenv('S3_BUCKET', '')
        self.secret_arn = os.getenv('SECRET_ARN', '')
        self.sns_topic_arn = self._get_sns_topic_arn()
        
        logger.info("AWS integration initialized")
    
    def _get_sns_topic_arn(self) -> str:
        """Get SNS topic ARN from env var or by listing topics."""
        arn = os.getenv('SNS_TOPIC_ARN', '')
        if arn:
            return arn
        try:
            token = None
            while True:
                if token:
                    response = self.sns_client.list_topics(NextToken=token)
                else:
                    response = self.sns_client.list_topics()

                for topic in response.get('Topics', []):
                    if 'mt5-trading-alerts' in topic.get('TopicArn', ''):
                        return topic['TopicArn']

                token = response.get('NextToken')
                if not token:
                    break

            return ''

        except Exception as e:
            logger.error(f"Error getting SNS topic ARN: {e}")
            return ''
    
    def get_mt5_credentials(self) -> Dict[str, str]:
        """Get MT5 credentials from Secrets Manager"""
        try:
            if not self.secret_arn:
                logger.warning("No secret ARN configured")
                return {}
            
            response = self.secrets_client.get_secret_value(SecretId=self.secret_arn)
            
            secret_string = response['SecretString']
            credentials = json.loads(secret_string)
            
            logger.info("MT5 credentials retrieved from Secrets Manager")
            return credentials
            
        except Exception as e:
            logger.error(f"Error getting MT5 credentials: {e}")
            return {}
    
    # S3 key layout:
    #   models/ppo/v{timestamp}/model.zip  — versioned checkpoint
    #   models/latest/model.zip            — pointer updated on every successful upload

    def upload_model(self, local_path: str) -> bool:
        """Upload ML model to S3 under a versioned key, then update the latest pointer."""
        try:
            if not self.s3_bucket:
                logger.warning("No S3 bucket configured")
                return False

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            versioned_key = f"models/ppo/v{timestamp}/model.zip"
            latest_key = "models/latest/model.zip"

            self.s3_client.upload_file(local_path, self.s3_bucket, versioned_key)
            self.s3_client.upload_file(local_path, self.s3_bucket, latest_key)

            logger.info(f"Model uploaded to S3: s3://{self.s3_bucket}/{versioned_key}")
            return True

        except Exception as e:
            logger.error(f"Error uploading model to S3: {e}")
            return False

    def download_model(self, local_path: str) -> bool:
        """Download the latest ML model from S3. Returns False (not an error) if none exists yet."""
        try:
            if not self.s3_bucket:
                logger.warning("No S3 bucket configured")
                return False

            latest_key = "models/latest/model.zip"

            dirpath = os.path.dirname(local_path)
            if dirpath:
                os.makedirs(dirpath, exist_ok=True)

            try:
                self.s3_client.download_file(self.s3_bucket, latest_key, local_path)
            except botocore.exceptions.ClientError as e:
                if e.response['Error']['Code'] in ('404', 'NoSuchKey'):
                    logger.info("No model found in S3 yet — starting without a pre-trained model")
                    return False
                raise

            logger.info(f"Model downloaded from S3: s3://{self.s3_bucket}/{latest_key}")
            return True

        except Exception as e:
            logger.error(f"Error downloading model from S3: {e}")
            return False
    
    def send_alert(self, subject: str, message: str) -> bool:
        """Send alert via SNS"""
        try:
            if not self.sns_topic_arn:
                logger.warning("No SNS topic ARN configured")
                return False
            
            # Publish message
            response = self.sns_client.publish(
                TopicArn=self.sns_topic_arn,
                Subject=subject,
                Message=message
            )
            
            logger.info(f"Alert sent via SNS: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending SNS alert: {e}")
            return False
    
    def publish_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = 'None'
    ) -> bool:
        """Publish custom metric to CloudWatch"""
        try:
            response = self.cloudwatch_client.put_metric_data(
                Namespace='MT5TradingBot',
                MetricData=[
                    {
                        'MetricName': metric_name,
                        'Value': value,
                        'Unit': unit,
                        'Timestamp': datetime.now(timezone.utc)
                    }
                ]
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error publishing metric to CloudWatch: {e}")
            return False
    
    def publish_metrics(self, metrics: list) -> bool:
        """Publish multiple metrics to CloudWatch in a single API call.

        Each entry: {'name': str, 'value': float, 'unit': str (optional)}
        """
        try:
            now = datetime.now(timezone.utc)
            metric_data = [
                {
                    'MetricName': m['name'],
                    'Value': float(m['value']),
                    'Unit': m.get('unit', 'None'),
                    'Timestamp': now,
                }
                for m in metrics
            ]
            self.cloudwatch_client.put_metric_data(
                Namespace='MT5TradingBot',
                MetricData=metric_data,
            )
            return True
        except Exception as e:
            logger.error(f"Error publishing metrics to CloudWatch: {e}")
            return False

    def upload_logs(self, log_file: str) -> bool:
        """Upload log file to S3"""
        try:
            if not self.s3_bucket:
                return False
            
            timestamp = datetime.now().strftime('%Y%m%d')
            s3_key = f"logs/trading_bot_{timestamp}.log"
            
            self.s3_client.upload_file(
                log_file,
                self.s3_bucket,
                s3_key
            )
            
            logger.info(f"Logs uploaded to S3: s3://{self.s3_bucket}/{s3_key}")
            return True
            
        except Exception as e:
            logger.error(f"Error uploading logs to S3: {e}")
            return False
    
    def backup_database(self, backup_file: str) -> bool:
        """Upload database backup to S3"""
        try:
            if not self.s3_bucket:
                return False
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            s3_key = f"backups/db_backup_{timestamp}.sql"
            
            self.s3_client.upload_file(
                backup_file,
                self.s3_bucket,
                s3_key
            )
            
            logger.info(f"Database backup uploaded to S3: s3://{self.s3_bucket}/{s3_key}")
            return True
            
        except Exception as e:
            logger.error(f"Error uploading database backup to S3: {e}")
            return False
