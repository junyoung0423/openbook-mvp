import httpx
import pytest

from openbook.terms import llm
from openbook.terms.llm import UpstageClient

SECRET_TEXT = "제4조 갑은 을에게 선급금 5,000,000원을 지급한다"


def _fake_post(status, body):
    def post(url, **kw):
        return httpx.Response(status, text=body, request=httpx.Request("POST", url))

    return post


def test_error_message_has_no_response_body(monkeypatch):
    # 오류 응답이 요청 내용(계약서)을 되돌려 줘도 예외 메시지에 들어가지 않는다
    monkeypatch.setattr(llm.httpx, "post", _fake_post(400, f'{{"echo": "{SECRET_TEXT}"}}'))
    with pytest.raises(RuntimeError) as e:
        UpstageClient(api_key="test").complete("sys", SECRET_TEXT)
    assert "HTTP 400" in str(e.value)
    assert "선급금" not in str(e.value)


def test_unreadable_response_has_fixed_message(monkeypatch):
    monkeypatch.setattr(llm.httpx, "post", _fake_post(200, SECRET_TEXT))
    with pytest.raises(RuntimeError) as e:
        UpstageClient(api_key="test").complete("sys", "x")
    assert "선급금" not in str(e.value)


def test_ok_response_returns_content(monkeypatch):
    body = '{"choices": [{"message": {"content": "답"}}]}'
    monkeypatch.setattr(llm.httpx, "post", _fake_post(200, body))
    assert UpstageClient(api_key="test").complete("sys", "x") == "답"
