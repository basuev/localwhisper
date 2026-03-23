import base64
import hashlib
import html as html_mod
import json
import logging
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

log = logging.getLogger(__name__)

AUTH_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
SCOPES = "openid profile email offline_access"
CALLBACK_PORT = 1455
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}/auth/callback"
TOKEN_PATH = Path.home() / ".config" / "localwhisper" / "auth.json"

_refresh_lock = threading.Lock()


def _generate_pkce() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode()
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return verifier, challenge


def _generate_state() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()


def _build_auth_url(code_challenge: str, state: str) -> str:
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "originator": "localwhisper",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def _exchange_code(code: str, verifier: str) -> dict:
    resp = requests.post(
        TOKEN_URL,
        json={
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _save_token(token_data: dict) -> None:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    token_data["expires_at"] = time.time() + token_data.get("expires_in", 3600)
    TOKEN_PATH.write_text(json.dumps(token_data))


def load_token() -> dict | None:
    if not TOKEN_PATH.exists():
        return None
    try:
        return json.loads(TOKEN_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def refresh_token(token_data: dict) -> dict | None:
    with _refresh_lock:
        try:
            resp = requests.post(
                TOKEN_URL,
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": token_data["refresh_token"],
                    "client_id": CLIENT_ID,
                },
                timeout=30,
            )
            resp.raise_for_status()
            new_data = resp.json()
            new_data.setdefault("refresh_token", token_data["refresh_token"])
            _save_token(new_data)
            return new_data
        except Exception:
            log.warning("Failed to refresh OpenAI token")
            return None


def _parse_jwt_claims(token: str) -> dict:
    try:
        payload = token.split(".")[1]
        padding = 4 - len(payload) % 4
        payload += "=" * padding
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


def get_account_id() -> str | None:
    token_data = load_token()
    if not token_data or not token_data.get("access_token"):
        return None
    claims = _parse_jwt_claims(token_data["access_token"])
    return (
        claims.get("chatgpt_account_id")
        or claims.get("https://api.openai.com/auth", {}).get("chatgpt_account_id")
    )


def get_valid_token() -> str | None:
    token_data = load_token()
    if not token_data:
        return None

    if time.time() >= token_data.get("expires_at", 0) - 60:
        token_data = refresh_token(token_data)
        if not token_data:
            return None

    return token_data.get("access_token")


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/auth/callback":
            self.send_error(404)
            return

        qs = parse_qs(parsed.query)

        error = qs.get("error", [None])[0]
        if error:
            desc = qs.get("error_description", [""])[0]
            log.error("OAuth error: %s - %s", error, desc)
            self.server.auth_code = None
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            safe_error = html_mod.escape(error)
            self.wfile.write(f"<html><body><p>Login failed: {safe_error}</p></body></html>".encode())
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        state = qs.get("state", [None])[0]
        if state != self.server.expected_state:
            log.error("OAuth state mismatch")
            self.server.auth_code = None
            self.send_error(400)
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        self.server.auth_code = qs.get("code", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body><p>Login successful. You can close this tab.</p></body></html>")

        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, format, *args):
        pass


def login() -> bool:
    verifier, challenge = _generate_pkce()
    state = _generate_state()

    try:
        server = HTTPServer(("127.0.0.1", CALLBACK_PORT), _CallbackHandler)
    except OSError:
        log.error("Port %d already in use, login already in progress?", CALLBACK_PORT)
        return False
    server.auth_code = None
    server.expected_state = state

    url = _build_auth_url(challenge, state)
    log.info("Opening browser for OpenAI login: %s", url)
    webbrowser.open(url)

    server.timeout = 120
    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()
    server_thread.join(timeout=130)

    server.server_close()

    if not server.auth_code:
        log.error("OAuth login timed out or failed")
        return False

    try:
        token_data = _exchange_code(server.auth_code, verifier)
        _save_token(token_data)
        log.info("OpenAI login successful")
        return True
    except Exception:
        log.exception("Failed to exchange OAuth code")
        return False
