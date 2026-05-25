import base64
import time
import urllib.parse
import urllib.request

from .config import load_token_cache, save_token_cache


DEFAULT_TOKEN_TTL = 3600


class AuthError(Exception):
    """Raised when OAuth2 client_credentials fails."""


def get_access_token(config, scope=None, force=False, ssl_context=None, timeout=30):
    cache_key = build_cache_key(config, scope)
    cache = load_token_cache()

    if not force:
        cached = cache.get(cache_key)
        if cached and token_is_valid(cached):
            result = dict(cached)
            result["source"] = "cache"
            return result

    if should_mock_token(config):
        token = mock_token(scope)
    else:
        token = request_client_credentials_token(
            config,
            scope=scope,
            ssl_context=ssl_context,
            timeout=timeout,
        )

    cache[cache_key] = token
    save_token_cache(cache)
    return dict(token)


def should_mock_token(config):
    if config.get("mock"):
        return True
    configured_oauth = bool(config.get("token_url") or config.get("client_id") or config.get("client_secret"))
    configured_service = bool(
        config.get("base_url")
        or config.get("accounts_url")
        or config.get("consents_url")
        or config.get("resources_url")
    )
    return not configured_oauth and not configured_service


def build_cache_key(config, scope):
    token_url = config.get("token_url") or "mock-token-url"
    client_id = config.get("client_id") or "mock-client"
    scope_text = scope or ""
    return "|".join((token_url, client_id, scope_text))


def token_is_valid(token):
    expires_at = float(token.get("expires_at") or 0)
    return bool(token.get("access_token")) and expires_at > time.time() + 60


def mock_token(scope=None):
    now = int(time.time())
    token = {
        "access_token": "mock-access-token-%s" % now,
        "token_type": "Bearer",
        "expires_in": DEFAULT_TOKEN_TTL,
        "expires_at": now + DEFAULT_TOKEN_TTL,
        "scope": scope or "openid accounts consents resources",
        "source": "mock",
    }
    return token


def request_client_credentials_token(config, scope=None, ssl_context=None, timeout=30):
    token_url = config.get("token_url")
    client_id = config.get("client_id")
    client_secret = config.get("client_secret")
    if not token_url:
        raise AuthError("Missing token_url. Run: openfinance config set --token-url URL")
    if not client_id or not client_secret:
        raise AuthError("Missing client_id/client_secret. Run: openfinance config set --client-id ID --client-secret SECRET")

    form = {"grant_type": "client_credentials"}
    if scope:
        form["scope"] = scope
    body = urllib.parse.urlencode(form).encode("utf-8")

    credentials = ("%s:%s" % (client_id, client_secret)).encode("utf-8")
    basic = base64.b64encode(credentials).decode("ascii")
    request = urllib.request.Request(
        token_url,
        data=body,
        headers={
            "Accept": "application/json",
            "Authorization": "Basic %s" % basic,
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "openfinance-br-cli",
        },
        method="POST",
    )

    opener = build_opener(ssl_context)
    try:
        with opener.open(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except Exception as exc:
        raise AuthError("OAuth2 client_credentials request failed: %s" % exc)

    try:
        import json

        data = json.loads(payload)
    except Exception as exc:
        raise AuthError("Token endpoint did not return valid JSON: %s" % exc)

    access_token = data.get("access_token")
    if not access_token:
        raise AuthError("Token endpoint response does not include access_token")

    expires_in = int(data.get("expires_in") or DEFAULT_TOKEN_TTL)
    now = int(time.time())
    return {
        "access_token": access_token,
        "token_type": data.get("token_type") or "Bearer",
        "expires_in": expires_in,
        "expires_at": now + expires_in,
        "scope": data.get("scope") or scope or "",
        "source": "oauth2",
    }


def build_opener(ssl_context=None):
    if ssl_context is None:
        return urllib.request.build_opener()
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl_context))
