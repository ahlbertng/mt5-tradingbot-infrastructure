# 🤖 MT5 Trading Bot - Multi-Cloud Infrastructure

[![Terraform](https://img.shields.io/badge/Terraform-1.0+-623CE4?style=flat&logo=terraform)](https://www.terraform.io/)
[![AWS](https://img.shields.io/badge/AWS-Cloud-FF9900?style=flat&logo=amazon-aws)](https://aws.amazon.com/)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=flat&logo=docker)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> Production-grade infrastructure for an ML-powered algorithmic trading bot with multi-cloud deployment and 70% cost optimization.

## 🎯 Project Overview

This project demonstrates enterprise-level DevOps practices by implementing a complete infrastructure stack for an algorithmic trading bot powered by reinforcement learning. The system uses a hybrid cloud architecture to optimize costs while maintaining production-grade reliability.

### Key Features

- **Multi-Cloud Architecture**: Hybrid Oracle Cloud + AWS deployment
- **Infrastructure as Code**: Complete Terraform configuration
- **Configuration Management**: Ansible playbooks for automated deployment
- **Containerization**: Docker and Docker Compose for consistency
- **ML Integration**: Reinforcement learning using Stable-Baselines3
- **Cost Optimization**: 70% reduction vs traditional AWS-only approach
- **Production Monitoring**: CloudWatch metrics, Grafana dashboards
- **Security**: Encrypted state, secrets management, IAM roles

## 🏗️ Architecture

### Hybrid Cloud Design

```
┌─────────────────────────────────────────────────────────────┐
│                   ORACLE CLOUD (FREE TIER)                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  ARM VM (4 CPU, 24GB RAM)                           │   │
│  │  ├─ Trading Bot (Docker)                            │   │
│  │  ├─ Grafana (Monitoring)                            │   │
│  │  └─ CloudWatch Agent                                │   │
│  └─────────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    AWS MANAGED SERVICES                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ RDS          │  │ S3           │  │ CloudWatch   │     │
│  │ PostgreSQL   │  │ ML Models    │  │ Monitoring   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐                       │
│  │ SNS          │  │ Secrets Mgr  │                       │
│  │ Alerts       │  │ Credentials  │                       │
│  └──────────────┘  └──────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

### Tech Stack

**Infrastructure**
- Terraform - Infrastructure as Code
- Ansible - Configuration Management
- Docker/Docker Compose - Containerization

**Cloud Providers**
- AWS (RDS, S3, CloudWatch, SNS, Secrets Manager)
- Oracle Cloud (ARM VM - forever free tier)

**Application**
- Python 3.11
- Stable-Baselines3 (PPO Reinforcement Learning)
- FinRL (Financial RL framework)
- MetaTrader 5 API
- PostgreSQL

**Monitoring**
- Grafana (dashboards)
- AWS CloudWatch (metrics & logs)
- SNS (email/SMS alerts)

## 🚀 Quick Start

### Prerequisites

- AWS Account (free tier eligible)
- Terraform >= 1.0
- Ansible >= 2.9
- Docker & Docker Compose
- MT5 Demo Account

### Deployment Options

#### Option 1: Local Testing (Recommended for first-time)

```bash
# 1. Clone repository
git clone https://github.com/yourusername/mt5-trading-bot-infrastructure.git
cd mt5-trading-bot-infrastructure

# 2. Configure environment
cp .env.example .env
nano .env  # Add your MT5 credentials

# 3. Start services
docker-compose up -d

# 4. Access Grafana
open http://localhost:3000
```

#### Option 2: AWS + Oracle Cloud Hybrid (Production)

```bash
# 1. Deploy AWS infrastructure
cd terraform
cp terraform.tfvars.example terraform.tfvars
nano terraform.tfvars  # Update with your values
terraform init
terraform apply

# 2. Create Oracle Cloud VM
# - Sign up at oracle.com/cloud/free
# - Create ARM instance (4 CPU, 24GB)
# - Download SSH key
# - Note public IP

# 3. Update Ansible inventory
cd ../ansible
nano inventory/hosts.yml  # Add Oracle VM IP

# 4. Create secrets file
cp vars/secrets.yml.example vars/secrets.yml
nano vars/secrets.yml  # Add credentials
ansible-vault encrypt vars/secrets.yml

# 5. Deploy bot
ansible-playbook playbooks/deploy.yml --ask-vault-pass
```

## 📁 Project Structure

```
.
├── terraform/              # Infrastructure as Code
│   ├── main.tf            # Main configuration
│   ├── variables.tf       # Input variables
│   ├── outputs.tf         # Output values
│   └── terraform.tfvars   # Your values (gitignored)
├── ansible/               # Configuration Management
│   ├── inventory/         # Host definitions
│   ├── playbooks/         # Automation playbooks
│   ├── templates/         # Config templates
│   └── vars/              # Variables & secrets
├── bot/                   # Trading bot application
│   ├── main.py           # Main orchestrator
│   ├── ml_agent.py       # RL agent
│   ├── mt5_connector.py  # MT5 integration
│   ├── database.py       # PostgreSQL ops
│   └── requirements.txt  # Python dependencies
├── docker-compose.yml     # Container orchestration
├── Dockerfile            # Bot container image
└── .gitignore           # Protected files

```

## 🔧 Configuration

### Environment Variables

```bash
# MT5 Account
MT5_LOGIN=your_account_number
MT5_PASSWORD=your_password
MT5_SERVER=ICMarketsSC-Demo

# Database (AWS RDS)
DB_ENDPOINT=your-rds-endpoint.rds.amazonaws.com:5432
DB_NAME=trading_db
DB_USERNAME=trading_admin
DB_PASSWORD=your_secure_password

# AWS Services
S3_BUCKET=your-s3-bucket
AWS_REGION=us-east-1
SNS_TOPIC_ARN=arn:aws:sns:...
```

### Terraform Variables

Key variables in `terraform.tfvars`:

```hcl
aws_region = "us-east-1"
environment = "prod"
db_password = "your_secure_password"
oracle_vm_ip = "123.45.67.89"  # Update after VM creation
```

## 📊 Monitoring

### Grafana Dashboards
- Account balance tracking
- Daily P&L charts
- Trade execution metrics
- System resource monitoring

### CloudWatch Metrics
- Custom metrics: AccountBalance, DailyPnL, TradesExecuted
- System metrics: CPU, Memory, Disk
- Logs: Bot application logs

### Alerts
- Low account balance
- High daily loss
- Bot downtime
- System resource alerts

## 🔒 Security

- **S3 Backend**: Encrypted Terraform state with versioning
- **Secrets Management**: Ansible Vault + AWS Secrets Manager
- **IAM Roles**: Least privilege access
- **Network Security**: Security groups with IP whitelisting
- **Encryption**: All data encrypted at rest and in transit

## 🧪 Testing

```bash
# Run local tests
docker-compose up -d
docker-compose logs -f trading-bot

# Validate Terraform
cd terraform
terraform validate
terraform plan

# Test Ansible connectivity
cd ansible
ansible trading_bots -m ping
```

## 📈 Machine Learning

The bot uses **Proximal Policy Optimization (PPO)** for adaptive trading strategy:

- **State Space**: Market indicators, account info, positions
- **Action Space**: Buy, Sell, Hold
- **Reward**: Profit/Loss with risk-adjusted returns
- **Training**: Continuous learning from live trades
- **Framework**: Stable-Baselines3 + FinRL

## 🛠️ Management Commands

```bash
# Terraform
terraform plan          # Preview changes
terraform apply         # Deploy infrastructure
terraform destroy       # Tear down resources
terraform output        # View outputs

# Ansible
ansible-playbook playbooks/deploy.yml    # Deploy bot
ansible-playbook playbooks/manage.yml -e "action=start"
ansible-playbook playbooks/manage.yml -e "action=stop"
ansible-playbook playbooks/manage.yml -e "action=logs"

# Docker
docker-compose up -d         # Start services
docker-compose down          # Stop services
docker-compose logs -f       # View logs
docker-compose restart       # Restart services
```

## 🎓 Key Learnings

This project demonstrates:

- Multi-cloud architecture design and implementation
- Infrastructure as Code best practices
- Configuration management at scale
- Cost optimization strategies
- Production monitoring and alerting
- Security hardening
- ML model deployment in production
- DevOps automation workflows

## 🚧 Roadmap

- [ ] CI/CD pipeline with GitHub Actions
- [ ] Multi-region deployment
- [ ] A/B testing for ML strategies
- [ ] Backtesting framework
- [ ] Real-time model performance tracking
- [ ] Kubernetes deployment option

## ⚠️ Disclaimer

This is an educational project. **Do not use with real money without thorough testing.** Trading involves significant risk of loss.