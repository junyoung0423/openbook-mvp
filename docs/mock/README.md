# 목 데이터 (process_contract 응답 예시)

`process_contract`가 돌려주는 JSON의 **실제 모양**입니다. 프론트 화면과 API 응답은 이 모양을 기준으로 만듭니다.
계약서는 모두 **가상 샘플**(`data/samples/`)이고, 조건 값은 실제 모델(`solar-pro4`)이 낸 결과입니다. 모델 답은 호출마다 조금씩 달라질 수 있습니다.

| 파일 | 상황 | 화면이 해야 할 일 |
|---|---|---|
| `process_result_ok_sample_a.json` | 정상. 조건 9/9 추출, 경고 1건 | 조건 확인 화면. 경고(정해지지 않은 공제 항목)를 눈에 띄게 |
| `process_result_ok_sample_b.json` | 정상. 조건 6/9 추출, 나머지는 `not_found` | `찾지 못함` 항목에 직접 입력 칸 제공 |
| `process_result_llm_error.json` | 조항은 나뉨, 조건 추출 호출 실패 (`terms=null`, `error` 있음) | 조항 목록은 보여 주고, 조건은 "다시 시도" 또는 전부 직접 입력 |
| `process_result_no_clauses.json` | 조항을 못 나눔 (`clauses=[]`, `clause_review_needed=true`) | 사용자가 직접 나누는 화면(또는 본문 붙여넣기 안내) |

## 필드

| 필드 | 뜻 |
|---|---|
| `clause_style` | `article`(제N조) / `numbered`(N.) / `none`(규칙 실패) |
| `clause_review_needed` | `true`면 조항 분할이 불확실하니 사용자가 확인·수정하게 한다 |
| `clauses[]` | `id`, `no`, `title`, `text`(조항 본문 원문 그대로. 제목 줄 `제4조 (선급금)`은 `no`·`title`에 있으므로 빠져 있음), `type_id`, `std_clause_id` (현재 `null`) |
| `terms` | `null`이면 조건 추출을 못 한 상태. 아니면 `terms.terms[]` 9개 항목 |
| `terms.terms[].key` | `mg_amount`, `mg_pay_date`, `mg_recoup`, `mg_carryover`, `rs_rate`, `revenue_base`, `deductions`, `settlement_cycle`, `payment_day` |
| `terms.terms[].status` | `extracted` / `not_found` / `user_input` |
| `terms.terms[].value` | 항목별 형식. 금액·비율은 **문자열**, 선택값은 영문 값, 공제·구간은 목록 |
| `terms.terms[].source_clause_id`, `quote` | 근거 조항 id와 원문 인용. 화면에서 조항 원문과 함께 보여 준다 |
| `terms.terms[].confirmed` | 항상 `false`로 나온다. **확정은 사용자만** 한다 |
| `warnings[]` | 사용자가 확인해야 할 점. 화면에 그대로 보여 준다 (앞부분은 항목 이름. 예: `공제 항목: …`) |
| `error` | 조건 추출 호출 실패 사유 |

## 항목별 `value` 형식

| key | 형식 | 예 |
|---|---|---|
| `mg_amount` | 원 단위 금액 문자열 | `"5000000"` |
| `mg_pay_date`, `payment_day` | 계약서 문구 그대로의 문자열 | `"정산서 제공일로부터 15일 이내"` |
| `mg_recoup` | `from_rs`(RS에서 차감) / `separate`(별도) / `unknown` | |
| `mg_carryover` | `carry_over` / `refund` / `forgiven` / `unknown` | |
| `rs_rate` | 0~1 비율 문자열, 또는 구간 목록 | `"0.6"` |
| `revenue_base` | `gross`(총매출) / `net`(순매출) / `other` | |
| `deductions` | `[{"name", "rate", "amount"}]` 중 `rate`와 `amount` 중 하나만 값이 있음 | `[{"name":"결제 수수료","rate":"0.1","amount":null}]` |
| `settlement_cycle` | `monthly` / `quarterly` / `semiannual` / `other` | |

> `mg_carryover`, `settlement_cycle`의 선택지는 명세서에 정해진 값이 없어 **임시로 정한 것**입니다. 허정민 님의 계약 유형 분류(이슈 #4)로 확정됩니다. 화면에서 선택지를 하드코딩하지 말고 스키마 파일에서 읽으세요.
