def test_pkce_generation():
    import base64
    import hashlib

    from localwhisper.oauth import _generate_pkce

    verifier, challenge = _generate_pkce()
    assert len(verifier) > 40
    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    assert challenge == expected


def test_build_auth_url():
    from localwhisper.oauth import _build_auth_url

    url = _build_auth_url("test_challenge", "test_state_12345678")
    assert "auth.openai.com" in url
    assert "client_id=" in url
    assert "code_challenge=test_challenge" in url
    assert "localhost%3A1455" in url or "localhost:1455" in url
    assert "%2Fauth%2Fcallback" in url or "/auth/callback" in url
    assert "S256" in url
    assert "state=test_state_12345678" in url


def test_token_save_load_roundtrip(tmp_path, monkeypatch):
    import localwhisper.oauth as oauth_mod

    token_path = tmp_path / "auth.json"
    monkeypatch.setattr(oauth_mod, "TOKEN_PATH", token_path)

    token_data = {
        "access_token": "test_access",
        "refresh_token": "test_refresh",
        "expires_in": 3600,
    }
    oauth_mod._save_token(token_data)
    loaded = oauth_mod.load_token()
    assert loaded["access_token"] == "test_access"
    assert loaded["refresh_token"] == "test_refresh"
    assert "expires_at" in loaded
