import pytest


@pytest.fixture(autouse=True)
def _login_required(monkeypatch):
    """로컬 .env에 OPENBOOK_AUTH_DISABLED=1이 있어도 테스트는 로그인을 켠 상태로 돈다."""
    monkeypatch.setenv("OPENBOOK_AUTH_DISABLED", "0")
