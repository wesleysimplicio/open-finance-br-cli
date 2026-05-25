import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from . import __version__
from .auth import get_access_token
from .config import DEFAULT_PARTICIPANTS_URL, DEFAULT_SANDBOX_PARTICIPANTS_URL


SCHEMA_SOURCES = {
    "accounts": {
        "version": "2.4.2",
        "url": "https://raw.githubusercontent.com/OpenBanking-Brasil/openapi/main/swagger-apis/accounts/2.4.2.yml",
        "endpoints": {
            "GET /accounts": "ResponseAccountList",
            "GET /accounts/{accountId}": "ResponseAccountIdentification",
            "GET /accounts/{accountId}/balances": "ResponseAccountBalances",
            "GET /accounts/{accountId}/transactions": "ResponseAccountTransactions",
            "GET /accounts/{accountId}/transactions-current": "ResponseAccountTransactions",
        },
    },
    "consents": {
        "version": "3.0.1",
        "url": "https://raw.githubusercontent.com/OpenBanking-Brasil/openapi/main/swagger-apis/consents/3.0.1.yml",
        "endpoints": {
            "POST /consents": "CreateConsent -> ResponseConsent",
            "GET /consents/{consentId}": "ResponseConsentRead",
            "DELETE /consents/{consentId}": "204",
        },
    },
    "resources": {
        "version": "3.0.0",
        "url": "https://raw.githubusercontent.com/OpenBanking-Brasil/openapi/main/swagger-apis/resources/3.0.0.yml",
        "endpoints": {"GET /resources": "ResponseResourceList"},
    },
    "participants": {
        "version": "directory-public-json",
        "url": DEFAULT_PARTICIPANTS_URL,
        "endpoints": {"GET /participants": "Directory participants JSON"},
    },
}


class OpenFinanceError(Exception):
    """Raised for HTTP and client configuration failures."""


class OpenFinanceClient:
    def __init__(self, config):
        self.config = dict(config or {})
        self._ssl_context = None
        self._ssl_context_loaded = False

    def token(self, scope=None, force=False):
        return get_access_token(
            self.config,
            scope=scope,
            force=force,
            ssl_context=self.get_ssl_context(),
        )

    def accounts(self, page=None, page_size=None, account_type=None):
        query = {
            "page": page,
            "page-size": page_size,
            "accountType": account_type,
        }
        return self.request("GET", "/accounts", service="accounts", query=query)

    def account(self, account_id):
        return self.request("GET", "/accounts/%s" % quote_path(account_id), service="accounts")

    def balances(self, account_id):
        return self.request("GET", "/accounts/%s/balances" % quote_path(account_id), service="accounts")

    def transactions(
        self,
        account_id,
        current=False,
        page=None,
        page_size=None,
        from_booking_date=None,
        to_booking_date=None,
        credit_debit_indicator=None,
    ):
        suffix = "transactions-current" if current else "transactions"
        query = {
            "page": page,
            "page-size": page_size,
            "fromBookingDate": from_booking_date,
            "toBookingDate": to_booking_date,
            "creditDebitIndicator": credit_debit_indicator,
        }
        path = "/accounts/%s/%s" % (quote_path(account_id), suffix)
        return self.request("GET", path, service="accounts", query=query)

    def create_consent(self, payload):
        return self.request("POST", "/consents", service="consents", data=payload)

    def get_consent(self, consent_id):
        return self.request("GET", "/consents/%s" % quote_path(consent_id), service="consents")

    def delete_consent(self, consent_id):
        return self.request("DELETE", "/consents/%s" % quote_path(consent_id), service="consents")

    def resources(self, page=None, page_size=None):
        query = {"page": page, "page-size": page_size}
        return self.request("GET", "/resources", service="resources", query=query)

    def participants(self, sandbox=False, limit=None, force_mock=False):
        if force_mock or self.config.get("mock"):
            return mock_response("participants", "GET", "/participants")

        url = self.config.get("participants_url")
        if not url:
            url = DEFAULT_SANDBOX_PARTICIPANTS_URL if sandbox else DEFAULT_PARTICIPANTS_URL
        payload = self.request_url("GET", url, require_auth=False)
        if limit and isinstance(payload, list):
            return payload[: int(limit)]
        if limit and isinstance(payload, dict) and isinstance(payload.get("data"), list):
            result = dict(payload)
            result["data"] = result["data"][: int(limit)]
            return result
        return payload

    def request(self, method, path, service, query=None, data=None, require_auth=True):
        if self.should_mock(service):
            return mock_response(service, method, path, data=data, query=query)

        base_url = self.service_base_url(service)
        if not base_url:
            raise OpenFinanceError(
                "Missing base URL for %s. Run: openfinance config set --base-url URL"
                % service
            )
        url = join_url(base_url, path)
        if query:
            url = append_query(url, query)
        return self.request_url(method, url, data=data, require_auth=require_auth)

    def request_url(self, method, url, data=None, require_auth=True):
        body = None
        headers = {
            "Accept": "application/json",
            "User-Agent": "openfinance-br-cli/%s" % __version__,
            "x-fapi-interaction-id": str(uuid.uuid4()),
        }
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        if require_auth:
            token = self.token()
            headers["Authorization"] = "%s %s" % (
                token.get("token_type") or "Bearer",
                token["access_token"],
            )

        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        opener = build_opener(self.get_ssl_context())
        try:
            with opener.open(request, timeout=30) as response:
                status = response.getcode()
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raw_error = exc.read()
            raise OpenFinanceError(format_http_error(exc.code, raw_error))
        except Exception as exc:
            raise OpenFinanceError("Request failed: %s" % exc)

        if status == 204 or not raw:
            return {"status_code": status, "message": "No content"}
        text = raw.decode("utf-8")
        try:
            return json.loads(text)
        except ValueError:
            return {"status_code": status, "body": text}

    def service_base_url(self, service):
        specific_key = "%s_url" % service
        return self.config.get(specific_key) or self.config.get("base_url")

    def should_mock(self, service):
        if self.config.get("mock"):
            return True
        if service in ("accounts", "consents", "resources"):
            return not self.service_base_url(service)
        return False

    def get_ssl_context(self):
        if not self._ssl_context_loaded:
            self._ssl_context = build_ssl_context(self.config)
            self._ssl_context_loaded = True
        return self._ssl_context


def build_ssl_context(config):
    certfile = config.get("certificate")
    keyfile = config.get("certificate_key")
    if not certfile:
        return None
    context = ssl.create_default_context()
    try:
        context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    except OSError as exc:
        raise OpenFinanceError("Could not load certificate %s: %s" % (certfile, exc))
    return context


def build_opener(ssl_context=None):
    if ssl_context is None:
        return urllib.request.build_opener()
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl_context))


def join_url(base_url, path):
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def append_query(url, query):
    filtered = {}
    for key, value in (query or {}).items():
        if value is None or value == "":
            continue
        filtered[key] = value
    if not filtered:
        return url
    separator = "&" if "?" in url else "?"
    return url + separator + urllib.parse.urlencode(filtered, doseq=True)


def quote_path(value):
    return urllib.parse.quote(str(value), safe="")


def format_http_error(status, raw_error):
    if not raw_error:
        return "HTTP %s" % status
    text = raw_error.decode("utf-8", errors="replace")
    try:
        payload = json.loads(text)
        return "HTTP %s: %s" % (status, json.dumps(payload, ensure_ascii=False))
    except ValueError:
        return "HTTP %s: %s" % (status, text)


def now_zulu():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def base_envelope(path, data, total_records=1):
    return {
        "data": data,
        "links": {"self": "https://mock.openfinance.local%s" % path},
        "meta": {
            "requestDateTime": now_zulu(),
            "totalRecords": total_records,
            "totalPages": 1,
        },
        "_mock": True,
    }


def mock_response(service, method, path, data=None, query=None):
    if service == "accounts":
        return mock_accounts_response(method, path)
    if service == "consents":
        return mock_consents_response(method, path, data)
    if service == "resources":
        return mock_resources_response(path)
    if service == "participants":
        return mock_participants_response()
    return base_envelope(path, {})


def mock_accounts_response(method, path):
    account_id = "mock-account-001"
    if path == "/accounts":
        account = {
            "brandName": "Organizacao A",
            "companyCnpj": "21128159000166",
            "type": "CONTA_DEPOSITO_A_VISTA",
            "compeCode": "001",
            "branchCode": "6272",
            "number": "94088392",
            "checkDigit": "4",
            "accountId": account_id,
        }
        return base_envelope(path, [account], total_records=1)

    if path.endswith("/balances"):
        data = {
            "availableAmount": {"amount": "1000.0400", "currency": "BRL"},
            "blockedAmount": {"amount": "0.0000", "currency": "BRL"},
            "automaticallyInvestedAmount": {"amount": "250.0000", "currency": "BRL"},
            "updateDateTime": now_zulu(),
        }
        return base_envelope(path, data)

    if path.endswith("/transactions") or path.endswith("/transactions-current"):
        data = [
            {
                "transactionId": "mock-transaction-001",
                "completedAuthorisedPaymentType": "TRANSACAO_EFETIVADA",
                "creditDebitType": "DEBITO",
                "transactionName": "Transferencia Enviada",
                "type": "PIX",
                "transactionAmount": {"amount": "50.0000", "currency": "BRL"},
                "transactionDateTime": "2026-05-25T12:29:03.374Z",
                "partieCnpjCpf": "12345678901",
                "partiePersonType": "PESSOA_NATURAL",
                "partieCompeCode": "001",
                "partieBranchCode": "6272",
                "partieNumber": "67890854360",
                "partieCheckDigit": "4",
            }
        ]
        return base_envelope(path, data, total_records=1)

    data = {
        "compeCode": "001",
        "branchCode": "6272",
        "number": "24550245",
        "checkDigit": "4",
        "type": "CONTA_DEPOSITO_A_VISTA",
        "subtype": "INDIVIDUAL",
        "currency": "BRL",
    }
    return base_envelope(path, data)


def mock_consents_response(method, path, payload):
    if method == "DELETE":
        consent_id = path.rstrip("/").split("/")[-1]
        return {
            "status_code": 204,
            "data": {"consentId": consent_id, "status": "REVOKED"},
            "_mock": True,
        }

    if method == "GET":
        consent_id = path.rstrip("/").split("/")[-1]
        data = mock_consent_data(consent_id=consent_id)
        data["status"] = "AUTHORISED"
        return base_envelope(path, data)

    request_data = {}
    if isinstance(payload, dict):
        request_data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    consent_id = "urn:openfinancebrcli:%s" % uuid.uuid4()
    data = mock_consent_data(consent_id=consent_id, request_data=request_data)
    return base_envelope(path, data)


def mock_consent_data(consent_id, request_data=None):
    request_data = request_data or {}
    logged_user = request_data.get("loggedUser") or {
        "document": {"identification": "12345678901", "rel": "CPF"}
    }
    permissions = request_data.get("permissions") or [
        "ACCOUNTS_READ",
        "ACCOUNTS_BALANCES_READ",
        "ACCOUNTS_TRANSACTIONS_READ",
        "RESOURCES_READ",
    ]
    expiration = request_data.get("expirationDateTime") or "2026-12-31T23:59:59Z"
    data = {
        "consentId": consent_id,
        "creationDateTime": now_zulu(),
        "status": "AWAITING_AUTHORISATION",
        "statusUpdateDateTime": now_zulu(),
        "permissions": permissions,
        "expirationDateTime": expiration,
        "loggedUser": logged_user,
    }
    business_entity = request_data.get("businessEntity")
    if business_entity:
        data["businessEntity"] = business_entity
    return data


def mock_resources_response(path):
    data = [
        {
            "resourceId": "mock-account-001",
            "type": "ACCOUNT",
            "status": "AVAILABLE",
        }
    ]
    return base_envelope(path, data, total_records=1)


def mock_participants_response():
    return [
        {
            "OrganisationDetails": {
                "OrganisationId": "mock-org-001",
                "RegistrationNumber": "21128159000166",
                "RegisteredName": "Organizacao A",
            },
            "AuthorisationServers": [
                {
                    "CustomerFriendlyName": "Organizacao A",
                    "DeveloperPortalURI": "https://mock.openfinance.local/developers",
                    "APIResources": [
                        {
                            "APIFamilyType": "accounts",
                            "APIVersion": "2.4.2",
                            "APIEndpoint": "https://mock.openfinance.local/open-banking/accounts/v2",
                        }
                    ],
                }
            ],
            "_mock": True,
        }
    ]
