# 이어서 작업 — 2026-07-25 (2-eval 실행)

2026-07-24 세션의 다음 스텝. 이 문서만 읽어도 맥락을 잡고 바로 시작할 수 있게 정리한다.

> 참고: 이 파일은 `docs/next/...` 아래라 `execute.py`의 가드레일 로더(`docs/*.md` 비재귀 glob)에 걸리지 않는다. step 프롬프트에 주입되지 않으니 자유롭게 적어도 된다.

---

## 0. 내일(7/25) 할 일 — 요약

2-eval 실행은 끝났다(§3). 남은 것 세 가지, 순서대로:

1. **`eval/golden/questions.jsonl` 16문항 검수** — 각 질문이 색인 docs(PRD·ARCHITECTURE·ADR·wiki)에서 답변 가능한지 직접 확인. 이상한 문항은 수정 후 `pytest tests/test_eval_dataset.py`로 회귀 확인.
2. **실평가 스모크 1회** (§4) — pgvector 5433 기동(`CLAUDE.local.md`) 후:
   ```bash
   .venv/Scripts/python.exe -m eval.ragas_run --dataset eval/golden
   .venv/Scripts/python.exe -m eval.ci_gate --threshold faithfulness=0.9
   ```
   실 LLM 호출(질문 수만큼 비용), 첫 실행은 BGE-M3 로드로 수십 초. 지표가 낮아도 정상 — B 페이즈 베이스라인(ADR-006).
3. **`feat-2-eval` → main PR** (§5) — 검수·스모크 통과 후. 선례: PR #1~#4.

환경은 준비돼 있음: ragas 0.4.3 설치·SAC 차단 해결(§2)·전체 pytest 83 passed. 단, `pip install -r requirements.txt`를 다시 돌리면 pyarrow/torch/regex가 차단 버전으로 올라올 수 있음 — 증상 나오면 `CLAUDE.local.md`의 다운그레이드 재적용.

## 1. 지금까지 (2026-07-24 완료분)

- **브랜치 정리 완료.** 확인 결과 `feat-0-rag-core`(PR #1~#3)·`feat-1-generate`(PR #4) 모두 이미 `safe-rag/main`에 머지돼 있었다. 로컬 main fast-forward + 머지된 로컬·원격 브랜치 삭제 완료(feat-1-generate 원격은 PR 머지 시 이미 자동 삭제돼 있었음). 남은 브랜치: `main`, `feat-2-eval`뿐.
- **C 페이즈 결정 6건 확정** — `docs/next/20260724/handoff.md` §3·§4의 `→ 결정:` 칸에 기록. 요지: 1차는 생성축만(Faithfulness·Answer Relevancy), judge=`claude-sonnet-5`(config `judge_model`), Langfuse 스택은 미루고 `create_score`는 no-op 안전, 평가 경로는 `search()`+`generate_answer()` 직접 조합, 데이터셋 jsonl → 결과 `eval/results/latest.json` → ci_gate는 미달 시 exit 1, 골든셋(검색축)은 2차에 프로젝트 docs 30~50문항으로.
- **`phases/2-eval` step 0~3 설계 완료** — 커밋 `2f70a57`, `feat-2-eval` 브랜치로 safe-rag에 push됨(트래킹 설정됨). step 0 `score-helper`(observability `create_score`) → step 1 `eval-dataset`(질문 jsonl+로더) → step 2 `ragas-runner`(RAGAS 채점·결과 저장·점수 push) → step 3 `ci-gate`(threshold 판정). `phases/index.json`에 `2-eval` pending 등록됨.
- **전체 pytest 67 passed** — 단, 전역 python이 아니라 **프로젝트 venv**(`.venv/Scripts/python.exe -m pytest`)로 실행해야 한다. 전역 Python312에는 fastapi 등이 없어 collection error가 난다.

## 2. 사전 체크리스트 (2026-07-24 완료)

- [x] step 파일 4개 검토: `phases/2-eval/step0~3.md`. 참조 심볼 전부 실코드와 대조 확인, step 2↔3 결과 파일 계약(`metrics` 키) 일치. 단 하나 수정: step 2 requirements에 **`langchain-community<0.4` 핀 추가** — ragas 0.4.3이 community 0.4에서 제거된 `chat_models.vertexai`를 최상단 import해서 핀 없이는 `import ragas`가 깨짐(step2.md에 사유 명기).
- [x] `ragas` 0.4.3·`langchain-anthropic` 1.5.1 설치 완료. pyarrow는 24.0.0 유지돼 재적용 불필요. 대신 **SAC가 torch 2.13.0·regex 2026.7.19를 새로 차단**(7/23까진 잘 돌던 파일 — 클라우드 평판 갱신) → `torch==2.12.1`+`torchvision==0.27.1`+`regex==2026.6.28`로 다운그레이드 해결(`CLAUDE.local.md` 갱신). 전체 pytest **67 passed** 재확인.

## 3. 본론 ① — 2-eval 실행 보고 (2026-07-24 완료)

`.venv/Scripts/python.exe scripts/execute.py 2-eval`로 4 step 전부 성공 (21:55~22:10, exit 0, 재시도 0회).

| step | 산출물 요지 | 커밋 |
|------|------------|------|
| 0 score-helper | `create_score(trace_id,name,value)` — no-op 가드 + v3/v2 지연 import + 예외 삼킴 | `9d81632` |
| 1 eval-dataset | `eval/golden/questions.jsonl` 16문항(question만) + `eval/dataset.py` `load_questions` + 테스트 4개 | `6978c40` |
| 2 ragas-runner | `eval/ragas_run.py`(build_samples/score_samples/main), config `judge_model`, requirements Eval 섹션(`langchain-community<0.4` 핀 포함), `.gitignore` eval/results/ | `c01966e` |
| 3 ci-gate | `eval/ci_gate.py`(parse_thresholds/check/main, 보수적 exit 1) + 테스트 9개 | `761a342` |

- 검증: 전체 pytest **83 passed**(기존 67 + 신규 16), 4 deselected(integration).
- `questions.jsonl` 16문항 1차 훑기 결과 전부 색인 docs(ADR·ARCHITECTURE·PRD·wiki) 근거 질문으로 판단 — **최종 사람 검수는 남음**.
- 상세 step summary는 `phases/2-eval/index.json` 참조.

## 4. 본론 ② — 실평가 1회 돌려보기 (스모크) ← 다음 세션 시작점

step 실행이 끝나면 실제 평가를 한 번 돌려 파이프라인을 검증한다. 필요 조건:

- pgvector 5433 기동(`CLAUDE.local.md`의 docker run 명령) + 색인 존재(7/23에 44청크/8문서 색인됨, `proj2_pgdata` 볼륨에 유지).
- `.env`에 `ANTHROPIC_API_KEY`(설정돼 있음) — 생성(opus)·judge(sonnet) 실호출 발생, 질문 수만큼 비용 발생.
- 첫 실행은 BGE-M3 메모리 로드로 수십 초 걸림.

```bash
.venv/Scripts/python.exe -m eval.ragas_run --dataset eval/golden
.venv/Scripts/python.exe -m eval.ci_gate --threshold faithfulness=0.9
```

- 확인 포인트: `eval/results/latest.json` 생성·포맷, stdout 지표 요약, ci_gate exit code(통과/미달), Langfuse 키 없으니 점수 push는 조용히 no-op이어야 함.
- 지표가 낮게 나와도 당황하지 말 것 — ADR-006이 예고한 상황(검색 고도화 B 이전)이며, 그 수치가 B 페이즈의 베이스라인이 된다.

## 5. 이후 — 머지·다음 논의

- 검수·스모크까지 끝나면 `feat-2-eval` → main PR(선례: PR #1~#4).
- 다음 논의 후보: 검색축 2차(골든셋 30~50문항 작성·검수 프로세스), 관측 페이즈(Langfuse 스택 기동, ci_gate의 CI 편입).

## 6. 에러 복구 (harness 규약)

- **error**: `phases/2-eval/index.json`에서 해당 step `status`→`"pending"`, `error_message` 삭제 후 재실행.
- **blocked**: `blocked_reason` 해결 → `status`→`"pending"`, `blocked_reason` 삭제 후 재실행.
