"""
STRICT NETWORK CAPABILITY

Capability: network.fetch (OUTBOUND ONLY)
No inference. No defaults. Refusal-first.

Build Prompt: CAPABILITY EXPANSION UNDER MEK
"""

from __future__ import annotations

import urllib.request
import urllib.error
import ssl
from typing import Dict, Any, Set, Optional
from dataclasses import dataclass
from enum import Enum


class NetworkRefusal(Enum):
    URL_NOT_ALLOWED = "url_not_allowed"
    METHOD_NOT_ALLOWED = "method_not_allowed"
    REDIRECT_DETECTED = "redirect_detected"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    MISSING_URL = "missing_url"
    UNSAFE_SCHEME = "unsafe_scheme"


class NetworkError(RuntimeError):
    def __init__(self, refusal: NetworkRefusal, details: str):
        self.refusal = refusal
        self.details = details
        super().__init__(f"[{refusal.value}] {details}")


ALLOWED_DOMAINS: Set[str] = {
    "api.openai.com",
    "api.anthropic.com",
    "huggingface.co",
    "pypi.org",
}

ALLOWED_METHODS: Set[str] = {"GET", "POST"}

MAX_PAYLOAD_BYTES = 1024 * 1024


@dataclass(frozen=True)
class NetworkConfig:
    allowed_domains: Set[str] = ALLOWED_DOMAINS.copy()
    allowed_methods: Set[str] = ALLOWED_METHODS.copy()
    max_payload_bytes: int = MAX_PAYLOAD_BYTES
    forbid_cookies: bool = True
    forbid_redirects: bool = True
    https_only: bool = True


def validate_url_scheme(url: str, config: NetworkConfig) -> None:
    if not url:
        raise NetworkError(
            NetworkRefusal.MISSING_URL,
            "URL required"
        )

    if config.https_only and not url.startswith("https://"):
        raise NetworkError(
            NetworkRefusal.UNSAFE_SCHEME,
            f"HTTPS required: {url}"
        )


def validate_url_allowed(url: str, config: NetworkConfig) -> None:
    from urllib.parse import urlparse

    parsed = urlparse(url)

    if not parsed.netloc:
        raise NetworkError(
            NetworkRefusal.URL_NOT_ALLOWED,
            f"Invalid URL: {url}"
        )

    domain = parsed.netloc.lower()

    if not config.allowed_domains:
        return

    for allowed in config.allowed_domains:
        if domain == allowed or domain.endswith(f".{allowed}"):
            return

    raise NetworkError(
        NetworkRefusal.URL_NOT_ALLOWED,
        f"Domain not allowed: {domain}"
    )


def validate_method(method: str, config: NetworkConfig) -> None:
    if not method:
        raise NetworkError(
            NetworkRefusal.METHOD_NOT_ALLOWED,
            "Method required"
        )

    if method.upper() not in config.allowed_methods:
        raise NetworkError(
            NetworkRefusal.METHOD_NOT_ALLOWED,
            f"Method not allowed: {method}"
        )


def validate_payload_size(payload: bytes, config: NetworkConfig) -> None:
    if len(payload) > config.max_payload_bytes:
        raise NetworkError(
            NetworkRefusal.PAYLOAD_TOO_LARGE,
            f"Payload size {len(payload)} exceeds limit {config.max_payload_bytes}"
        )


class NetworkFetch:
    consequence_level = "MEDIUM"
    required_fields = ["url", "method"]

    @staticmethod
    def execute(
        context: Dict[str, Any],
        config: Optional[NetworkConfig] = None,
    ) -> Dict[str, Any]:
        config = config or NetworkConfig()

        url = context.get("url")
        if not url:
            raise NetworkError(
                NetworkRefusal.MISSING_URL,
                "URL field required"
            )

        method = context.get("method", "GET")
        headers = context.get("headers", {})
        body = context.get("body")
        timeout = context.get("timeout", 30)

        validate_url_scheme(url, config)
        validate_url_allowed(url, config)
        validate_method(method, config)

        if body:
            if isinstance(body, str):
                body = body.encode("utf-8")
            validate_payload_size(body, config)

        if config.forbid_cookies:
            headers = {k: v for k, v in headers.items()
                     if k.lower() != "cookie"}

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED

        try:
            data = body if method.upper() == "POST" else None

            req = urllib.request.Request(
                url,
                data=data,
                headers=headers,
                method=method.upper(),
            )

            response = urllib.request.urlopen(
                req,
                timeout=timeout,
                context=ssl_context,
            )

            response_data = response.read()
            response_headers = dict(response.headers)

            response_text = None
            try:
                response_text = response_data.decode("utf-8")
            except UnicodeDecodeError:
                pass

            return {
                "status_code": response.status,
                "headers": response_headers,
                "body": response_text,
                "body_bytes": len(response_data),
                "url": url,
            }

        except urllib.error.HTTPError as e:
            response_data = e.read()
            response_text = None
            try:
                response_text = response_data.decode("utf-8")
            except UnicodeDecodeError:
                pass

            return {
                "status_code": e.code,
                "headers": dict(e.headers) if e.headers else {},
                "body": response_text,
                "body_bytes": len(response_data) if response_data else 0,
                "url": url,
                "error": str(e),
            }

        except urllib.error.URLError as e:
            if "redirect" in str(e).lower() or e.reason:
                raise NetworkError(
                    NetworkRefusal.REDIRECT_DETECTED,
                    f"Redirect detected or URL error: {e.reason}"
                )
            raise NetworkError(
                NetworkRefusal.URL_NOT_ALLOWED,
                f"Failed to fetch URL: {e.reason}"
            )

        except Exception as e:
            raise NetworkError(
                NetworkRefusal.URL_NOT_ALLOWED,
                f"Failed to fetch URL: {e}"
            )
