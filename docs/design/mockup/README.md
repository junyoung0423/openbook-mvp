# 오픈북 화면 시안 v1

원본(사람이 보는 캔버스): https://claude.ai/artifact/DD9ywp5Rrssoh1vbv8A2Yu

이 폴더는 캔버스의 화면 파일 사본입니다. 구현 방법은 `docs/work-orders/05-디자인-적용.md` 0-1절을 봅니다.

- `*.dc.html`의 inline style 값(색·크기·간격·모서리)이 디자인 기준입니다.
- `{{ }}`, `<sc-for>`, `<sc-if>`, `<dc-import>`는 시안 도구 문법입니다. 구현할 때 JSX 반복·조건·컴포넌트로 바꿉니다.
- 글꼴 주소 `/_blob/...`는 캔버스 안에서만 열립니다. 구현에서는 `pretendard` npm 패키지를 씁니다.
- 숫자·문장은 데모 1(`data/samples/demo/`) 엔진 출력을 붙여 넣은 예시입니다. 구현에서는 API 값을 씁니다.
