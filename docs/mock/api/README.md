# API 응답 목 데이터 (2단계 화면용)

PR #24 엔드포인트의 **실제 응답**입니다. 가상 샘플 `data/samples/sample_a.txt`를 실제 모델(`solar-pro4`)로 처리해 저장한 뒤 API로 받았습니다. 모델 답은 호출마다 조금씩 달라질 수 있습니다.

| 파일 | 요청 | 화면 |
|---|---|---|
| `terms_get_sample_a.json` | `GET /contracts/{id}/terms` | 조건 확인·수정 화면 첫 상태. `unconfirmed_required`에 든 항목에 "확인해 주세요" 표시 |
| `terms_get_sample_b.json` | `GET` (샘플 B) | 필수 조건 일부가 `not_found` (RS율·공제). 해당 칸에 직접 입력 칸을 보여 준다 |
| `terms_get_extraction_failed.json` | `GET` (조건 추출 호출 실패) | 9개 모두 `not_found`. 조항 목록은 있으니 "다시 시도" 또는 전부 직접 입력 |
| `terms_put_confirm_sample_a.json` | `PUT /contracts/{id}/terms` (필수 5개 확정) | `all_confirmed: true`면 정산서 입력으로 넘어가는 버튼을 연다 |
| `terms_put_invalid.json` | `PUT` 잘못된 값 (비율을 숫자 0.7로 보냄) | `detail.message`를 입력 칸 아래에 보여 준다. 아무것도 저장되지 않음 |
| `comparison_sample_a.json` | `GET /contracts/{id}/comparison` | 비교 요약. 표준 조항별 `status`, `difference`, 양쪽 인용, `disclaimer` |
| `qa_found.json` | `POST /contracts/{id}/qa` | 답 + 근거 조항 인용 + `notice`(법률 자문 아님) |
| `qa_amount_question.json` | 금액을 묻는 질문 | 금액을 계산해 주지 않고 대조 화면으로 안내한다 |
| `qa_not_found.json` | 계약서에 근거가 없는 질문 | `found: false`, 인용 없음 |
| `statement_paste_sample.json` | `POST /contracts/{id}/statements/paste` | 정산서 입력 폼을 채워 보여 주고, `rows[].note`가 있는 줄(넣지 않은 이유)을 따로 표시 |
| `error_not_found.json` | 없는 계약서 | 오류 형식 예시 |

## 요청 형식

- 로그인: `POST /auth/signup`·`/auth/login` `{"email", "password"}` → `{token, user}`. 이후 모든 요청에 `Authorization: Bearer <token>` (30일). `POST /auth/logout`, `GET /auth/me`. 오류: `INVALID_CREDENTIALS` 401, `EMAIL_TAKEN` 409, `WEAK_PASSWORD` 422 (8자 미만).
- `PUT /contracts/{id}/terms`
  - 본문: `{"terms": [{"key": "rs_rate", "value": "0.7", "confirmed": true}]}`
  - 보낸 key만 바뀝니다. `value`가 `null`이면 값은 두고 확정 여부만 바꿉니다.
  - 금액·비율은 **문자열**로 보냅니다.
- `POST /contracts/{id}/qa`: `{"question": "…"}` (500자까지)
- `POST /contracts/{id}/statements/paste`: `{"text": "…"}` (20,000자까지)
- `GET /contracts/{id}/comparison?refresh=true`: 비교를 다시 실행합니다. 기본은 저장해 둔 결과를 씁니다.

## 계약서·정산서·대조 (P0, 2026-11-23 추가)

| 요청 | 하는 일 |
|---|---|
| `POST /contracts` (multipart: `file`, `title` 선택) | 파일 업로드. 202와 `{id, title, status: "처리중"}`. 처리는 응답 뒤에 돈다 |
| `POST /contracts/text` `{"title", "text"}` | 본문 붙여넣기로 등록 (100,000자까지) |
| `GET /contracts`, `GET /contracts/{id}` | 목록·상태. `status`가 `조건 확인 대기`가 되면 조건 화면으로, `처리 실패`면 다시 올리기 안내 |
| `GET /contracts/{id}/clauses` | 조항 목록 |
| `DELETE /contracts/{id}` | 계약서와 조항·조건·정산서·대조 결과·Q&A를 함께 삭제 (204) |
| `POST /contracts/{id}/statements` | 정산서 저장 (본문은 `Statement`, 201) |
| `GET /contracts/{id}/statements`, `DELETE .../statements/{sid}` | 정산서 목록·삭제 |
| `GET /contracts/{id}/reconciliations` | 대조 결과. 정산서마다 `summary`(결과 문장), `breakdown`(단계별 계산), `questions`(플랫폼에 확인할 질문). 필수 조건 미확정이면 409 `TERMS_NOT_CONFIRMED` |

- 원본 파일은 서버에 저장하지 않습니다.
- 대조 결과의 `rules_version`이 `provisional-…`이면 계산 규칙이 아직 임시 안입니다 (`backend/src/openbook/engine/rules.py`).

## 오류 형식

`{"detail": {"code": "...", "message": "..."}}`

| code | HTTP | 뜻 |
|---|---|---|
| `UNAUTHENTICATED` | 401 | 사용자 없음 |
| `CONTRACT_NOT_FOUND` | 404 | 없거나 내 계약서가 아님 |
| `NO_CLAUSES` | 409 | 아직 조항이 없음 (처리 중) |
| `INVALID_TERM` | 422 | 조건 값이 형식에 맞지 않음, 또는 찾지 못한 조건을 값 없이 확정하려 함 |
| `LLM_FAILED` | 502 | AI 호출 실패. "다시 시도" 버튼 |
| `LLM_NOT_CONFIGURED` | 503 | 서버에 AI 키가 없음 (개발 환경 설정 문제). 업로드·비교·Q&A만 해당 |
| `TERMS_NOT_CONFIRMED` | 409 | 필수 조건 5개가 확정되지 않아 대조할 수 없음 |
| `STATEMENT_NOT_FOUND` | 404 | 없는 정산서 |
| `UNSUPPORTED_FILE` · `FILE_TOO_LARGE` · `EMPTY_FILE` | 415 · 413 · 422 | 업로드 파일 문제 |

요청 모양 자체가 틀리면 FastAPI 기본 422가 나옵니다. 이때 `detail`은 목록입니다.
