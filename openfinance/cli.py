import argparse
import json
import os
import re
import sys

from . import __version__
from .client import OpenFinanceClient, OpenFinanceError, SCHEMA_SOURCES
from .config import (
    ConfigError,
    config_path,
    load_config,
    masked_config,
    token_cache_path,
    update_config,
)


RESET = "\033[0m"
COLORS = {
    "key": "\033[94m",
    "string": "\033[92m",
    "number": "\033[96m",
    "literal": "\033[95m",
    "punct": "\033[90m",
}
STRING_RE = re.compile(r'("(?:\\.|[^"\\])*")(\s*:)?')
NUMBER_RE = re.compile(r"(?<![\w.-])-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?(?![\w.-])")
LITERAL_RE = re.compile(r"\b(true|false|null)\b")


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config()
        if getattr(args, "mock", False):
            config["mock"] = True
        client = OpenFinanceClient(config)
        result = args.handler(args, client, config)
        if result is not None:
            emit_json(result, color=not args.no_color)
        return 0
    except (ConfigError, OpenFinanceError, ValueError) as exc:
        emit_json({"error": str(exc)}, color=False, stream=sys.stderr)
        return 1


def build_parser():
    parser = argparse.ArgumentParser(
        prog="openfinance",
        description="CLI consumidor das APIs padronizadas do Open Finance Brasil.",
    )
    parser.add_argument("--version", action="version", version="openfinance %s" % __version__)
    parser.add_argument("--no-color", action="store_true", help="desativa cores ANSI na saida JSON")
    parser.add_argument("--mock", action="store_true", help="forca respostas mockadas")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_config_parser(subparsers)
    build_token_parser(subparsers)
    build_accounts_parser(subparsers)
    build_account_parser(subparsers)
    build_balances_parser(subparsers)
    build_transactions_parser(subparsers)
    build_consents_parser(subparsers)
    build_participants_parser(subparsers)
    build_resources_parser(subparsers)
    build_schemas_parser(subparsers)
    return parser


def build_config_parser(subparsers):
    parser = subparsers.add_parser("config", help="gerencia configuracao local")
    nested = parser.add_subparsers(dest="config_command", required=True)

    set_parser = nested.add_parser("set", help="define credenciais e URLs")
    set_parser.add_argument("--base-url")
    set_parser.add_argument("--accounts-url")
    set_parser.add_argument("--consents-url")
    set_parser.add_argument("--resources-url")
    set_parser.add_argument("--participants-url")
    set_parser.add_argument("--token-url")
    set_parser.add_argument("--client-id")
    set_parser.add_argument("--client-secret")
    set_parser.add_argument("--certificate")
    set_parser.add_argument("--certificate-key")
    set_parser.add_argument("--mock", choices=("true", "false", "yes", "no", "1", "0"))
    set_parser.set_defaults(handler=handle_config_set)

    show_parser = nested.add_parser("show", help="exibe configuracao mascarando segredos")
    show_parser.set_defaults(handler=handle_config_show)

    path_parser = nested.add_parser("path", help="exibe caminhos usados pelo CLI")
    path_parser.set_defaults(handler=handle_config_path)


def build_token_parser(subparsers):
    parser = subparsers.add_parser("token", help="obtem access_token via OAuth2 client_credentials")
    parser.add_argument("--scope", help="escopos OAuth2 separados por espaco")
    parser.add_argument("--force", action="store_true", help="ignora cache e solicita novo token")
    parser.set_defaults(handler=handle_token)


def build_accounts_parser(subparsers):
    parser = subparsers.add_parser("accounts", help="GET /accounts")
    add_pagination(parser)
    parser.add_argument("--account-type", help="filtro accountType da spec")
    parser.set_defaults(handler=handle_accounts)


def build_account_parser(subparsers):
    parser = subparsers.add_parser("account", help="GET /accounts/{id}")
    parser.add_argument("account_id")
    parser.set_defaults(handler=handle_account)


def build_balances_parser(subparsers):
    parser = subparsers.add_parser("balances", help="GET /accounts/{id}/balances")
    parser.add_argument("account_id")
    parser.set_defaults(handler=handle_balances)


def build_transactions_parser(subparsers):
    parser = subparsers.add_parser("transactions", help="GET /accounts/{id}/transactions")
    parser.add_argument("account_id")
    add_pagination(parser)
    add_transaction_filters(parser)
    parser.set_defaults(handler=handle_transactions)

    current = subparsers.add_parser(
        "transactions-current",
        help="GET /accounts/{id}/transactions-current",
    )
    current.add_argument("account_id")
    add_pagination(current)
    add_transaction_filters(current)
    current.set_defaults(handler=handle_transactions_current)


def build_consents_parser(subparsers):
    parser = subparsers.add_parser("consents", help="POST/GET/DELETE /consents")
    nested = parser.add_subparsers(dest="consents_command", required=True)

    create = nested.add_parser("create", help="POST /consents")
    create.add_argument("--payload", help="arquivo JSON de CreateConsent; use '-' para stdin")
    create.add_argument("--cpf", default="12345678901", help="CPF sem mascara para loggedUser")
    create.add_argument("--business-cnpj", help="CNPJ sem mascara para businessEntity")
    create.add_argument(
        "--permissions",
        nargs="+",
        default=[
            "ACCOUNTS_READ",
            "ACCOUNTS_BALANCES_READ",
            "ACCOUNTS_TRANSACTIONS_READ",
            "RESOURCES_READ",
        ],
    )
    create.add_argument("--expiration-date-time", default="2026-12-31T23:59:59Z")
    create.set_defaults(handler=handle_consents_create)

    get_parser = nested.add_parser("get", help="GET /consents/{consentId}")
    get_parser.add_argument("consent_id")
    get_parser.set_defaults(handler=handle_consents_get)

    delete_parser = nested.add_parser("delete", help="DELETE /consents/{consentId}")
    delete_parser.add_argument("consent_id")
    delete_parser.set_defaults(handler=handle_consents_delete)


def build_participants_parser(subparsers):
    parser = subparsers.add_parser("participants", help="GET /participants no diretorio central")
    parser.add_argument("--sandbox", action="store_true", help="usa diretorio sandbox")
    parser.add_argument("--limit", type=int, help="limita quantidade exibida quando a resposta for lista")
    parser.add_argument("--mock-response", action="store_true", help="forca mock apenas neste comando")
    parser.set_defaults(handler=handle_participants)


def build_resources_parser(subparsers):
    parser = subparsers.add_parser("resources", help="GET /resources")
    add_pagination(parser)
    parser.set_defaults(handler=handle_resources)


def build_schemas_parser(subparsers):
    parser = subparsers.add_parser("schemas", help="exibe specs OpenAPI usadas como referencia")
    parser.set_defaults(handler=handle_schemas)


def add_pagination(parser):
    parser.add_argument("--page", type=int)
    parser.add_argument("--page-size", type=int)


def add_transaction_filters(parser):
    parser.add_argument("--from-booking-date")
    parser.add_argument("--to-booking-date")
    parser.add_argument("--credit-debit-indicator", choices=("CREDITO", "DEBITO"))


def handle_config_set(args, client, config):
    updates = {
        "base_url": args.base_url,
        "accounts_url": args.accounts_url,
        "consents_url": args.consents_url,
        "resources_url": args.resources_url,
        "participants_url": args.participants_url,
        "token_url": args.token_url,
        "client_id": args.client_id,
        "client_secret": args.client_secret,
        "certificate": args.certificate,
        "certificate_key": args.certificate_key,
        "mock": args.mock,
    }
    updated = update_config(**updates)
    return {"saved": True, "path": str(config_path()), "config": masked_config(updated)}


def handle_config_show(args, client, config):
    return masked_config(config)


def handle_config_path(args, client, config):
    return {
        "config": str(config_path()),
        "token_cache": str(token_cache_path()),
    }


def handle_token(args, client, config):
    return client.token(scope=args.scope, force=args.force)


def handle_accounts(args, client, config):
    return client.accounts(
        page=args.page,
        page_size=args.page_size,
        account_type=args.account_type,
    )


def handle_account(args, client, config):
    return client.account(args.account_id)


def handle_balances(args, client, config):
    return client.balances(args.account_id)


def handle_transactions(args, client, config):
    return client.transactions(
        args.account_id,
        current=False,
        page=args.page,
        page_size=args.page_size,
        from_booking_date=args.from_booking_date,
        to_booking_date=args.to_booking_date,
        credit_debit_indicator=args.credit_debit_indicator,
    )


def handle_transactions_current(args, client, config):
    return client.transactions(
        args.account_id,
        current=True,
        page=args.page,
        page_size=args.page_size,
        from_booking_date=args.from_booking_date,
        to_booking_date=args.to_booking_date,
        credit_debit_indicator=args.credit_debit_indicator,
    )


def handle_consents_create(args, client, config):
    payload = load_payload(args.payload) if args.payload else build_consent_payload(args)
    return client.create_consent(payload)


def handle_consents_get(args, client, config):
    return client.get_consent(args.consent_id)


def handle_consents_delete(args, client, config):
    return client.delete_consent(args.consent_id)


def handle_participants(args, client, config):
    return client.participants(
        sandbox=args.sandbox,
        limit=args.limit,
        force_mock=args.mock_response,
    )


def handle_resources(args, client, config):
    return client.resources(page=args.page, page_size=args.page_size)


def handle_schemas(args, client, config):
    return SCHEMA_SOURCES


def load_payload(path):
    if path == "-":
        text = sys.stdin.read()
    else:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    return payload


def build_consent_payload(args):
    data = {
        "loggedUser": {
            "document": {
                "identification": args.cpf,
                "rel": "CPF",
            }
        },
        "permissions": args.permissions,
        "expirationDateTime": args.expiration_date_time,
    }
    if args.business_cnpj:
        data["businessEntity"] = {
            "document": {
                "identification": args.business_cnpj,
                "rel": "CNPJ",
            }
        }
    return {"data": data}


def emit_json(payload, color=True, stream=None):
    stream = stream or sys.stdout
    text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
    if color and should_color(stream):
        text = colorize_json(text)
    stream.write(text + "\n")


def should_color(stream):
    if os.environ.get("NO_COLOR"):
        return False
    return True


def colorize_json(text):
    def replace_string(match):
        value = match.group(1)
        suffix = match.group(2) or ""
        color = COLORS["key"] if suffix else COLORS["string"]
        return color + value + RESET + suffix

    text = STRING_RE.sub(replace_string, text)
    text = NUMBER_RE.sub(lambda match: COLORS["number"] + match.group(0) + RESET, text)
    text = LITERAL_RE.sub(lambda match: COLORS["literal"] + match.group(0) + RESET, text)
    return text
