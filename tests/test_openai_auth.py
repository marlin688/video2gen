import base64
import json
import time
from pathlib import Path

from v2g.openai_auth import (
    load_openai_auth_session,
    read_openai_auth_token_file,
)

_ACCOUNT_CLAIM = "https://api.openai.com/auth.chatgpt_account_id"


def _encode_b64url(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _make_jwt(exp_seconds: int, account_id: str) -> str:
    header = _encode_b64url({"alg": "RS256", "typ": "JWT"})
    payload = _encode_b64url({"exp": exp_seconds, _ACCOUNT_CLAIM: account_id})
    return f"{header}.{payload}.signature"


def _write_token_file(path: Path, access_token: str, refresh_token: str, expires_ms: int, account_id: str):
    content = {
        "openai": {
            "type": "oauth",
            "refresh": refresh_token,
            "access": access_token,
            "expires": expires_ms,
            "accountId": account_id,
        }
    }
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self):
        return self._payload


class _FakeHTTPClient:
    def __init__(self, response: _FakeResponse):
        self._response = response
        self.calls = 0

    def post(self, url: str, *, json: object):
        _ = url
        _ = json
        self.calls += 1
        return self._response


def test_load_openai_auth_session_without_refresh(tmp_path: Path):
    now_sec = int(time.time())
    account_id = "acct-test-1"
    token = _make_jwt(now_sec + 3600, account_id)
    token_path = tmp_path / "auth.json"
    _write_token_file(
        token_path, token, "refresh-1", (now_sec + 3600) * 1000, account_id,
    )

    session = load_openai_auth_session(
        token_path, now_ms=now_sec * 1000, refresh_window_ms=8_000,
    )

    assert session.access_token == token
    assert session.account_id == account_id
    assert session.expires_at_ms == (now_sec + 3600) * 1000


def test_load_openai_auth_session_refreshes_and_writes_back(tmp_path: Path):
    now_sec = int(time.time())
    account_id = "acct-test-2"
    old_token = _make_jwt(now_sec + 1, account_id)
    new_token = _make_jwt(now_sec + 7200, account_id)

    token_path = tmp_path / "auth.json"
    _write_token_file(
        token_path, old_token, "refresh-old", (now_sec + 1) * 1000, account_id,
    )

    fake_client = _FakeHTTPClient(
        _FakeResponse(
            200,
            {
                "access_token": new_token,
                "refresh_token": "refresh-new",
            },
        )
    )

    session = load_openai_auth_session(
        token_path,
        now_ms=(now_sec + 2) * 1000,
        refresh_window_ms=8_000,
        http_client=fake_client,
    )

    assert fake_client.calls == 1
    assert session.access_token == new_token
    assert session.account_id == account_id
    assert session.expires_at_ms == (now_sec + 7200) * 1000

    saved = read_openai_auth_token_file(token_path)
    assert saved.openai.access == new_token
    assert saved.openai.refresh == "refresh-new"
