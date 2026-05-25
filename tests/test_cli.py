import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class OpenFinanceCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.config_path = root / "config.json"
        self.token_path = root / "tokens.json"

    def tearDown(self):
        self.tempdir.cleanup()

    def run_cli(self, *args):
        from openfinance.cli import main

        stdout = io.StringIO()
        env = {
            "OPENFINANCE_CONFIG": str(self.config_path),
            "OPENFINANCE_TOKEN_CACHE": str(self.token_path),
        }
        with mock.patch.dict(os.environ, env, clear=False):
            with contextlib.redirect_stdout(stdout):
                code = main(["--no-color"] + list(args))

        self.assertEqual(code, 0, stdout.getvalue())
        output = stdout.getvalue().strip()
        self.assertTrue(output, "CLI produced no JSON output")
        return json.loads(output)

    def test_accounts_uses_schema_shaped_mock_without_config(self):
        payload = self.run_cli("accounts")

        self.assertEqual(payload["meta"]["totalRecords"], 1)
        account = payload["data"][0]
        self.assertEqual(account["accountId"], "mock-account-001")
        self.assertEqual(account["companyCnpj"], "21128159000166")
        self.assertEqual(account["type"], "CONTA_DEPOSITO_A_VISTA")
        self.assertIn("links", payload)

    def test_token_command_returns_and_caches_mock_token(self):
        payload = self.run_cli("token")

        self.assertEqual(payload["token_type"], "Bearer")
        self.assertTrue(payload["access_token"].startswith("mock-access-token"))
        self.assertTrue(self.token_path.exists())

    def test_consents_create_builds_open_finance_payload(self):
        payload = self.run_cli(
            "consents",
            "create",
            "--cpf",
            "12345678901",
            "--permissions",
            "ACCOUNTS_READ",
            "ACCOUNTS_BALANCES_READ",
            "RESOURCES_READ",
            "--expiration-date-time",
            "2026-12-31T23:59:59Z",
        )

        consent = payload["data"]
        self.assertEqual(consent["status"], "AWAITING_AUTHORISATION")
        self.assertEqual(consent["loggedUser"]["document"]["identification"], "12345678901")
        self.assertIn("RESOURCES_READ", consent["permissions"])

    def test_config_set_persists_and_masks_secret_on_show(self):
        self.run_cli(
            "config",
            "set",
            "--base-url",
            "https://example.test/open-banking/accounts/v2",
            "--client-id",
            "client",
            "--client-secret",
            "secret",
            "--certificate",
            "/tmp/cert.pem",
        )

        payload = self.run_cli("config", "show")
        self.assertEqual(payload["base_url"], "https://example.test/open-banking/accounts/v2")
        self.assertEqual(payload["client_id"], "client")
        self.assertEqual(payload["client_secret"], "***")
        self.assertEqual(payload["certificate"], "/tmp/cert.pem")


if __name__ == "__main__":
    unittest.main()
