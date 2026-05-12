# SSL Certificate Expiry Monitor

A production-ready solution for monitoring SSL/TLS certificate expiration dates across multiple domains. This tool automatically checks certificates, generates reports, and sends email notifications.

## Features

- **Parallel Certificate Checking**: Uses threading for efficient concurrent checks
- **Comprehensive Reporting**: Generates both JSON and HTML reports
- **Email Notifications**: Sends formatted HTML emails with embedded reports
- **Jenkins Integration**: Ready-to-use Jenkins pipeline for automated daily checks
- **Error Handling**: Graceful handling of connection failures, timeouts, and invalid certificates
- **Configurable**: Environment variables and command-line options for customization

## Requirements

- Python 3.8+
- OpenSSL command-line tool
- Jenkins (for automated execution)

## Installation

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Manual Execution

```bash
python cert_monitor.py --input certificates.txt --output-dir ./reports
```

### Command Line Options

- `--input, -i`: Path to input file containing domains (required)
- `--output-dir, -o`: Output directory for reports (default: ./reports)
- `--timeout, -t`: Connection timeout in seconds (default: 10)
- `--max-workers, -w`: Maximum parallel workers (default: 10)

### Input File Format

Create a text file with one domain per line:

```
google.com
github.com
example.com:8443
https://custom.domain.com
```

Supports:
- Hostnames (default port 443)
- Custom ports (domain:port format)
- Full URLs (protocol is ignored)

## Jenkins Setup

1. Create a new Jenkins pipeline job
2. Configure SCM to point to this repository
3. Ensure a dedicated permanent agent is available with Docker installed
4. If required, update the pipeline label in `Jenkinsfile` to match your agent label
5. Set up the following environment variables:
   - `EMAIL_RECIPIENTS`: Comma-separated list of email addresses
   - `ADMIN_EMAIL`: Admin email for failure notifications

### Scheduling

This pipeline is configured to run daily at 8 AM using:

```
H 8 * * *
```

### Docker Agent Requirements

The permanent agent must have:
- Docker engine installed
- permission to run Docker commands
- access to the workspace directory

The pipeline builds the `cert-monitor:latest` Docker image from `Dockerfile`, then runs the certificate check inside the container.

## Output

### JSON Report

Contains structured data including:
- Generation timestamp
- Summary statistics
- Detailed certificate information

### HTML Report

Responsive HTML table with:
- Color-coded status indicators
- Summary dashboard
- Professional formatting for email clients

## Status Codes

- **VALID**: Certificate is valid (>30 days remaining)
- **EXPIRING_SOON**: Certificate expires within 30 days
- **EXPIRED**: Certificate has already expired
- **FAILED**: Connection or parsing failed
- **TIMEOUT**: Connection timed out
- **ERROR**: Unexpected error occurred

## Security Considerations

- Uses subprocess safely with proper input validation
- No sensitive data stored in logs
- OpenSSL commands are executed with timeouts
- Error messages are sanitized

## Docker Support

Build the Docker image:

```bash
docker build -t cert-monitor .
```

Run the container:

```bash
docker run -v $(pwd)/certificates.txt:/app/certificates.txt -v $(pwd)/reports:/app/reports cert-monitor
```

### Jenkins Docker Execution

This repository includes a `Jenkinsfile` that builds and runs the Docker image on a dedicated permanent agent. The job is intended to execute inside a Docker-capable Jenkins node using a label such as `permanent-docker`.

## Development

### Running Tests

```bash
python -m pytest tests/
```

### Code Quality

```bash
# Format code
black .

# Lint code
flake8 .

# Type checking
mypy .
```

## License

MIT License