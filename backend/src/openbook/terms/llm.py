"""LLM 호출 인터페이스. 추출 로직은 LLMClient만 알고, 모델 교체·테스트용 가짜 구현이 쉽다.

Upstage는 OpenAI 호환 chat completions를 제공한다. 모델 이름과 주소는 환경변수로 바꾼다.
- UPSTAGE_API_KEY  (필수)
- UPSTAGE_MODEL    (기본값은 아직 실제 호출로 확인하지 않았다. 호출이 거절되면 콘솔의 모델 이름으로 바꾼다)
- UPSTAGE_BASE_URL (기본 https://api.upstage.ai/v1)

계약서 원문은 로그에 남기지 않는다. 오류 메시지에도 요청 본문을 넣지 않는다.
"""

from __future__ import annotations

import os
from typing import Protocol

import httpx
from dotenv import load_dotenv

DEFAULT_MODEL = "solar-pro4"
DEFAULT_BASE_URL = "https://api.upstage.ai/v1"


class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> str:
        """시스템·사용자 프롬프트를 보내고 모델의 텍스트 답을 돌려준다."""
        ...


class UpstageClient:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 120.0,
    ) -> None:
        if not api_key:
            raise ValueError("UPSTAGE_API_KEY가 비어 있습니다.")
        self._api_key = api_key
        self.model = model
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._timeout = timeout

    @classmethod
    def from_env(cls) -> UpstageClient:
        load_dotenv()
        return cls(
            api_key=os.environ.get("UPSTAGE_API_KEY", ""),
            model=os.environ.get("UPSTAGE_MODEL", DEFAULT_MODEL),
            base_url=os.environ.get("UPSTAGE_BASE_URL", DEFAULT_BASE_URL),
        )

    def complete(self, system: str, user: str) -> str:
        resp = httpx.post(
            self._url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self.model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=self._timeout,
        )
        if resp.status_code != 200:
            # 오류 응답이 요청 내용(계약서)을 되돌려 줄 수 있으므로 응답 본문은 넣지 않는다.
            raise RuntimeError(f"Upstage 호출 실패: HTTP {resp.status_code}")
        try:
            return resp.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise RuntimeError("Upstage 응답 형식을 읽지 못했습니다.") from None
