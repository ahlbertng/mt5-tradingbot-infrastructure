terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    # Update these values with your own
    bucket = "ahlbert-tradingbot-terraform-state"
    key    = "mt5-trading-bot/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "MT5-Trading-Bot"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# VPC Configuration
resource "aws_vpc" "trading_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "mt5-trading-vpc"
  }
}

resource "aws_subnet" "public_subnet" {
  vpc_id                  = aws_vpc.trading_vpc.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = {
    Name = "mt5-trading-public-subnet"
  }
}

resource "aws_subnet" "private_subnet" {
  vpc_id            = aws_vpc.trading_vpc.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "${var.aws_region}b"

  tags = {
    Name = "mt5-trading-private-subnet"
  }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.trading_vpc.id

  tags = {
    Name = "mt5-trading-igw"
  }
}

resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.trading_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = {
    Name = "mt5-trading-public-rt"
  }
}

resource "aws_route_table_association" "public_rta" {
  subnet_id      = aws_subnet.public_subnet.id
  route_table_id = aws_route_table.public_rt.id
}



# Security Group for RDS
resource "aws_security_group" "rds_sg" {
  name        = "mt5-rds-sg"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = aws_vpc.trading_vpc.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"

# allow from Oracle VM IP only
    cidr_blocks = [
      "${var.oracle_vm_ip}/32"
    ]
    description = "PostgreSQL from Oracle VM"
  }

  tags = {
    Name = "mt5-rds-sg"
  }
}



# DynamoDB table for Terraform state locking
resource "aws_dynamodb_table" "terraform_locks" {
  name         = "terraform-locks-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = {
    Name = "terraform-locks-${var.environment}"
  }
}

# Secrets Manager secret for RDS master credentials
resource "aws_secretsmanager_secret" "rds_master" {
  name        = "mt5-rds-master-${var.environment}"
  description = "RDS master credentials for mt5-trading-db"

  tags = {
    Name = "mt5-rds-master"
  }
}

resource "aws_secretsmanager_secret_version" "rds_master_version" {
  secret_id     = aws_secretsmanager_secret.rds_master.id
  secret_string = jsonencode({
    username = var.db_username,
    password = var.db_password
  })
}

# RDS PostgreSQL
resource "aws_db_subnet_group" "trading_db_subnet" {
  name       = "mt5-trading-db-subnet"
  subnet_ids = [aws_subnet.public_subnet.id, aws_subnet.private_subnet.id]

  tags = {
    Name = "mt5-trading-db-subnet"
  }
}

resource "aws_db_instance" "trading_db" {
  identifier     = "mt5-trading-db"
  engine         = "postgres"
  engine_version = "17.6"
  instance_class = var.db_instance_class

  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.db_username
  # Password is managed via Secrets Manager. Enable RDS to manage the master
  # user password lifecycle. Terraform will not store the plaintext password
  # on the DB resource when this is enabled.
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.trading_db_subnet.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "mon:04:00-mon:05:00"

  skip_final_snapshot = var.environment == "dev" ? true : false
  final_snapshot_identifier = var.environment == "dev" ? null : "mt5-trading-db-final-snapshot"

  tags = {
    Name = "mt5-trading-db"
  }
}

#IAM User for Oracle VM to access S3
resource "aws_iam_user" "oracle_bot_user"{
  name  = "mt5-oracle_bot_user"

  tags  = {
    Name = "Oracle Bot S3 Access"
  }
}

resource "aws_iam_user_policy" "oracle_bot_s3_policy" {
  name = "mt5-oracle-s3-access"
  user = aws_iam_user.oracle_bot_user.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.model_storage.arn,
          "${aws_s3_bucket.model_storage.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = aws_secretsmanager_secret.mt5_credentials.arn
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = aws_sns_topic.trading_alerts.arn
      }
    ]
  })
}

# Access keys for Oracle VM
resource "aws_iam_access_key" "oracle_bot_key" {
  user = aws_iam_user.oracle_bot_user.name
}

# S3 Bucket for Model Storage
resource "aws_s3_bucket" "model_storage" {
  bucket = "mt5-trading-models-${var.environment}-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "mt5-model-storage"
  }
}

# Explicitly block public access to the model storage bucket
resource "aws_s3_bucket_public_access_block" "model_storage_block" {
  bucket = aws_s3_bucket.model_storage.id

  block_public_acls   = true
  block_public_policy = true
  ignore_public_acls  = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "model_storage_versioning" {
  bucket = aws_s3_bucket.model_storage.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "model_storage_encryption" {
  bucket = aws_s3_bucket.model_storage.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Secrets Manager for MT5 Credentials
resource "aws_secretsmanager_secret" "mt5_credentials" {
  name        = "mt5-trading-credentials-${var.environment}"
  description = "MT5 trading account credentials"

  tags = {
    Name = "mt5-credentials"
  }
}

resource "aws_secretsmanager_secret_version" "mt5_credentials_version" {
  secret_id = aws_secretsmanager_secret.mt5_credentials.id
  secret_string = jsonencode({
    mt5_login    = var.mt5_login
    mt5_password = var.mt5_password
    mt5_server   = var.mt5_server
  })
}

# SNS Topic for Alerts
resource "aws_sns_topic" "trading_alerts" {
  name = "mt5-trading-alerts-${var.environment}"

  tags = {
    Name = "mt5-trading-alerts"
  }
}

resource "aws_sns_topic_subscription" "trading_alerts_email" {
  topic_arn = aws_sns_topic.trading_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "trading_bot_logs" {
  name              = "/aws/ec2/mt5-trading-bot"
  retention_in_days = 30

  tags = {
    Name = "mt5-trading-bot-logs"
  }
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}
