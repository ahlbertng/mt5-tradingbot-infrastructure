FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for MT5
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    xvfb \
    wine64 \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from bot folder
COPY bot/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire bot folder
COPY bot/ /app/

# Create necessary directories
RUN mkdir -p /app/logs /app/models /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import os; exit(0 if os.path.exists('/app/logs/trading_bot.log') else 1)" || exit 1

# Run the bot
CMD ["python", "-u", "main.py"]
