# 이어서 작업 — 2026-07-22 (다음 페이즈: 생성 레이어 A)

2026-07-21 설계 세션(`/grill-me`)에서 확정한 다음 스텝. 결정과 그 근거는 **ADR-006** 참조. 이 문서는 착수 전 **아직 안 정한 설계 항목**을 담는다.

> 참고: 이 파일은 `docs/next/...` 아래라 `execute.py` 가드레일 로더(`docs/*.md` 비재귀 glob)에 안 걸린다 — step 프롬프트에 주입 안 되니 자유롭게 적어도 된다.

---

## 1. 정해진 것 (ADR-006)

- **다음 페이즈 = 생성 레이어 `app/generate`.** 순서: **A(생성) → C(평가) → B(검색 고도화).**
- **산출물:** `POST /query`가 청크 뭉치 대신 **`{인용 근거 + LLM 생성 답변}`** 을 반환.
- **근거:** 생성은 제품 그 자체(CLAUDE.md CRITICAL: 근거 기반 + 인용). B는 A에 **비의존** — B는 문맥 지표만 필요하고 생성 답변을 안 먹는다.
- **가시성:** FastAPI 자동 `/docs`(Swagger)에서 확인. **UI 코드 0줄.** 웹 UI는 범위 밖·나중.

## 2. 시작 전 정해야 할 것 (미결 4)

착수 전에 아래 4개를 정하고 각 `→ 결정:` 칸을 채운다. (TDD니까 결정 → 테스트 → 구현)

1. **LLM 선택** — Claude vs OpenAI (CLAUDE.md: 교체 가능). 기본값 하나 정하고 인터페이스로 갈아끼우게 할까? (임베딩 ADR-005의 `Embedder` Protocol 선례를 그대로 따라 `Generator` 인터페이스 하나 두면 됨)
   → 결정:

2. **인용을 답변에 어떻게 박나** — `Retrieved.source`/`page`(이미 검색이 반환 중)를 답변에 어떻게 노출? 후보: (a) 답변 문장 뒤 `[source:page]` 인라인, (b) `{answer, citations[]}` 분리 필드. 분리 필드가 평가·프론트 양쪽에 유리할 가능성.
   → 결정:

3. **근거 부실 / no-context 처리** — 검색 결과가 비었거나 관련 없을 때(예: 최고 score가 임계 이하). "모르겠다/문서에 없음"으로 거절할지, 임계 컷을 둘지. **CLAUDE.md CRITICAL: 파라메트릭 기억으로 지어내기 금지** — 할루시네이션 방지가 이 항목의 핵심.
   → 결정:

4. **`@observe` 계층** — `generate` span을 기존 `query` trace 아래에 어떻게 중첩? `search` span과 형제로? 프롬프트·토큰·비용까지 계측? **CLAUDE.md CRITICAL: 계측 없는 LLM 호출 금지.** (Langfuse 키 없으면 no-op이어도 데코레이터는 유지)
   → 결정:

## 3. AC (검증 기준)

- `app/generate/...` + 테스트. 생성 로직은 **실제 LLM 호출 없이** 계약/오버라이드로 검증한다 (`/query`의 `embedder=Depends` 오버라이드 선례).
- `POST /query` 응답에 **`answer` + `citations`** 필드 존재. citation의 `source`가 **retrieved context에서 온 것인지** assert (지어낸 출처 차단).
- no-context 케이스 테스트: 관련 문맥 없을 때 거절/폴백이 동작하는지.
- 수동 확인: `uvicorn app.api:app` → `http://localhost:8000/docs` → `/query` Try it out.

## 4. 주의

- 이건 **새 페이즈**다(0-rag-core 아님). harness 규약 커밋(`feat(...)` → `chore(... output)`)과 phase 인덱스는 착수 시 정리.
- `.env`에 LLM API 키 필요(선택한 provider). 키는 `.env`로만, 커밋 금지.
