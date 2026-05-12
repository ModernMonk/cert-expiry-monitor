# Use Python 3.9 slim image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    openssl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY cert_monitor.py .
COPY certificates.txt .

# Create reports directory
RUN mkdir reports

# Set default command
CMD ["python", "cert_monitor.py", "--input", "certificates.txt", "--output-dir", "reports"]