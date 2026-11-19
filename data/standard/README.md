# 표준계약서 데이터

표준계약서 조항을 여기에 둡니다.

- `webtoon_serial_2024.yaml`: 문화체육관광부 만화 분야 표준계약서 [별표 3] 웹툰 연재계약서, 32개 조항. 출처·옮겨 적은 방법은 [SOURCE.md](SOURCE.md).
- 코드에서는 `load_standard()`(32개 전부) 또는 `load_standard(core_only=True)`(정산 관련 6개)로 읽습니다.

## 형식 (YAML 또는 JSON)

`backend/src/openbook/comparison/standard.py`의 `load_standard()`가 읽습니다.

```yaml
clauses:
  - id: s-01            # 필수, 중복 불가
    "no": "제1조"        # 표준계약서의 조항 번호 표기 (선택). 키 no는 따옴표로 감쌉니다 (YAML에서 no는 false로 읽힘)
    title: "목적"        # 선택
    core: true          # MVP에서 비교하는 정산 관련 조항이면 true (기본 false)
    text: |             # 필수. 표준계약서 원문 그대로
      ...
```

## 지켜야 할 것
- **원문을 요약하거나 바꾸지 않습니다.** 비교 결과의 `standard_quote`는 이 원문에 글자 그대로 있어야 검증을 통과합니다.
- **출처와 라이선스를 기록합니다.** 표준계약서의 원본 문서, 발행 기관, 기준일, 이용 조건을 이 폴더에 적어 두세요. 요약이나 해설집을 바탕으로 만든 데이터라면 그 사실도 적습니다 (법률 검수를 받았는지 포함).
- 실제 계약서는 이 폴더에 두지 않습니다.
