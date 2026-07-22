# Step 2: answer

## 읽어야 할 파일

먼저 아래 파일들을 읽고 프로젝트의 아키텍처와 설계 의도를 파악하라:

- `/docs/ARCHITECTURE.md`
- `/docs/ADR.md`
- `/docs/next/20260722/handoff.md` (미결 2번·3번의 결정: 분리 필드 + 서버 구성 citations, 임계 컷 거절)
- `app/retrieve/search.py` — `Retrieved(text, source, page, score)` dataclass. 이 step의 입력 타입.
- `app/generate/llm.py` — step 1 산출물. `Generator` Protocol과 `Generated`를 사용한다.
- `app/config.py`
- `tests/test_generate.py` — step 1의 FakeGenerator 선례.

이전 step에서 만들어진 코드를 꼼꼼히 읽고, 설계 의도를 이해한 뒤 작업하라.

## 작업

### 1. `app/generate/answer.py` (신규) — 이 페이즈의 핵심 로직

```python
REFUSAL = "제공된 문서에서 근거를 찾지 못했습니다."


@dataclass
class Answered:
    answer: str
    citations: list[Retrieved]


def generate_answer(
    question: str, retrieved: list[Retrieved], generator: Generator
) -> Answered: ...
```

구현 규칙:

- **no-context 게이트 (CRITICAL — 할루시네이션 방지)**: `retrieved`가 비었거나 최고 `score`가 `get_settings().no_context_threshold` 미만이면 **generator를 호출하지 않고** `Answered(REFUSAL, [])`을 즉시 반환한다. LLM 미호출이라 비용 0이고 결정적이라 테스트 가능하다.
- **프롬프트 구성**: 통과 시 청크들을 `[1]`, `[2]`, … 번호를 붙여 나열한 문맥(각 항목에 source·page 포함)과 질문으로 user prompt를 만들고, system 프롬프트에는 반드시 다음 세 가지 지시를 담는다 — (1) 주어진 문맥에만 근거해 답하라(파라메트릭 기억 금지, CLAUDE.md CRITICAL), (2) 문맥에 답이 없으면 지어내지 말고 모른다고 답하라(임계는 넘었지만 무관한 청크만 걸린 경우의 이중 방어), (3) 답변 문장 끝에 근거 청크 번호를 `[n]` 형식으로 표기하라. 정확한 문구는 재량.
- **citations는 서버가 구성**: `citations`는 LLM에 전달한 `retrieved` 리스트를 그대로 넣는다. LLM 출력에서 출처를 파싱하거나 만들지 마라 — 지어낸 출처를 구조적으로 차단하는 게 이 설계의 핵심이다(handoff 결정 2). `[n]` 표기는 가독성용 유도일 뿐 검증하지 않는다.
- `generate_answer` 자체에는 `@observe`를 붙이지 않는다. 이유: LLM 호출 계측은 `ClaudeGenerator.generate`에 이미 있고(query→search·generate 형제 span, handoff 결정 4), 거절 경로는 LLM 호출이 없다.
- `Retrieved`는 데이터 타입으로만 import한다. `search()`를 호출하지 마라(레이어 경계 — 조합은 step 3의 api가 한다).

### 2. `app/config.py` 수정

```python
# ponytail: 임계값 미캘리브레이션 — BGE-M3 cosine 분포 실측 전. C 페이즈(RAGAS)에서 튜닝.
no_context_threshold: float = 0.4
```

### 3. 테스트 `tests/test_answer.py` (신규)

FakeGenerator(호출 여부와 받은 system/prompt를 기록)로, DB·LLM 없이 검증한다:

- 빈 `retrieved` → `answer == REFUSAL`, `citations == []`, **generator 미호출 assert**.
- 전부 저score(예: 0.1) → 동일하게 거절 + generator 미호출.
- 임계 이상 청크 존재 시 정상 경로: `answer`가 FakeGenerator 반환 텍스트와 일치, **`citations`가 입력 `retrieved`와 동일**.
- FakeGenerator가 캡처한 prompt에 청크 텍스트와 `[1]` 번호가 포함되는지(프롬프트 구성 검증).

## Acceptance Criteria

```bash
python -m pytest tests/test_answer.py -q   # 신규 테스트 통과
pytest                                     # 전체 스위트 무손상
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - ARCHITECTURE.md 디렉토리 구조를 따르는가? (`app/generate` 레이어만 수정)
   - ADR 기술 스택을 벗어나지 않았는가?
   - CLAUDE.md CRITICAL 규칙을 위반하지 않았는가? (근거 기반 답변, 인용 포함, 지어내기 차단)
3. 결과에 따라 `phases/1-generate/index.json`의 해당 step을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "산출물 한 줄 요약"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 (API 키, 외부 인증, 수동 설정 등) → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- LLM 출력에서 citations를 만들거나 파싱하지 마라. 이유: 지어낸 출처 차단이 이 설계의 핵심 — citations는 retrieved에서만 구성한다.
- `search()`를 호출하거나 `app/retrieve` 로직에 의존하지 마라(타입 import 제외). 이유: 레이어 경계 — 검색·생성 조합은 step 3의 api가 한다.
- `app/api.py`를 수정하지 마라. 이유: step 3의 범위다.
- 임계값 캘리브레이션(실측 튜닝)을 시도하지 마라. 이유: C 페이즈(RAGAS)의 범위다. 기본 0.4 + ponytail 주석으로 충분.
- 기존 테스트를 깨뜨리지 마라.
