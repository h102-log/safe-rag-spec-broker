# 이어서 작업 — 2026-07-25 (2-eval 실행)

2026-07-24 세션의 다음 스텝. 이 문서만 읽어도 맥락을 잡고 바로 시작할 수 있게 정리한다.

> 참고: 이 파일은 `docs/next/...` 아래라 `execute.py`의 가드레일 로더(`docs/*.md` 비재귀 glob)에 걸리지 않는다. step 프롬프트에 주입되지 않으니 자유롭게 적어도 된다.

---

## 1. 지금까지 (2026-07-24 완료분)

- **브랜치 정리 완료(원격 삭제 1건 제외).** 확인 결과 `feat-0-rag-core`(PR #1~#3)·`feat-1-generate`(PR #4) 모두 이미 `safe-rag/main`에 머지돼 있었다. 로컬 main fast-forward + 머지된 로컬 브랜치 2개 삭제 완료. **원격 브랜치 삭제만 미완**(권한 차단): `git push safe-rag --delete feat-0-rag-core feat-1-generate` 직접 실행 필요.
- **C 페이즈 결정 6건 확정** — `docs/next/20260724/handoff.md` §3·§4의 `→ 결정:` 칸에 기록. 요지: 1차는 생성축만(Faithfulness·Answer Relevancy), judge=`claude-sonnet-5`(config `judge_model`), Langfuse 스택은 미루고 `create_score`는 no-op 안전, 평가 경로는 `search()`+`generate_answer()` 직접 조합, 데이터셋 jsonl → 결과 `eval/results/latest.json` → ci_gate는 미달 시 exit 1, 골든셋(검색축)은 2차에 프로젝트 docs 30~50문항으로.
- **`phases/2-eval` step 0~3 설계 완료** — 커밋 `2f70a57`, `feat-2-eval` 브랜치로 safe-rag에 push됨(트래킹 설정됨). step 0 `score-helper`(observability `create_score`) → step 1 `eval-dataset`(질문 jsonl+로더) → step 2 `ragas-runner`(RAGAS 채점·결과 저장·점수 push) → step 3 `ci-gate`(threshold 판정). `phases/index.json`에 `2-eval` pending 등록됨.
- **전체 pytest 67 passed** — 단, 전역 python이 아니라 **프로젝트 venv**(`.venv/Scripts/python.exe -m pytest`)로 실행해야 한다. 전역 Python312에는 fastapi 등이 없어 collection error가 난다.

## 2. 사전 체크리스트

- [ ] 원격 머지 브랜치 삭제(위 명령) — 선택이지만 하기로 했던 정리.
- [ ] step 파일 4개 검토: `phases/2-eval/step0~3.md`. 특히 step 2의 결과 파일 포맷(ci_gate 입력 계약)과 금지사항이 의도와 맞는지.
- [ ] `ragas`·`langchain-anthropic` 설치(실행 세션에서 requirements에 추가됨): 설치 후 **pyarrow가 25로 올라오면 `pip install --only-binary=:all: "pyarrow<25"` 재적용**(Smart App Control 차단, `CLAUDE.local.md`).

## 3. 본론 ① — 2-eval 실행 (harness 워크플로우 E)

```bash
.venv/Scripts/python.exe scripts/execute.py 2-eval        # 순차 실행 (venv python 필수)
.venv/Scripts/python.exe scripts/execute.py 2-eval --push # 실행 후 push
```

- execute.py가 `feat-2-eval` 브랜치를 재사용한다(이미 존재·push됨).
- step별 AC(pytest)는 실 LLM·DB·ragas 없이 통과하도록 설계됨 — 실행 자체에 API 키·DB 불필요.
- step 1의 산출물 `eval/golden/questions.jsonl`은 **사람 검수 대상** — 실행 후 질문 10~20개가 현재 색인 docs에서 답변 가능한지 직접 훑어볼 것.

## 4. 본론 ② — 실평가 1회 돌려보기 (스모크)

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
