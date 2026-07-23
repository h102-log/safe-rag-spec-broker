# Step 0: score-helper

## 읽어야 할 파일

먼저 아래 파일들을 읽고 프로젝트의 아키텍처와 설계 의도를 파악하라:

- `/docs/ARCHITECTURE.md`
- `/docs/ADR.md` (특히 ADR-004: RAGAS 점수를 `create_score`로 trace에 push, 키 미설정 시 no-op)
- `/docs/next/20260724/handoff.md` (§4 결정 4: 스택 기동은 미루고 push 코드는 no-op 안전으로)
- `observability/langfuse_setup.py` — 이 step에서 수정할 파일. `_noop_observe` 가드, `update_generation`/`get_trace_id`의 v3 우선 + v2 폴백 + 지연 import + 예외 삼킴 패턴을 꼼꼼히 읽어라. 새 함수도 정확히 같은 패턴을 따라야 한다.
- `tests/test_langfuse_setup.py` — 기존 no-op 회귀 테스트. 여기에 테스트를 추가한다.

이전 step에서 만들어진 코드를 꼼꼼히 읽고, 설계 의도를 이해한 뒤 작업하라.

## 작업

`observability/langfuse_setup.py`에 함수 하나를 추가한다:

```python
def create_score(*, trace_id: str, name: str, value: float) -> None:
    """지정한 Langfuse trace에 평가 점수를 기록 (ADR-004).

    계측이 no-op(키 미설정/미설치)이면 아무것도 하지 않는다.
    """
```

구현 규칙:

- `observe is _noop_observe`이면 즉시 return — `update_generation`과 동일한 가드.
- Langfuse v3 우선: `from langfuse import get_client` → `get_client().create_score(trace_id=trace_id, name=name, value=value)`. ImportError 시 v2 폴백: `from langfuse import Langfuse` → `Langfuse().score(trace_id=trace_id, name=name, value=value)`.
- 전체를 try/except로 감싸 어떤 예외도 밖으로 새지 않게 한다. 이유: CRITICAL — Langfuse가 없거나 실패해도 평가 실행이 죽으면 안 된다(ADR-004, `update_generation` 선례).

테스트 `tests/test_langfuse_setup.py`에 추가:

- 키 미설정(no-op) 상태에서 `create_score(trace_id="t", name="faithfulness", value=0.9)` 호출이 예외 없이 조용히 통과하는지.

## Acceptance Criteria

```bash
python -m pytest tests/test_langfuse_setup.py -q   # 신규 포함 테스트 통과
pytest                                             # 전체 스위트 무손상 (integration은 기본 deselect)
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - ARCHITECTURE.md 디렉토리 구조를 따르는가? (observability 레이어만 수정)
   - ADR 기술 스택을 벗어나지 않았는가?
   - CLAUDE.md CRITICAL 규칙을 위반하지 않았는가? (키 없이 import·호출 가능해야 함)
3. 결과에 따라 `phases/2-eval/index.json`의 해당 step을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "산출물 한 줄 요약"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 (API 키, 외부 인증, 수동 설정 등) → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `langfuse`를 모듈 최상단에서 import하지 마라. 이유: langfuse 미설치 환경에서 import가 깨진다 — 반드시 함수 내부에서 지연 import(기존 파일의 선례).
- `app/`·`eval/` 하위 코드를 만들거나 수정하지 마라. 이유: 이 step은 observability 레이어만 다룬다. eval 쪽 사용처는 step 2에서 배선한다.
- Langfuse 스택(compose 서비스)을 추가하지 마라. 이유: 스택 기동은 관측 페이즈로 미룬다는 결정(handoff §4 결정 4).
- 기존 테스트를 깨뜨리지 마라.
