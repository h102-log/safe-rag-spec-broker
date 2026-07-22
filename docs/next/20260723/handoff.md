# 이어서 작업 — 2026-07-23 (1-generate 실행 + 검수)

2026-07-22 설계 세션의 다음 스텝. 이 문서만 읽어도 맥락을 잡고 바로 시작할 수 있게 정리한다.

> 참고: 이 파일은 `docs/next/...` 아래라 `execute.py`의 가드레일 로더(`docs/*.md` 비재귀 glob)에 걸리지 않는다. step 프롬프트에 주입되지 않으니 자유롭게 적어도 된다.

---

## 1. 지금까지 (2026-07-22 완료분)

- **미결 4건 결정 완료** — 근거·상세는 `docs/next/20260722/handoff.md`의 각 `→ 결정:` 칸에 기록됨. 요약:
  1. LLM: Claude 기본, `Generator` Protocol + `ClaudeGenerator`, config `generation_model="claude-opus-4-8"`
  2. 인용: `{answer, citations[], trace_id}` 분리 필드, citations는 retrieved에서 서버가 구성(LLM 출력 아님), 프롬프트로 `[n]` 표기 유도
  3. no-context: 임계 컷(`no_context_threshold=0.4`, 미캘리브레이션) — 미달 시 LLM 미호출 고정 거절
  4. 계측: `query` trace 아래 `search`·`generate` 형제 span, `as_type="generation"` + `update_generation(model, usage)` 헬퍼로 토큰·비용
- **페이즈 `1-generate` 설계 완료:** `phases/1-generate/index.json` + `step0~3.md` 생성, `phases/index.json`에 항목 추가(pending).
  - step 0 `observe-generation-helper` → step 1 `generator` → step 2 `answer` → step 3 `api-query` (완전 순차)
- 작업 브랜치는 `feat-0-rag-core`였음. **7/22 작성분(docs + phases)이 커밋됐는지 먼저 확인** — 안 됐으면 `docs(1-generate): 미결 4건 결정 + step 0~3 설계` 같은 conventional commit으로 커밋하고 시작.

## 2. 사전 준비 체크리스트

- [ ] 7/22 작성분 커밋 확인 (위)
- [ ] `.env`에 `ANTHROPIC_API_KEY` — **AC(자동 검증)는 키 없이 통과하도록 설계됨**. 키는 step 3의 Swagger 수동 확인과 실사용에 필요.
- [ ] pgvector 기동: `docker compose up -d db`. 로컬 5432를 타 프로젝트 postgres가 점유 중이면 **5433에 pgvector 컨테이너 + `DATABASE_URL` override** (0-rag-core step 4·5 선례).
- [ ] venv: `./.venv/Scripts/python.exe` (Python 3.12, 전체 의존성 설치됨). `anthropic`은 step 1이 requirements.txt에 추가하는 신규 의존성 — **AC는 지연 import라 미설치여도 통과**하지만, 수동 확인 전에 `pip install -r requirements.txt` 한 번 필요.

## 3. 실행

```bash
./.venv/Scripts/python.exe scripts/execute.py 1-generate          # 순차 자율 실행
./.venv/Scripts/python.exe scripts/execute.py 1-generate --push   # 실행 후 push까지
```

- `feat-1-generate` 브랜치 생성/checkout, 가드레일(CLAUDE.md + docs/*.md) 주입, step별 feat→chore 2단계 커밋, 실패 시 3회 자가 교정 — 전부 execute.py가 처리.
- **진행 방식 선택지:** 0-rag-core는 execute.py 무정지 실행 대신 "한 세션 한 step → 검증 → 승인" 체크포인트 방식으로 진행했던 선례가 있음. 이번엔 step이 4개고 스펙이 촘촘하니 execute.py 자율 실행 후 일괄 검수가 기본안. 불안하면 체크포인트 방식으로 전환해도 됨.
- push 대상 주의: `origin`은 템플릿(push 금지), 실제 repo는 `safe-rag`(main 업스트림 설정됨).

## 4. 결과 검수 체크리스트 (실행 후)

**상태·커밋:**
- [ ] `phases/1-generate/index.json` — step 0~3 전부 `completed` + summary가 산출물을 구체적으로 담는지
- [ ] `git log` — step당 `feat(1-generate): step N — <이름>` → `chore(1-generate): step N output` 쌍이 규약대로인지

**테스트:**
- [ ] `./.venv/Scripts/python.exe -m pytest -q` — 전체 통과(integration 기본 제외), 기존 스위트 무손상
- [ ] `REQUIRE_DB=1 ./.venv/Scripts/python.exe -m pytest -m integration tests/test_query.py -q` — DB 띄운 상태에서 **REQUIRE_DB로 조용한 skip=false-green 차단**하고 통과 확인

**코드 스팟체크 (CRITICAL 위반 여부):**
- [ ] `ClaudeGenerator.generate`에 `@observe(name="generate", as_type="generation")` + `update_generation` 호출 있는지 (계측 없는 LLM 호출 금지)
- [ ] `generate_answer`: citations가 retrieved에서만 구성되는지(LLM 출력 파싱 없음), 임계 미달 시 generator 미호출인지
- [ ] `app/api.py`: `results` 필드 제거됐는지, `generator=Depends(get_generator)` 주입인지, 레이어 조합만 하는지
- [ ] `anthropic` import가 `__init__` 내부 지연인지 (키·패키지 없이 import 가능)

**수동 확인 (walking skeleton 가시성):**
- [ ] `uvicorn app.api:app` → `http://localhost:8000/docs` → `/query` Try it out → `answer`(문장 끝 `[n]`)·`citations`(source/page)·`trace_id` 확인. 색인된 문서가 없으면 먼저 `python -m app.ingest --source ./docs`.
- [ ] 무관한 질문(예: "오늘 날씨") → 거절 응답(`제공된 문서에서 근거를 찾지 못했습니다.` + citations 빈 배열) 확인
- [ ] Langfuse 키 설정 시: trace 계층이 `query → search·generate(형제)`인지, generation span에 model·토큰·비용 잡히는지 (키 없으면 skip)

## 5. 에러 복구 (harness 규약)

- **error**: `phases/1-generate/index.json`에서 해당 step `status`→`"pending"`, `error_message` 삭제 후 재실행.
- **blocked**: `blocked_reason` 해결(예: API 키, DB) → `status`→`"pending"`, `blocked_reason` 삭제 후 재실행.
- 재실행은 같은 명령: `./.venv/Scripts/python.exe scripts/execute.py 1-generate` (completed step은 건너뜀).

## 6. 검수 통과 후

- [ ] `safe-rag`로 push (`--push` 안 썼으면 수동으로)
- [ ] `phases/index.json`의 `1-generate` → `completed` 자동 기록 확인
- [ ] main 머지 여부 판단 — `feat-0-rag-core`도 main 미머지 상태였음(7/20 기준). 두 브랜치 정리 전략을 이때 같이 정하면 좋음.

## 7. 그다음: C 페이즈(평가) 준비 (ADR-006 순서: A→C→B)

1-generate가 끝나면 다음은 **평가 레이어**. 착수 전 논의가 필요한 항목을 미리 적어둔다:

- **RAGAS 생성축부터** (ADR-003): Faithfulness·Answer Relevancy는 reference-free라 골든셋 없이 시작 가능 — C 페이즈 1차 범위로 적합.
- **골든셋** (검색축 Context Precision/Recall용): 질문-문맥-정답 50~200개, 사람 검수 필수. 어떤 문서집합 기준으로 만들지, 규모를 얼마로 시작할지 결정 필요.
- **연동 지점**: `python -m eval.ragas_run --dataset eval/golden` 커맨드 계약(CLAUDE.md), RAGAS 점수를 Langfuse `create_score`로 trace에 push(ADR-004), `eval/ci_gate --threshold faithfulness=0.9` 회귀 게이트.
- **평가용 LLM**: RAGAS의 judge LLM을 뭘로 할지(생성과 같은 Claude로 갈지) — 비용·편향 트레이드오프 논의.
