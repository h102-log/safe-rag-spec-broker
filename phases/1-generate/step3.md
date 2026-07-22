# Step 3: api-query

## 읽어야 할 파일

먼저 아래 파일들을 읽고 프로젝트의 아키텍처와 설계 의도를 파악하라:

- `/docs/ARCHITECTURE.md`
- `/docs/ADR.md`
- `/docs/next/20260722/handoff.md` (미결 4건의 결정 전부 — 이 step이 최종 산출물을 완성한다)
- `app/api.py` — 이 step에서 수정할 파일. `@observe(name="query")` + `embedder=Depends(get_embedder)` 오버라이드 패턴을 확인하라.
- `app/generate/llm.py` (step 1 산출: `Generator`, `get_generator`)
- `app/generate/answer.py` (step 2 산출: `generate_answer`, `Answered`, `REFUSAL`)
- `app/retrieve/search.py`
- `tests/test_query.py` — 갱신 대상. FakeEmbedder 색인→질의 integration 흐름과 `app.dependency_overrides` 사용법을 확인하라.
- `tests/conftest.py` — `conn` 픽스처(DB 미가용 시 skip, REQUIRE_DB 시 fail).

이전 step에서 만들어진 코드를 꼼꼼히 읽고, 설계 의도를 이해한 뒤 작업하라.

## 작업

### 1. `app/api.py` 수정 — `/query`가 청크 뭉치 대신 `{answer, citations, trace_id}`를 반환

```python
@app.post("/query")
@observe(name="query")
def query(
    req: QueryRequest,
    embedder=Depends(get_embedder),
    generator=Depends(get_generator),
) -> dict:
    ...
```

구현 규칙:

- 흐름: `results = search(req.question, embedder=embedder)` → `ans = generate_answer(req.question, results, generator)` → `{"answer": ans.answer, "citations": [asdict(c) for c in ans.citations], "trace_id": ...}` 반환. trace_id 처리는 기존 코드 유지.
- **`results` 필드는 제거한다.** 이유: handoff 결정 — "청크 뭉치 대신 {인용 근거 + 생성 답변}". citations가 같은 provenance(source/page/text/score)를 담는다.
- `generator`는 `Depends(get_generator)`로 주입 — 테스트가 실제 Claude 클라이언트 생성 없이 오버라이드할 수 있게(embedder 선례). 이 배선 덕에 `query` trace 아래 `search`·`generate` 형제 span 계층이 완성된다(결정 4).
- 레이어 준수: api는 retrieve(`search`)와 generate(`generate_answer`, `get_generator`)를 **조합만** 한다. 프롬프트·임계 로직을 api에 넣지 마라.

### 2. `tests/test_query.py` 갱신 (@integration 유지)

- 기존 색인→검색 흐름은 유지하되, `/query` 응답 assert를 새 형태로 교체한다.
- `FakeGenerator`(고정 답변 반환, test_answer.py 선례)를 `app.dependency_overrides[get_generator]`로 주입한다. 실제 LLM 호출 금지(handoff AC).
- 필수 assert:
  - `"answer"` 필드 존재·비어있지 않음.
  - `"citations"` 비어있지 않고, **모든 citation의 `source`가 이 테스트에서 색인한 소스 집합의 부분집합**인지 — 지어낸 출처 차단 검증(handoff AC).
  - citation에 `page` 키 존재(인용 provenance, CLAUDE.md CRITICAL).
  - `"trace_id"` 존재.
  - `"results"` 키가 더 이상 없는지.
- 테스트 종료 시 `dependency_overrides` 정리(기존 선례 따름).

### 3. 수동 확인 (가시성 — ADR-006 walking skeleton)

`uvicorn app.api:app` → `http://localhost:8000/docs` → `/query` Try it out. 실제 Claude 호출은 `.env`의 `ANTHROPIC_API_KEY`가 필요하다 — 키가 없으면 이 수동 확인은 건너뛰고 summary에 그 사실을 남긴다(키 요구로 blocked 처리하지 마라 — 자동 검증(AC)은 키 없이 통과해야 정상이다).

## Acceptance Criteria

```bash
pytest                                     # 전체 스위트 무손상 (integration 기본 deselect)
pytest -m integration tests/test_query.py -q   # pgvector 가용 시 통과 (미가용이면 skip — REQUIRE_DB 설정 시엔 fail)
```

pgvector가 로컬 5432에 없으면 0-rag-core 선례처럼 5433에 pgvector 컨테이너를 띄우고 `DATABASE_URL` override로 실행한다.

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - ARCHITECTURE.md 디렉토리 구조를 따르는가? (api는 레이어 조합만)
   - ADR 기술 스택을 벗어나지 않았는가?
   - CLAUDE.md CRITICAL 규칙을 위반하지 않았는가? (근거 기반 + 인용 + 계측 + 키는 .env로만)
3. 결과에 따라 `phases/1-generate/index.json`의 해당 step을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "산출물 한 줄 요약"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 (API 키, 외부 인증, 수동 설정 등) → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 실제 Claude API를 호출하는 테스트를 쓰지 마라. 이유: handoff AC — 계약/오버라이드로 검증한다. 키 의존 테스트는 CI를 불안정하게 만든다.
- 프롬프트 구성·no-context 임계 로직을 api.py에 넣지 마라. 이유: step 2의 `generate_answer`가 담당 — api는 조합만 한다(레이어 분리).
- `app/generate`·`app/retrieve`·`observability`의 기존 코드를 수정하지 마라. 이유: 이 step은 api 배선만 다룬다. 수정이 필요해 보이면 error로 남겨라.
- 웹 UI·프론트엔드 코드를 만들지 마라. 이유: ADR-006 — 가시성은 Swagger `/docs`로 대체, UI 코드 0줄.
- 기존 테스트를 깨뜨리지 마라(응답 형태 변경에 따른 test_query.py 갱신은 이 step의 작업 범위).
