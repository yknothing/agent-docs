"""HTTP fetch utilities with retries and redirect handling."""

from __future__ import annotations

import http.client
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional, Tuple

from agent_docs.core.config import (
    DEFAULT_HTTP_TIMEOUT,
    DEFAULT_SOURCE_PROBE_TIMEOUT,
    HTTP_CLIENT_ERROR_MAX,
    HTTP_CLIENT_ERROR_MIN,
    HTTP_FETCH_LAST_ATTEMPT_INDEX,
    HTTP_FETCH_MAX_ATTEMPTS,
    HTTP_FETCH_RETRY_BASE_SLEEP_SEC,
    HTTP_HEAD_UNSUPPORTED_CODES,
    HTTP_REDIRECT_CODES,
    HTTP_SUCCESS_STATUS,
    HTTP_SUCCESS_STATUS_MAX,
    HTTP_SUCCESS_STATUS_MIN,
    UA,
)
from agent_docs.ingest.normalize import parse_charset


def http_get(url: str, timeout: int = DEFAULT_HTTP_TIMEOUT) -> Tuple[int, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        try:
            body = resp.read()
        except http.client.IncompleteRead as e:
            body = e.partial
        ctype = resp.headers.get("Content-Type", "")
        charset = parse_charset(ctype)
        text = body.decode(charset, errors="replace")
        return resp.status, ctype, text


def http_get_bytes(url: str, timeout: int = DEFAULT_HTTP_TIMEOUT) -> Tuple[int, str, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        try:
            data = resp.read()
        except http.client.IncompleteRead as e:
            data = e.partial
        ctype = resp.headers.get("Content-Type", "")
        return resp.status, ctype, data


def fetch_url(url: str, timeout: int = DEFAULT_HTTP_TIMEOUT) -> Tuple[Optional[str], Optional[str]]:
    if not url:
        return None, None
    status = HTTP_SUCCESS_STATUS
    content_type: Optional[str] = None
    text = ""
    for attempt in range(HTTP_FETCH_MAX_ATTEMPTS):
        try:
            status, content_type, text = http_get(url, timeout=timeout)
            if text:
                break
            if attempt == HTTP_FETCH_LAST_ATTEMPT_INDEX:
                break
            time.sleep(HTTP_FETCH_RETRY_BASE_SLEEP_SEC + attempt)
        except urllib.error.HTTPError as e:
            if e.code in HTTP_REDIRECT_CODES:
                location = e.headers.get("Location")
                if location:
                    return fetch_url(urllib.parse.urljoin(url, location), timeout=timeout)
            if e.code and HTTP_CLIENT_ERROR_MIN <= e.code <= HTTP_CLIENT_ERROR_MAX:
                return None, None
            if attempt == HTTP_FETCH_LAST_ATTEMPT_INDEX:
                return None, None
            time.sleep(HTTP_FETCH_RETRY_BASE_SLEEP_SEC + attempt)
        except Exception:
            if attempt == HTTP_FETCH_LAST_ATTEMPT_INDEX:
                return None, None
            time.sleep(HTTP_FETCH_RETRY_BASE_SLEEP_SEC + attempt)
    if status != HTTP_SUCCESS_STATUS or not text:
        return None, None
    if content_type:
        return text, content_type
    return text, "text/plain"


def fetch_bytes(url: str, timeout: int = DEFAULT_HTTP_TIMEOUT) -> Tuple[Optional[bytes], Optional[str]]:
    if not url:
        return None, None
    status = HTTP_SUCCESS_STATUS
    content_type: Optional[str] = None
    data = b""
    for attempt in range(HTTP_FETCH_MAX_ATTEMPTS):
        try:
            status, content_type, data = http_get_bytes(url, timeout=timeout)
            if data:
                break
            if attempt == HTTP_FETCH_LAST_ATTEMPT_INDEX:
                break
            time.sleep(HTTP_FETCH_RETRY_BASE_SLEEP_SEC + attempt)
        except urllib.error.HTTPError as e:
            if e.code in HTTP_REDIRECT_CODES:
                location = e.headers.get("Location")
                if location:
                    return fetch_bytes(urllib.parse.urljoin(url, location), timeout=timeout)
            if e.code and HTTP_CLIENT_ERROR_MIN <= e.code <= HTTP_CLIENT_ERROR_MAX:
                return None, None
            if attempt == HTTP_FETCH_LAST_ATTEMPT_INDEX:
                return None, None
            time.sleep(HTTP_FETCH_RETRY_BASE_SLEEP_SEC + attempt)
        except Exception:
            if attempt == HTTP_FETCH_LAST_ATTEMPT_INDEX:
                return None, None
            time.sleep(HTTP_FETCH_RETRY_BASE_SLEEP_SEC + attempt)
    if status != HTTP_SUCCESS_STATUS or not data:
        return None, None
    return data, content_type


def test_source_available(url: str) -> bool:
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=DEFAULT_SOURCE_PROBE_TIMEOUT) as resp:
            return HTTP_SUCCESS_STATUS_MIN <= resp.status < HTTP_SUCCESS_STATUS_MAX
    except urllib.error.HTTPError as e:
        if e.code in HTTP_HEAD_UNSUPPORTED_CODES:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            try:
                with urllib.request.urlopen(req, timeout=DEFAULT_SOURCE_PROBE_TIMEOUT) as resp:
                    return HTTP_SUCCESS_STATUS_MIN <= resp.status < HTTP_SUCCESS_STATUS_MAX
            except Exception:
                return False
        return False
    except Exception:
        return False
