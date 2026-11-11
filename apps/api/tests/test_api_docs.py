from app.main import api_docs_enabled, app


def test_api_docs_enabled_matrix(monkeypatch):
    monkeypatch.setenv('OYDP_ENABLE_API_DOCS', '0')
    monkeypatch.delenv('OYDP_OIDC_DEV_HTTP', raising=False)
    assert api_docs_enabled() is False

    monkeypatch.setenv('OYDP_ENABLE_API_DOCS', '1')
    assert api_docs_enabled() is True

    monkeypatch.delenv('OYDP_ENABLE_API_DOCS', raising=False)
    monkeypatch.setenv('OYDP_OIDC_DEV_HTTP', '1')
    assert api_docs_enabled() is True

    monkeypatch.delenv('OYDP_OIDC_DEV_HTTP', raising=False)
    monkeypatch.delenv('OYDP_ENABLE_API_DOCS', raising=False)
    assert api_docs_enabled() is False


def test_interactive_docs_follow_import_time_posture():
    # docs_url is fixed at process import; CI/unit runs without loopback OIDC leave docs closed.
    if api_docs_enabled():
        assert app.docs_url == '/docs'
        assert app.openapi_url == '/openapi.json'
    else:
        assert app.docs_url is None
        assert app.redoc_url is None
        assert app.openapi_url is None
