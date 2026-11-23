"""회원가입·로그인·로그아웃과 토큰 확인 (테스트용 가상 계정)."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from openbook.api.auth import hash_password, token_hash, verify_password
from openbook.api.deps import get_db
from openbook.api.main import app
from openbook.db import AuthSession, Base, User, create_db_engine, make_session_factory

EMAIL = "writer@example.test"
PASSWORD = "test-pass-1234"


@pytest.fixture
def env(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'auth.db'}")
    Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)

    def _db():
        with sessions() as s:
            yield s

    app.dependency_overrides[get_db] = _db
    yield TestClient(app), sessions
    app.dependency_overrides.clear()
    engine.dispose()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_password_hash():
    h = hash_password(PASSWORD)
    assert PASSWORD not in h and h.startswith("scrypt$")
    assert verify_password(PASSWORD, h) and not verify_password("wrong-pass", h)
    assert not verify_password(PASSWORD, None) and not verify_password(PASSWORD, "garbage")


def test_signup_login_logout(env):
    client, sessions = env
    res = client.post(
        "/auth/signup", json={"email": "  Writer@Example.test ", "password": PASSWORD}
    )
    assert res.status_code == 201
    token = res.json()["token"]
    assert res.json()["user"]["email"] == EMAIL  # 소문자·공백 정리
    assert client.get("/auth/me", headers=_auth(token)).json()["email"] == EMAIL

    with sessions() as s:  # 비밀번호·토큰 원문은 저장하지 않는다
        user = s.scalars(select(User)).one()
        assert PASSWORD not in user.password_hash
        assert s.get(AuthSession, token_hash(token)) is not None
        assert s.scalars(select(AuthSession.token_hash)).one() != token

    again = client.post("/auth/signup", json={"email": EMAIL, "password": PASSWORD})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "EMAIL_TAKEN"

    login = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert login.status_code == 200
    token2 = login.json()["token"]
    assert client.post("/auth/logout", headers=_auth(token2)).status_code == 204
    assert client.get("/auth/me", headers=_auth(token2)).status_code == 401
    assert client.get("/auth/me", headers=_auth(token)).status_code == 200  # 다른 세션은 유지


def test_wrong_credentials_same_message(env):
    client, _ = env
    client.post("/auth/signup", json={"email": EMAIL, "password": PASSWORD})
    wrong = client.post("/auth/login", json={"email": EMAIL, "password": "nope-nope"})
    unknown = client.post("/auth/login", json={"email": "who@example.test", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json()["detail"]["code"] == "INVALID_CREDENTIALS"


def test_signup_validation(env):
    client, _ = env
    weak = client.post("/auth/signup", json={"email": EMAIL, "password": "short"})
    assert weak.status_code == 422 and weak.json()["detail"]["code"] == "WEAK_PASSWORD"
    assert (
        client.post(
            "/auth/signup", json={"email": "not-an-email", "password": PASSWORD}
        ).status_code
        == 422
    )


def test_protected_routes_need_valid_unexpired_token(env):
    client, sessions = env
    assert client.get("/contracts").status_code == 401
    assert (
        client.get("/contracts", headers={"X-User-Id": "u1"}).status_code == 401
    )  # 임시 방식은 막힘
    assert client.get("/contracts", headers=_auth("made-up")).status_code == 401
    assert client.get("/contracts", headers={"Authorization": "Basic abc"}).status_code == 401

    token = client.post("/auth/signup", json={"email": EMAIL, "password": PASSWORD}).json()["token"]
    assert client.get("/contracts", headers=_auth(token)).json() == []
    with sessions.begin() as s:
        s.get(AuthSession, token_hash(token)).expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert client.get("/contracts", headers=_auth(token)).status_code == 401


def test_users_only_see_their_own_contracts(env):
    client, _ = env
    a = client.post("/auth/signup", json={"email": "a@example.test", "password": PASSWORD}).json()
    b = client.post("/auth/signup", json={"email": "b@example.test", "password": PASSWORD}).json()
    from openbook.db import Contract

    with env[1].begin() as s:
        s.add(Contract(id="ka", user_id=a["user"]["id"], title="가상", status="처리중"))
    assert [c["id"] for c in client.get("/contracts", headers=_auth(a["token"])).json()] == ["ka"]
    assert client.get("/contracts", headers=_auth(b["token"])).json() == []
    assert client.get("/contracts/ka", headers=_auth(b["token"])).status_code == 404


def test_local_auth_switch_only_on_sqlite(env, monkeypatch):
    client, sessions = env
    monkeypatch.setenv("OPENBOOK_AUTH_DISABLED", "1")
    me = client.get("/auth/me").json()  # 토큰 없이도 로컬 사용자
    assert me["email"] == "local@openbook.invalid" and me["auth_disabled"] is True
    assert client.get("/contracts").status_code == 200
    with sessions() as s:
        assert s.get(User, "local-user") is not None

    monkeypatch.setenv("OPENBOOK_AUTH_DISABLED", "0")
    assert client.get("/contracts").status_code == 401  # 끄면 다시 로그인 필요


def test_local_auth_switch_ignored_on_other_databases(monkeypatch):
    from openbook.api.deps import auth_disabled

    class FakeDB:
        def get_bind(self):
            from sqlalchemy.engine import make_url

            return type("B", (), {"url": make_url("postgresql+psycopg://u:p@h/db")})()

    monkeypatch.setenv("OPENBOOK_AUTH_DISABLED", "1")
    assert auth_disabled(FakeDB()) is False
