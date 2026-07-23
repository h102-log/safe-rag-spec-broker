# 이어서 작업 — 2026-07-24 (브랜치 정리 + C 페이즈(평가) 논의·설계)

2026-07-23 실행 세션의 다음 스텝. 이 문서만 읽어도 맥락을 잡고 바로 시작할 수 있게 정리한다.

> 참고: 이 파일은 `docs/next/...` 아래라 `execute.py`의 가드레일 로더(`docs/*.md` 비재귀 glob)에 걸리지 않는다. step 프롬프트에 주입되지 않으니 자유롭게 적어도 된다.

---

## 1. 지금까지 (2026-07-23 완료분)

- **페이즈 `1-generate` 실행·검수·push 완료.** step 0~3 전부 `completed`(총 14분), 전체 pytest 67 passed + `REQUIRE_DB=1` integration 2 passed, CRITICAL 스팟체크 4건 통과(계측·서버 구성 citations·no-context 게이트·지연 import). `feat-1-generate` → `safe-rag` push 완료(트래킹 설정됨). `phases/index.json`의 `1-generate`는 `completed`.
- **로컬 환경 이슈 2건 해결 — 상세는 `CLAUDE.local.md`(커밋 안 됨, 이 머신 전용) 참조:**
  1. Smart App Control이 pyarrow 25.0.0 `_parquet` DLL 차단 → `pyarrow<25`(24.0.0) 다운그레이드로 해결. `pip install -r requirements.txt` 재실행 시 재발 가능.
  2. 5432를 `graphrag-postgres`가 점유 → pgvector를 5433 컨테이너로, `.env` `DATABASE_URL` override.
- **수동 확인 환경 준비 완료:** ingest 44청크/8문서 색인, uvicorn 8000 기동, `.env`에 `ANTHROPIC_API_KEY` 설정, BGE-M3 로컬 캐시됨.
- Swagger 수동 확인(answer `[n]`·citations·trace_id, 무관 질문 거절)은 사용자가 직접 진행하기로 함.

## 2. 사전 체크리스트

- [ ] Swagger 수동 확인이 미완이면 먼저 마무리: pgvector 5433 기동(`CLAUDE.local.md`의 docker run 명령) → `uvicorn app.api:app` → `http://localhost:8000/docs`. 첫 `/query`는 BGE-M3 메모리 로드로 수십 초 걸림.
- [ ] 확인 중 문제 발견 시: `1-generate` 후속 수정은 `feat-1-generate` 브랜치에서 `fix(1-generate): ...` 커밋으로.

## 3. 오늘의 본론 ① — 브랜치 정리 (main 머지 전략)

`feat-0-rag-core`·`feat-1-generate` 둘 다 main 미머지 상태. 정리 전략을 정하고 실행한다.

- 두 브랜치는 순차 관계(1-generate가 0-rag-core 위에 쌓임) — 사실상 하나의 선형 히스토리.
- 후보: (a) `feat-0-rag-core` → main 머지 후 `feat-1-generate` → main 순차 머지, (b) `feat-1-generate` 하나만 main에 머지(0-rag-core 커밋 포함), (c) PR 기반으로 갈지 로컬 머지로 갈지.
- push 대상 주의: `origin`은 템플릿(push 금지), 실제 repo는 `safe-rag`.
  → 결정: PR 기반 유지. 확인 결과 `feat-0-rag-core`는 이미 PR #1~#3, `feat-1-generate`는 PR #4로 `safe-rag/main`에 머지 완료 상태였다. 남은 정리만 실행: 로컬 main fast-forward, 머지된 로컬·원격 브랜치 삭제. 이후 후속 수정은 별도 `fix/...` 브랜치 → PR.

## 4. 오늘의 본론 ② — C 페이즈(평가) 논의 (ADR-006 순서: A→C→B)

착수 전 결정이 필요한 항목. 각 `→ 결정:` 칸을 채운 뒤 step 설계로 넘어간다. (TDD: 결정 → 테스트 → 구현)

1. **1차 범위** — ADR-003의 생성축(Faithfulness·Answer Relevancy)은 reference-free라 골든셋 없이 시작 가능. C 페이즈 1차를 생성축으로 한정하고 검색축(Context Precision/Recall)+골든셋은 2차로 미룰까?
   → 결정: 생성축만 1차. 골든셋 없이 즉시 착수 가능하고, ADR-006 취지(즉시 계측→B로 교정)에 부합. 검색축+골든셋은 2차.

2. **골든셋** (검색축용, 1차에 안 넣더라도 방향은 정하기) — 질문-문맥-정답 50~200개, 사람 검수 필수(ADR-003). 어떤 문서집합 기준으로 만들지(현재 색인은 프로젝트 자체 docs 8개뿐 — 평가 대상으로 적절한가? 실제 도메인 문서를 확보할지), 시작 규모는?
   → 결정: 현재 색인된 프로젝트 docs 기준 소규모(30~50문항)로 2차에 구축해 파이프라인부터 검증. 실제 도메인 문서 확보 시 교체.

3. **평가용 judge LLM** — RAGAS의 judge를 뭘로? 생성과 같은 Claude면 자기평가 편향 우려, 다른 모델이면 비용·키 관리 추가. (생성 모델은 config `generation_model=claude-opus-4-8`)
   → 결정: 생성과 다른 Claude 모델 `claude-sonnet-5` (config `judge_model`로 추가). 기존 ANTHROPIC_API_KEY 재사용으로 키 관리 추가 없음, 동일-모델 자기평가는 회피. 같은 계열 편향은 감수(필요 시 OpenAI judge로 교체 가능).

4. **Langfuse 스택 기동 여부** — ADR-004는 RAGAS 점수를 `create_score`로 trace에 push. 그런데 docker-compose는 pgvector만 있음(ponytail: Langfuse 스택은 관측 페이즈에서 추가). C 페이즈에서 Langfuse self-host를 띄울지, 아니면 점수 push는 키 없으면 no-op(기존 langfuse_setup 선례)으로 두고 스택은 뒤로 미룰지?
   → 결정: 스택 기동은 관측 페이즈로 미룸. 점수 push 코드(`create_score`)는 넣되 키 없으면 no-op(langfuse_setup 선례). C 페이즈는 점수 산출 자체에 집중.

5. **CLI·게이트 계약** — CLAUDE.md 커맨드 계약: `python -m eval.ragas_run --dataset eval/golden`(지표 → Langfuse), `python -m eval.ci_gate --threshold faithfulness=0.9`(회귀 게이트). 데이터셋 파일 포맷(jsonl?), ragas_run이 /query를 직접 호출할지 검색·생성 함수를 직접 조합할지, ci_gate의 실패 기준.
   → 결정: 데이터셋은 jsonl(`eval/golden/questions.jsonl`, 1차는 question만). ragas_run은 `search()`+`generate_answer()` 직접 조합(서버 불필요, FakeGenerator 주입 가능, @observe 계측은 함수에 붙어 있어 그대로 동작). 결과는 `eval/results/latest.json` 저장. ci_gate는 `--threshold 지표=값`(복수 허용) 파싱 → 결과 파일 비교 → 미달 시 사유 출력 + exit 1.

## 5. 결정 후 — step 설계

harness 워크플로우 C(Step 설계)대로: `phases/2-eval/`(가칭) step 초안 작성 → 사용자 피드백 → `phases/index.json`에 항목 추가 → step 파일 생성. 실행은 결정 범위에 따라 당일 또는 다음 세션.

- 설계 시 참고 선례: `phases/1-generate/step0~3.md`(자기완결성·AC 커맨드·금지사항 형식), `eval` 레이어는 `app/*`과 분리(CLAUDE.md 레이어 규칙).
- RAGAS는 무거운 신규 의존성 — 지연 import 선례(docling·FlagEmbedding·anthropic) 유지. AC는 실제 judge LLM 호출 없이 통과하도록 설계(FakeGenerator 선례).

## 6. 에러 복구 (harness 규약)

- **error**: `phases/{phase}/index.json`에서 해당 step `status`→`"pending"`, `error_message` 삭제 후 재실행.
- **blocked**: `blocked_reason` 해결 → `status`→`"pending"`, `blocked_reason` 삭제 후 재실행.
