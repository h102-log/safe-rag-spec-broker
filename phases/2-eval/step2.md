# Step 2: ragas-runner

## 읽어야 할 파일

먼저 아래 파일들을 읽고 프로젝트의 아키텍처와 설계 의도를 파악하라:

- `/docs/ARCHITECTURE.md`
- `/docs/ADR.md` (특히 ADR-003: 생성축 Faithfulness·Answer Relevancy / ADR-004: 점수를 trace에 push)
- `/docs/next/20260724/handoff.md` (§4 결정 1·3·4·5: 생성축만, judge=claude-sonnet-5, 점수 push는 no-op 안전, 함수 직접 조합·결과 파일 경로)
- `app/retrieve/search.py` — `search()`와 `Retrieved` 데이터클래스. 평가 파이프라인이 호출하는 검색 함수.
- `app/generate/answer.py` — `generate_answer()`, `Answered`, no-context 게이트(`no_context_threshold`). 평가 파이프라인이 호출하는 생성 함수.
- `app/generate/llm.py` — `Generator` Protocol, `get_generator()` 팩토리. 지연 import 선례.
- `app/ingest/embed.py` — `Embedder` Protocol, `get_embedder()`. Answer Relevancy용 임베딩으로 재사용한다.
- `app/config.py` — `judge_model` 설정 추가 위치. `generation_model` 선례.
- `observability/langfuse_setup.py` — step 0에서 추가된 `create_score(trace_id=, name=, value=)`, 기존 `observe`·`get_trace_id`.
- `eval/dataset.py` — step 1의 `load_questions`.
- `tests/test_answer.py` — `FakeGenerator` 선례(실 LLM 없이 테스트).
- `requirements.txt`

이전 step에서 만들어진 코드를 꼼꼼히 읽고, 설계 의도를 이해한 뒤 작업하라.

## 작업

### 1. `eval/ragas_run.py` (신규)

`python -m eval.ragas_run --dataset eval/golden` 진입점(CLAUDE.md 커맨드 계약).

```python
@dataclass
class Sample:
    question: str
    answer: str
    contexts: list[str]      # 검색된 청크 텍스트
    trace_id: str | None     # Langfuse no-op이면 None


def build_samples(
    questions: list[str], *, generator=None, searcher=None
) -> list[Sample]:
    """질문마다 search() + generate_answer()를 조합해 평가 샘플 생성."""


def score_samples(samples: list[Sample]) -> list[dict[str, float]]:
    """RAGAS 생성축 채점 — 샘플별 {faithfulness, answer_relevancy}."""


def main(argv: list[str] | None = None) -> None: ...
```

구현 규칙:

- `build_samples`: 기본값은 `generator=get_generator()`, `searcher=search` — 인자로 주입 가능하게 해 테스트에서 fake로 대체한다(FakeGenerator 선례). 질문당 처리를 `@observe(name="eval_query")` 함수로 감싸 search·generate가 자식 span이 되게 하고, 그 컨텍스트 안에서 `get_trace_id()`로 trace_id를 수집한다(키 없으면 None — 그대로 둔다).
- `score_samples`: `ragas`의 evaluate에 Faithfulness·Answer Relevancy 메트릭을 전달한다. judge LLM은 `langchain-anthropic`의 `ChatAnthropic(model=get_settings().judge_model)`을 ragas의 LLM 래퍼로 감싸 전달한다. Answer Relevancy에 필요한 임베딩은 `get_embedder()`(BGE-M3)를 ragas 임베딩 인터페이스에 맞춘 어댑터로 전달한다 — OpenAI 키를 요구하지 마라. 설치된 ragas 버전의 실제 API에 맞춰 구현하라.
- `main`: `--dataset`(기본 `eval/golden`) → `load_questions` → `build_samples` → `score_samples` → ① 샘플별 점수를 `create_score`로 trace에 push(trace_id가 None이면 건너뜀, ADR-004) ② 집계(평균)와 샘플별 점수를 `eval/results/latest.json`에 저장 ③ stdout에 지표 평균 요약 출력.
- `eval/results/latest.json` 포맷 (step 3 ci_gate의 입력 계약):

```json
{
  "n": 15,
  "metrics": { "faithfulness": 0.93, "answer_relevancy": 0.87 },
  "samples": [ { "question": "...", "faithfulness": 0.9, "answer_relevancy": 0.8, "trace_id": null } ]
}
```

- `ragas`·`langchain_anthropic`·`datasets` import는 **`score_samples` 내부로 지연**한다. 이유: 미설치 환경에서 `import eval.ragas_run`과 `build_samples` 테스트가 가능해야 한다(docling·FlagEmbedding·anthropic 지연 선례).
- `.gitignore`에 `eval/results/` 추가 — 실행 산출물은 커밋하지 않는다.

### 2. `app/config.py` 수정

`Settings`에 한 줄 추가:

```python
judge_model: str = "claude-sonnet-5"
```

### 3. `requirements.txt` 수정

`# Eval: RAGAS` 섹션으로 `ragas`, `langchain-anthropic` 추가.

### 4. 테스트 `tests/test_ragas_run.py` (신규)

실제 judge LLM·DB·ragas 설치 없이 검증한다:

- **import 테스트**: `import eval.ragas_run`이 ragas·langchain-anthropic 미설치 환경에서 성공하는지(지연 import 검증).
- **build_samples 테스트**: fake searcher(고정 `Retrieved` 목록 반환, `score=0.9`로 no-context 게이트 통과)와 `FakeGenerator`를 주입 → Sample의 question/answer/contexts가 기대대로 채워지는지, no-op 환경에서 trace_id가 None인지.
- `score_samples`나 `main`을 실 LLM으로 호출하는 테스트는 쓰지 마라.

## Acceptance Criteria

```bash
python -m pytest tests/test_ragas_run.py -q   # 신규 테스트 통과 (ragas·키·DB 불필요)
pytest                                        # 전체 스위트 무손상 (integration은 기본 deselect)
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - ARCHITECTURE.md 디렉토리 구조를 따르는가? (eval 레이어, app은 config 한 줄 외 무수정)
   - ADR 기술 스택을 벗어나지 않았는가? (RAGAS + Claude judge, 임베딩은 BGE-M3 재사용)
   - CLAUDE.md CRITICAL 규칙을 위반하지 않았는가? (온라인 검색·생성 경로는 기존 @observe 계측 그대로, 키는 .env로만)
3. 결과에 따라 `phases/2-eval/index.json`의 해당 step을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "산출물 한 줄 요약"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 (API 키, 외부 인증, 수동 설정 등) → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `ragas`·`langchain_anthropic`·`datasets`를 모듈 최상단에서 import하지 마라. 이유: 미설치 환경에서 import가 전부 깨진다(지연 import 선례).
- 검색·생성 로직을 재구현하지 마라. 이유: 평가 경로는 `search()`+`generate_answer()` 조합으로 결정됐다(handoff §4 결정 5) — app의 공개 함수만 호출한다.
- `/query` HTTP 호출로 샘플을 만들지 마라. 이유: 서버 기동 의존이 생기고 FakeGenerator 주입이 불가능해진다(handoff §4 결정 5).
- ragas 내부의 judge LLM 호출에 @observe 계측을 억지로 붙이려 하지 마라. 이유: CLAUDE.md CRITICAL의 계측 대상은 온라인 요청 경로다 — 오프라인 평가 배치의 judge 호출은 대상이 아니고, 온라인 경로(search·generate)는 이미 계측돼 있다.
- OpenAI judge 구현체를 만들지 마라. 이유: `judge_model` 설정 교체만으로 충분하도록 뒀다(YAGNI, handoff §4 결정 3).
- ci_gate(임계값 판정)를 여기 만들지 마라. 이유: step 3의 범위다.
- 기존 테스트를 깨뜨리지 마라.
