# Production IoT PoC Deployment Container
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for CDK CLI
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

# Copy requirements first for better Docker layer caching
COPY requirements.txt ./
COPY production/requirements-prod.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-prod.txt

# Install CDK CLI
RUN npm install -g aws-cdk@2

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 deployer && chown -R deployer:deployer /app
USER deployer

# Set environment variables
ENV PYTHONPATH=/app
ENV AWS_DEFAULT_REGION=us-west-2

# Default command
CMD ["python", "production/deployment_manager.py"] 