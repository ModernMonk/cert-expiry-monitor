import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from cert_monitor import CertificateMonitor, CertificateInfo

class TestCertificateMonitor(unittest.TestCase):

    def setUp(self):
        self.monitor = CertificateMonitor(timeout=5, max_workers=2)

    def test_parse_domain_port_default(self):
        domain, port = self.monitor.parse_domain_port("example.com")
        self.assertEqual(domain, "example.com")
        self.assertEqual(port, 443)

    def test_parse_domain_port_custom(self):
        domain, port = self.monitor.parse_domain_port("example.com:8443")
        self.assertEqual(domain, "example.com")
        self.assertEqual(port, 8443)

    def test_parse_domain_port_invalid_port(self):
        domain, port = self.monitor.parse_domain_port("example.com:invalid")
        self.assertEqual(domain, "example.com")
        self.assertEqual(port, 443)

    @patch('subprocess.run')
    def test_get_certificate_expiry_success(self, mock_run):
        # Mock successful openssl output
        mock_proc1 = MagicMock()
        mock_proc1.returncode = 0
        mock_proc1.stdout = "certificate data"
        mock_proc1.stderr = ""

        mock_proc2 = MagicMock()
        mock_proc2.returncode = 0
        mock_proc2.stdout = "notAfter=Jun  1 12:00:00 2025 GMT\n"
        mock_proc2.stderr = ""

        mock_run.side_effect = [mock_proc1, mock_proc2]

        result = self.monitor.get_certificate_expiry("example.com", 443)

        self.assertEqual(result.domain, "example.com:443")
        self.assertEqual(result.status, "VALID")
        self.assertIsNotNone(result.expiration_date)
        self.assertIsNotNone(result.days_remaining)
        self.assertIsNone(result.error)

    @patch('subprocess.run')
    def test_get_certificate_expiry_connection_failed(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = "Connection refused"
        mock_run.return_value = mock_proc

        result = self.monitor.get_certificate_expiry("invalid.example.com", 443)

        self.assertEqual(result.status, "FAILED")
        self.assertIn("Connection failed", result.error)

    @patch('subprocess.run')
    def test_get_certificate_expiry_timeout(self, mock_run):
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired(cmd=[], timeout=10)

        result = self.monitor.get_certificate_expiry("timeout.example.com", 443)

        self.assertEqual(result.status, "TIMEOUT")
        self.assertIn("Timeout", result.error)

    def test_certificate_info_to_dict(self):
        expiry = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        cert = CertificateInfo(
            domain="test.com:443",
            expiration_date=expiry,
            days_remaining=30,
            status="VALID"
        )

        data = cert.to_dict()
        self.assertEqual(data['domain'], "test.com:443")
        self.assertEqual(data['expiration_date'], expiry.isoformat())
        self.assertEqual(data['days_remaining'], 30)
        self.assertEqual(data['status'], "VALID")

    def test_check_certificates_parallel(self):
        domains = ["google.com", "github.com"]

        with patch.object(self.monitor, 'get_certificate_expiry') as mock_get:
            mock_get.side_effect = [
                CertificateInfo(domain="google.com:443", status="VALID"),
                CertificateInfo(domain="github.com:443", status="VALID")
            ]

            results = self.monitor.check_certificates(domains)

            self.assertEqual(len(results), 2)
            self.assertEqual(mock_get.call_count, 2)

if __name__ == '__main__':
    unittest.main()