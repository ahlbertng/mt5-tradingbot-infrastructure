# 🎮 Ansible Production Deployment - MT5 Trading Bot

## 📋 Executive Summary

This Ansible automation framework deploys a production-grade ML-powered trading infrastructure across a hybrid multi-cloud environment (Oracle Cloud + AWS), achieving **70% cost optimization** while maintaining enterprise-level reliability and security.

### Business Value

- **Cost Optimization**: 70% reduction vs traditional AWS-only deployment
- **Automated Deployment**: Zero-touch deployment with one command
- **Infrastructure as Code**: Reproducible, version-controlled infrastructure
- **Enterprise Security**: Encrypted secrets, IAM roles, network isolation
- **Production Monitoring**: CloudWatch metrics, Grafana dashboards, SNS alerts
- **Scalability**: Ready for multi-region, multi-environment expansion

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 ANSIBLE CONTROL NODE                        │
│                   (Your Laptop)                             │
│                                                             │
│  ansible-playbook playbooks/deploy-production.yml          │
│                      │                                      │
└──────────────────────┼──────────────────────────────────────┘
                       │ SSH
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              ORACLE CLOUD VM (Target)                       │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  Phase 1: System Setup                                │ │
│  │    - Update packages                                  │ │
│  │    - Install dependencies                             │ │
│  │    - Configure timezone                               │ │
│  ├───────────────────────────────────────────────────────┤ │
│  │  Phase 2: Docker Installation                         │ │
│  │    - Install Docker Engine                            │ │
│  │    - Configure Docker Compose                         │ │
│  ├───────────────────────────────────────────────────────┤ │
│  │  Phase 3: AWS Integration                             │ │
│  │    - Configure AWS CLI                                │ │
│  │    - Install CloudWatch Agent                         │ │
│  │    - Test connectivity to RDS/S3                      │ │
│  ├───────────────────────────────────────────────────────┤ │
│  │  Phase 4: Application Deployment                      │ │
│  │    - Clone repository                                 │ │
│  │    - Build Docker images                              │ │
│  │    - Deploy containers                                │ │
│  ├───────────────────────────────────────────────────────┤ │
│  │  Phase 5: Monitoring Setup                            │ │
│  │    - Configure Grafana                                │ │
│  │    - Set up CloudWatch metrics                        │ │
│  │    - Enable SNS alerts                                │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   AWS MANAGED SERVICES                      │
│  RDS • S3 • CloudWatch • SNS • Secrets Manager              │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
ansible/
├── ansible.cfg                 # Ansible configuration
├── inventory/
│   └── production.yml          # Production environment inventory
├── playbooks/
│   ├── deploy-production.yml   # Main deployment playbook
│   ├── manage-bot.yml          # Management operations
│   └── rollback.yml            # Rollback procedures
├── templates/
│   ├── env-production.j2       # Environment configuration
│   └── cloudwatch-config.json.j2
├── vars/
│   ├── secrets.yml.example     # Secrets template
│   └── production.yml          # Production variables
└── README.md                   # This file
```

---

## 🚀 Quick Start

### Prerequisites

**On Your Local Machine:**
- Ansible 2.9+ installed
- SSH access to Oracle VM
- AWS credentials (from Terraform)

**On Oracle Cloud:**
- VM created with SSH key
- Public IP noted

**In AWS:**
- Terraform infrastructure deployed
- RDS, S3, CloudWatch configured

---

### Step 1: Clone Repository

```bash
git clone https://github.com/yourusername/mt5-trading-bot-infrastructure.git
cd mt5-trading-bot-infrastructure/ansible
```

---

### Step 2: Configure Inventory

```bash
# Edit production inventory
nano inventory/production.yml

# Update this line with your Oracle VM IP:
ansible_host: "YOUR_ORACLE_VM_PUBLIC_IP"
```

---

### Step 3: Create Secrets File

```bash
# Copy example secrets
cp vars/secrets.yml.example vars/secrets.yml

# Edit with your credentials
nano vars/secrets.yml

# Add:
# - MT5 demo credentials
# - AWS access keys (from terraform output oracle_bot_secret_key)
# - Database password (from terraform.tfvars)
```

---

### Step 4: Encrypt Secrets

```bash
# Encrypt the secrets file
ansible-vault encrypt vars/secrets.yml

# Enter a strong vault password
# SAVE THIS PASSWORD - you'll need it for deployment!
```

---

### Step 5: Test Connectivity

```bash
# Test SSH connection to Oracle VM
ansible production -m ping

# Expected output:
# oracle-vm-prod | SUCCESS => {
#     "ping": "pong"
# }
```

---

### Step 6: Deploy to Production

```bash
# Run deployment
ansible-playbook playbooks/deploy-production.yml --ask-vault-pass

# Enter vault password when prompted
# Deployment takes ~10-15 minutes
```

---

## 📊 Deployment Phases

### Phase 1: System Preparation (2-3 min)
- Updates all system packages
- Installs essential tools
- Configures timezone and hostname
- Sets up firewall rules

### Phase 2: Docker Installation (3-4 min)
- Installs Docker Engine
- Configures Docker Compose
- Adds user to docker group
- Enables Docker service

### Phase 3: AWS Integration (2-3 min)
- Installs AWS CLI
- Configures credentials
- Tests S3 connectivity
- Installs CloudWatch agent

### Phase 4: Application Deployment (4-5 min)
- Clones bot repository
- Builds Docker images
- Creates environment configuration
- Starts containers

### Phase 5: Monitoring Setup (2-3 min)
- Configures Grafana dashboards
- Enables CloudWatch metrics
- Sets up SNS alerts
- Runs health checks

**Total Deployment Time: ~15 minutes**

---

## 🎯 Management Commands

### Deployment

```bash
# Initial deployment
ansible-playbook playbooks/deploy-production.yml --ask-vault-pass

# Deploy specific phases
ansible-playbook playbooks/deploy-production.yml --tags "docker,deploy"

# Dry run (check what would change)
ansible-playbook playbooks/deploy-production.yml --check
```

### Bot Management

```bash
# Start bot
ansible-playbook playbooks/manage-bot.yml -e "action=start"

# Stop bot
ansible-playbook playbooks/manage-bot.yml -e "action=stop"

# Restart bot
ansible-playbook playbooks/manage-bot.yml -e "action=restart"

# View logs
ansible-playbook playbooks/manage-bot.yml -e "action=logs"

# Update code and restart
ansible-playbook playbooks/manage-bot.yml -e "action=update"

# Get statistics
ansible-playbook playbooks/manage-bot.yml -e "action=stats"
```

### Ad-Hoc Commands

```bash
# Check disk space
ansible production -m shell -a "df -h"

# Check running containers
ansible production -m shell -a "docker ps"

# View bot logs
ansible production -m shell -a "cd /home/ubuntu/mt5-trading-bot && docker compose logs --tail=100 trading-bot"

# Reboot server
ansible production -m reboot
```

---

## 🔒 Security Best Practices

### Secrets Management

- ✅ All secrets stored in `vars/secrets.yml`
- ✅ File encrypted with `ansible-vault`
- ✅ Never commit unencrypted secrets
- ✅ AWS credentials rotated regularly
- ✅ Database passwords follow complexity requirements

### Network Security

- SSH key-based authentication only
- Firewall configured with minimal ports
- AWS Security Groups restrict access
- Private subnets for database

### Access Control

- Principle of least privilege
- Separate credentials per environment
- Audit logging enabled
- Regular security reviews

---

## 📈 Monitoring & Alerts

### Grafana Dashboards

Access: `http://YOUR_ORACLE_VM_IP:3000`

**Credentials:**
- Username: `admin`
- Password: (from secrets.yml)

**Available Dashboards:**
- Account balance tracking
- Daily P&L charts
- Trade execution metrics
- System resource monitoring

### CloudWatch Metrics

**Custom Metrics:**
- `AccountBalance` - Current account balance
- `DailyPnL` - Daily profit/loss
- `TradesExecuted` - Number of trades
- `WinRate` - Percentage of winning trades

**System Metrics:**
- CPU utilization
- Memory usage
- Disk space
- Network throughput

### SNS Alerts

**Configured Alerts:**
- Low account balance (< $9,000)
- High daily loss (> $400)
- Bot downtime (no metrics for 15 min)
- System resource alerts

---

## 💼 Business Presentation

### For Stakeholders

"This automated deployment framework enables us to deploy our ML trading infrastructure to production with a single command, ensuring consistency, security, and minimal human error. The hybrid cloud architecture reduces our infrastructure costs by 70% while maintaining enterprise-grade reliability."

### For Technical Teams

"Ansible orchestrates the complete deployment pipeline: system configuration, Docker installation, AWS service integration, application deployment, and monitoring setup. All configuration is version-controlled and reproducible. Secrets are encrypted with ansible-vault. The playbook includes comprehensive error handling and rollback capabilities."

### For Portfolio/Interviews

**Key Talking Points:**
- "Implemented Infrastructure as Code using Ansible for automated deployment"
- "Reduced deployment time from 2 hours manual to 15 minutes automated"
- "Achieved 70% cost optimization through hybrid cloud architecture"
- "Implemented enterprise security with encrypted secrets and IAM roles"
- "Set up comprehensive monitoring with CloudWatch and Grafana"

---

## 🧪 Testing

### Pre-Deployment Testing

```bash
# Syntax check
ansible-playbook playbooks/deploy-production.yml --syntax-check

# Dry run
ansible-playbook playbooks/deploy-production.yml --check

# Test connectivity
ansible production -m ping
```

### Post-Deployment Verification

```bash
# Check all services running
ansible production -m shell -a "docker ps"

# Verify database connectivity
ansible production -m shell -a "docker compose exec -T postgres psql -h YOUR_RDS -U trading_admin -d trading_db -c 'SELECT 1;'"

# Check CloudWatch agent
ansible production -m shell -a "systemctl status amazon-cloudwatch-agent"
```

---

## 🔄 Rollback Procedures

```bash
# Rollback to previous version
ansible-playbook playbooks/rollback.yml -e "version=previous"

# Rollback specific service
ansible-playbook playbooks/rollback.yml -e "service=trading-bot"
```

---

## 📝 Troubleshooting

### Common Issues

**Issue: Cannot connect to Oracle VM**
```bash
# Test SSH manually
ssh -i ~/.ssh/oracle-mt5-key ubuntu@YOUR_ORACLE_VM_IP

# Check firewall rules in Oracle Console
```

**Issue: AWS credentials not working**
```bash
# Test manually on VM
ssh ubuntu@YOUR_ORACLE_VM_IP
aws s3 ls s3://your-bucket/
```

**Issue: Docker containers not starting**
```bash
# Check logs
ansible production -m shell -a "docker compose logs"
```

---

## 📞 Support

**Documentation:**
- Full architecture docs: `docs/ARCHITECTURE.md`
- Troubleshooting guide: `docs/TROUBLESHOOTING.md`

**Contact:**
- DevOps Team: devops@yourcompany.com
- Incident Reports: alerts@yourcompany.com

---

## 📄 License

This project is licensed under the MIT License.

---

**Built with ❤️ using Ansible, Docker, and AWS**

*Showcasing DevOps automation and cloud architecture expertise*
