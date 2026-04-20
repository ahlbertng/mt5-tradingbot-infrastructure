#!/usr/bin/env python3
"""
Monitoring Script - Check bot health and performance
Run this manually or via cron for additional monitoring
"""

import boto3
import psycopg2
import os
from datetime import datetime, timedelta
import json

def check_ec2_status():
    """Check if EC2 instance is running"""
    ec2 = boto3.client('ec2')
    
    # Get instance by tag
    response = ec2.describe_instances(
        Filters=[
            {'Name': 'tag:Name', 'Values': ['mt5-trading-bot']},
            {'Name': 'instance-state-name', 'Values': ['running']}
        ]
    )
    
    if response['Reservations']:
        instance = response['Reservations'][0]['Instances'][0]
        print(f"✅ EC2 Instance Running: {instance['InstanceId']}")
        print(f"   Public IP: {instance.get('PublicIpAddress', 'N/A')}")
        return True
    else:
        print("❌ EC2 Instance NOT running")
        return False

def check_rds_status():
    """Check if RDS database is available"""
    rds = boto3.client('rds')
    
    try:
        response = rds.describe_db_instances(
            DBInstanceIdentifier='mt5-trading-db'
        )
        
        if response['DBInstances']:
            db = response['DBInstances'][0]
            status = db['DBInstanceStatus']
            
            if status == 'available':
                print(f"✅ RDS Database Available")
                print(f"   Endpoint: {db['Endpoint']['Address']}")
                return True
            else:
                print(f"⚠️  RDS Database Status: {status}")
                return False
    except Exception as e:
        print(f"❌ RDS Database Error: {e}")
        return False

def get_db_connection():
    """Return a psycopg2 connection using validated DB_ENDPOINT and env vars"""
    endpoint = os.getenv('DB_ENDPOINT')
    if not endpoint:
        raise ValueError('DB_ENDPOINT is not set')

    host = endpoint.split(':')[0]
    return psycopg2.connect(
        host=host,
        port=5432,
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USERNAME'),
        password=os.getenv('DB_PASSWORD')
    )


def check_recent_trades():
    """Check if bot has made recent trades"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Check trades in last 24 hours
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM trades 
                    WHERE open_time >= NOW() - INTERVAL '24 hours'
                """)

                count = cursor.fetchone()[0]

                if count > 0:
                    print(f"✅ Recent Trades: {count} trades in last 24 hours")
                else:
                    print("⚠️  No trades in last 24 hours")

                # Get latest trade
                cursor.execute("""
                    SELECT symbol, order_type, open_time, status
                    FROM trades
                    ORDER BY open_time DESC
                    LIMIT 1
                """)

                latest = cursor.fetchone()
                if latest:
                    print(f"   Latest: {latest[0]} {latest[1]} at {latest[2]}")

        return count > 0

    except Exception as e:
        print(f"❌ Database Check Error: {e}")
        return False

def check_account_balance():
    """Check current account balance"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT balance, equity, profit, timestamp
                    FROM account_metrics
                    ORDER BY timestamp DESC
                    LIMIT 1
                """)

                result = cursor.fetchone()

                if result:
                    balance, equity, profit, timestamp = result
                    print(f"✅ Account Status (as of {timestamp}):")
                    print(f"   Balance: ${balance:,.2f}")
                    print(f"   Equity: ${equity:,.2f}")
                    print(f"   Profit: ${profit:,.2f}")

                    initial_balance = 10000
                    pnl_pct = ((balance - initial_balance) / initial_balance) * 100

                    if pnl_pct >= 0:
                        print(f"   Performance: +{pnl_pct:.2f}% 📈")
                    else:
                        print(f"   Performance: {pnl_pct:.2f}% 📉")

                    return True
                else:
                    print("⚠️  No account metrics found")
                    return False

    except Exception as e:
        print(f"❌ Account Check Error: {e}")
        return False

def check_cloudwatch_logs():
    """Check recent CloudWatch logs for errors"""
    logs = boto3.client('logs')
    
    try:
        # Query logs for errors in last hour
        query = """
        fields @timestamp, @message
        | filter @message like /ERROR/
        | sort @timestamp desc
        | limit 5
        """
        
        start_time = int((datetime.now() - timedelta(hours=1)).timestamp())
        end_time = int(datetime.now().timestamp())
        
        response = logs.start_query(
            logGroupName='/aws/ec2/mt5-trading-bot',
            startTime=start_time,
            endTime=end_time,
            queryString=query
        )
        
        query_id = response['queryId']
        
        # Wait for query to complete
        import time
        result = None
        for _ in range(10):
            result = logs.get_query_results(queryId=query_id)
            if result['status'] == 'Complete':
                break
            time.sleep(1)
        
        if result and result['results']:
            print(f"⚠️  Recent Errors Found: {len(result['results'])} errors in last hour")
            for record in result['results'][:3]:
                msg = next((item['value'] for item in record if item['field'] == '@message'), '')
                print(f"   - {msg[:100]}...")
        else:
            print("✅ No recent errors in logs")
        
    except Exception as e:
        print(f"⚠️  CloudWatch Logs Check: {e}")

def main():
    """Run all health checks"""
    print("=" * 60)
    print("MT5 Trading Bot - Health Check")
    print(f"Time: {datetime.now()}")
    print("=" * 60)
    print()
    
    checks = [
        ("EC2 Instance", check_ec2_status),
        ("RDS Database", check_rds_status),
        ("Recent Trades", check_recent_trades),
        ("Account Balance", check_account_balance),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\nChecking {name}...")
        print("-" * 40)
        result = check_func()
        results.append(result)
        print()
    
    print("\nChecking CloudWatch Logs...")
    print("-" * 40)
    check_cloudwatch_logs()
    
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Health Check Summary: {passed}/{total} checks passed")
    
    if passed == total:
        print("✅ All systems operational")
    else:
        print("⚠️  Some issues detected - review above")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
