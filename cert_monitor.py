#!/usr/bin/env python3
"""
Certificate Expiry Monitoring Tool

This script monitors SSL/TLS certificate expiration dates for a list of domains/URLs.
It generates JSON and HTML reports suitable for automated email notifications.

Usage:
    python cert_monitor.py --input certificates.txt --output-dir ./reports

Requirements:
    - openssl command-line tool
    - Python 3.8+
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional, Dict, Any
import threading
import concurrent.futures
from jinja2 import Template

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('cert_monitor.log')
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class CertificateInfo:
    """Data class for certificate information."""
    domain: str
    expiration_date: Optional[datetime] = None
    days_remaining: Optional[int] = None
    status: str = "UNKNOWN"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        if self.expiration_date:
            data['expiration_date'] = self.expiration_date.isoformat()
        return data

class CertificateMonitor:
    """Main class for certificate monitoring."""

    def __init__(self, timeout: int = 10, max_workers: int = 10):
        self.timeout = timeout
        self.max_workers = max_workers
        self.cert_pattern = re.compile(r'notAfter=(.+)')

    def parse_domain_port(self, entry: str) -> tuple[str, int]:
        """Parse domain and port from entry."""
        if ':' in entry:
            domain, port_str = entry.rsplit(':', 1)
            try:
                port = int(port_str)
            except ValueError:
                port = 443
        else:
            domain = entry
            port = 443
        return domain.strip(), port

    def get_certificate_expiry(self, domain: str, port: int = 443) -> CertificateInfo:
        """Retrieve certificate expiration date using openssl."""
        cert_info = CertificateInfo(domain=f"{domain}:{port}")

        try:
            # Build openssl command
            cmd = [
                'openssl', 's_client',
                '-connect', f'{domain}:{port}',
                '-servername', domain,
                '-timeout', str(self.timeout)
            ]

            # Run openssl s_client
            proc1 = subprocess.run(
                cmd,
                input=b'',
                capture_output=True,
                text=True,
                timeout=self.timeout * 2
            )

            if proc1.returncode != 0:
                cert_info.status = "FAILED"
                cert_info.error = f"Connection failed: {proc1.stderr.strip()}"
                return cert_info

            # Extract certificate and get end date
            proc2 = subprocess.run(
                ['openssl', 'x509', '-noout', '-enddate'],
                input=proc1.stdout,
                capture_output=True,
                text=True
            )

            if proc2.returncode != 0:
                cert_info.status = "FAILED"
                cert_info.error = f"Certificate parsing failed: {proc2.stderr.strip()}"
                return cert_info

            # Parse expiration date
            match = self.cert_pattern.search(proc2.stdout)
            if not match:
                cert_info.status = "FAILED"
                cert_info.error = "Could not find expiration date in certificate"
                return cert_info

            expiry_str = match.group(1).strip()
            # Parse date (format: Jun  1 12:00:00 2024 GMT)
            expiry_date = datetime.strptime(expiry_str, '%b %d %H:%M:%S %Y %Z')
            expiry_date = expiry_date.replace(tzinfo=timezone.utc)

            cert_info.expiration_date = expiry_date
            now = datetime.now(timezone.utc)
            cert_info.days_remaining = (expiry_date - now).days

            if cert_info.days_remaining <= 0:
                cert_info.status = "EXPIRED"
            elif cert_info.days_remaining <= 30:
                cert_info.status = "EXPIRING_SOON"
            else:
                cert_info.status = "VALID"

        except subprocess.TimeoutExpired:
            cert_info.status = "TIMEOUT"
            cert_info.error = f"Timeout after {self.timeout * 2} seconds"
        except Exception as e:
            cert_info.status = "ERROR"
            cert_info.error = str(e)

        return cert_info

    def check_certificates(self, domains: List[str]) -> List[CertificateInfo]:
        """Check certificates for multiple domains in parallel."""
        logger.info(f"Starting certificate checks for {len(domains)} domains")

        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_domain = {}
            for entry in domains:
                domain, port = self.parse_domain_port(entry)
                future = executor.submit(self.get_certificate_expiry, domain, port)
                future_to_domain[future] = entry

            for future in concurrent.futures.as_completed(future_to_domain):
                entry = future_to_domain[future]
                try:
                    result = future.result()
                    results.append(result)
                    logger.info(f"Checked {entry}: {result.status}")
                except Exception as e:
                    logger.error(f"Unexpected error checking {entry}: {e}")
                    results.append(CertificateInfo(
                        domain=entry,
                        status="ERROR",
                        error=str(e)
                    ))

        return results

    def generate_json_report(self, results: List[CertificateInfo], output_path: Path) -> None:
        """Generate JSON report."""
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_checked": len(results),
            "expiring_soon": len([r for r in results if r.status == "EXPIRING_SOON"]),
            "expired": len([r for r in results if r.status == "EXPIRED"]),
            "failed": len([r for r in results if r.status in ["FAILED", "TIMEOUT", "ERROR"]]),
            "certificates": [r.to_dict() for r in results]
        }

        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"JSON report saved to {output_path}")

    def generate_html_report(self, results: List[CertificateInfo], output_path: Path) -> None:
        """Generate HTML report."""
        html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SSL Certificate Expiry Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
        .summary { display: flex; gap: 20px; margin-bottom: 20px; }
        .summary-item { background-color: #e9ecef; padding: 10px; border-radius: 5px; flex: 1; text-align: center; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f8f9fa; }
        .status-valid { color: green; }
        .status-expiring-soon { color: orange; }
        .status-expired, .status-failed, .status-timeout, .status-error { color: red; }
        .expiring-soon { background-color: #fff3cd; }
        .expired { background-color: #f8d7da; }
        .failed { background-color: #f5c6cb; }
    </style>
</head>
<body>
    <div class="header">
        <h1>SSL Certificate Expiry Report</h1>
        <p>Generated at: {{ generated_at }}</p>
    </div>

    <div class="summary">
        <div class="summary-item">
            <h3>Total Checked</h3>
            <p>{{ total_checked }}</p>
        </div>
        <div class="summary-item">
            <h3>Expiring Soon (≤30 days)</h3>
            <p>{{ expiring_soon }}</p>
        </div>
        <div class="summary-item">
            <h3>Expired</h3>
            <p>{{ expired }}</p>
        </div>
        <div class="summary-item">
            <h3>Failed</h3>
            <p>{{ failed }}</p>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>Domain</th>
                <th>Expiration Date</th>
                <th>Days Remaining</th>
                <th>Status</th>
                <th>Error</th>
            </tr>
        </thead>
        <tbody>
            {% for cert in certificates %}
            <tr class="{% if cert.status == 'EXPIRING_SOON' %}expiring-soon{% elif cert.status == 'EXPIRED' %}expired{% elif cert.status in ['FAILED', 'TIMEOUT', 'ERROR'] %}failed{% endif %}">
                <td>{{ cert.domain }}</td>
                <td>{{ cert.expiration_date or 'N/A' }}</td>
                <td>{{ cert.days_remaining or 'N/A' }}</td>
                <td class="status-{{ cert.status.lower() }}">{{ cert.status }}</td>
                <td>{{ cert.error or '' }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
        """

        template = Template(html_template)
        report_data = {
            "generated_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
            "total_checked": len(results),
            "expiring_soon": len([r for r in results if r.status == "EXPIRING_SOON"]),
            "expired": len([r for r in results if r.status == "EXPIRED"]),
            "failed": len([r for r in results if r.status in ["FAILED", "TIMEOUT", "ERROR"]]),
            "certificates": [
                {
                    "domain": r.domain,
                    "expiration_date": r.expiration_date.strftime('%Y-%m-%d %H:%M:%S UTC') if r.expiration_date else None,
                    "days_remaining": r.days_remaining,
                    "status": r.status,
                    "error": r.error
                }
                for r in results
            ]
        }

        html_content = template.render(**report_data)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"HTML report saved to {output_path}")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='SSL Certificate Expiry Monitor')
    parser.add_argument('--input', '-i', required=True, help='Input file with domains')
    parser.add_argument('--output-dir', '-o', default='./reports', help='Output directory for reports')
    parser.add_argument('--timeout', '-t', type=int, default=10, help='Connection timeout in seconds')
    parser.add_argument('--max-workers', '-w', type=int, default=10, help='Maximum parallel workers')

    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Read domains
    try:
        with open(args.input, 'r') as f:
            domains = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logger.error(f"Input file {args.input} not found")
        sys.exit(1)

    if not domains:
        logger.error("No domains found in input file")
        sys.exit(1)

    # Initialize monitor
    monitor = CertificateMonitor(timeout=args.timeout, max_workers=args.max_workers)

    # Check certificates
    results = monitor.check_certificates(domains)

    # Generate reports
    json_path = output_dir / 'certificate_report.json'
    html_path = output_dir / 'certificate_report.html'

    monitor.generate_json_report(results, json_path)
    monitor.generate_html_report(results, html_path)

    logger.info("Certificate monitoring completed")

if __name__ == '__main__':
    main()