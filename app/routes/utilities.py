"""Utility endpoints: outbound URL fetch and a network diagnostic."""

import ipaddress
import platform
import re
import subprocess
import urllib.request
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.config import get_settings

router = APIRouter(tags=["utilities"])

DEFAULT_PORTS = {"http": 80, "https": 443}
HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$"
)


class FetchRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class FetchResponse(BaseModel):
    url: str
    status_code: int
    content: str


def _is_allowed_destination(url: str) -> bool:
    try:
        parts = urlsplit(url)
        port = parts.port or DEFAULT_PORTS.get(parts.scheme)
    except ValueError:
        return False
    if parts.scheme not in DEFAULT_PORTS or not parts.hostname or parts.username or parts.password:
        return False
    host = parts.hostname.lower()
    allowed = get_settings().allowed_fetch_hosts
    return host in allowed or f"{host}:{port}" in allowed


@router.post("/fetch-url", response_model=FetchResponse)
def fetch_url(request: FetchRequest):
    # Validate destination before making any outbound request
    if not _is_allowed_destination(request.url):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL not allowed")
    settings = get_settings()
    try:
        # Use httpx and do not follow redirects to avoid SSRF via redirects
        resp = httpx.get(request.url, timeout=settings.fetch_timeout_seconds, follow_redirects=False)
        status_code = resp.status_code
        content = resp.content[: settings.max_fetch_bytes].decode("utf-8", errors="replace")
    except Exception:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Upstream request failed")

    return {"url": request.url, "status_code": status_code, "content": content}


def _is_valid_host(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return bool(HOSTNAME_RE.fullmatch(host))


@router.get("/diagnostics/ping")
def ping_host(host: str = Query(min_length=1, max_length=253)):
    # Reject inputs that look like options or contain shell metacharacters
    if host.startswith("-") or any(c in host for c in ";&|$`><\\"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid host")
    if not _is_valid_host(host):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid host")
    count_flag = "-n" if platform.system() == "Windows" else "-c"
    # Call ping without a shell and with an argument list to avoid command injection
    cmd = ["ping", count_flag, "1", host]
    try:
        result = subprocess.run(
            cmd,
            shell=False,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Ping unavailable")

    return {"host": host, "reachable": result.returncode == 0, "output": result.stdout[-2000:]}
