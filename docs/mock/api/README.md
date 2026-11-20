# API 응답 목 데이터 (2단계 화면용)

PR #24 엔드포인트의 **실제 응답**입니다. 가상 샘플 `data/samples/sample_a.txt`를 실제 모델(`solar-pro4`)로 처리해 저장한 뒤 API로 받았습니다. 모델 답은 호출마다 조금씩 달라질 수 있습니다.

| 파일 | 요청 | 화면 |
|---|---|---|
| `terms_get_sample_a.json` | `GET /contracts/{id}/terms` | 조건 확인·수정 화면 첫 상태. `unconfirmed_required`에 든 항목에 "확인해 주세요" 표시 |
| `terms_put_confirm_sample_a.json` | `PUT /contracts/{id}/terms` (필수 5개 확정) | `all_confirmed: true`면 정산서 입력으로 넘어가는 버튼을 연다 |
| `terms_put_invalid.json` | `PUT` 잘못된 값 (비율을 숫자 0.7로 보냄) | `detail.message`를 입력 칸 아래에 보여 준다. 아무것도 저장되지 않음 |
| `comparison_sample_a.json` | `GET /contracts/{id}/comparison` | 비교 요약. 표준 조항별 `status`, `difference`, 양쪽 인용, `disclaimer` |
| `qa_found.json` | `POST /contracts/{id}/qa` | 답 + 근거 조항 인용 + `notice`(법률 자문 아님) |
| `qa_amount_question.json` | 금액을 묻는 질문 | 금액을 계산해 주지 않고 대조 화면으로 안내한다 |
| `qa_not_found.json` | 계약서에 근거가 없는 질문 | `found: false`, 인용 없음 |
| `statement_paste_sample.json` | `POST /contracts/{id}/statements/paste` | 정산서 입력 폼을 채워 보여 주고, `rows[].note`가 있는 줄(넣지 않은 이유)을 따로 표시 |
| `error_not_found.json` | 없는 계약서 | 오류 형식 예시 |

## 요청 형식

- 모든 요청에 임시로 `X-User-Id` 헤더가 필요합니다. 로그인이 붙으면 바뀝니다.
- `PUT /contracts/{id}/terms`
  - 본문: `{"terms": [{"key": "rs_rate", "value": "0.7", "confirmed": true}]}`
  - 보낸 key만 바뀝니다. `value`가 `null`이면 값은 두고 확정 여부만 바꿉니다.
  - 금액·비율은 **문자열**로 보냅니다.
- `POST /contracts/{id}/qa`: `{"question": "…"}` (500자까지)
- `POST /contracts/{id}/statements/paste`: `{"text": "…"}` (20,000자까지)
- `GET /contracts/{id}/comparison?refresh=true`: 비교를 다시 실행합니다. 기본은 저장해 둔 결과를 씁니다.

## 오류 형식

`{"detail": {"code": "...", "message": "..."}}`

| code | HTTP | 뜻 |
|---|---|---|
| `UNAUTHENTICATED` | 401 | 사용자 없음 |
| `CONTRACT_NOT_FOUND` | 404 | 없거나 내 계약서가 아님 |
| `NO_CLAUSES` | 409 | 아직 조항이 없음 (처리 중) |
| `INVALID_TERM` | 422 | 조건 값이 형식에 맞지 않음, 또는 찾지 못한 조건을 값 없이 확정하려 함 |
| `LLM_FAILED` | 502 | AI 호출 실패. "다시 시도" 버튼 |

요청 모양 자체가 틀리면 FastAPI 기본 422가 나옵니다. 이때 `detail`은 목록입니다.
