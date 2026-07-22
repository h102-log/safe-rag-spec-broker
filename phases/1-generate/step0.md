# Step 0: observe-generation-helper

## 읽어야 할 파일

먼저 아래 파일들을 읽고 프로젝트의 아키텍처와 설계 의도를 파악하라:

- `/docs/ARCHITECTURE.md`
- `/docs/ADR.md` (특히 ADR-004: 관측 = Langfuse, 키 미설정 시 no-op)
- `/docs/next/20260722/handoff.md` (특히 미결 4번의 결정: 토큰·비용 계측 포함)
- `observability/langfuse_setup.py` — 이 step에서 수정할 파일. `_noop_observe` / `_resolve_observe` / `get_trace_id()`의 no-op 안전 패턴을 꼼꼼히 읽어라. 새 함수도 정확히 같은 패턴을 따라야 한다.

## 작업

`observability/langfuse_setup.py`에 함수 하나를 추가한다:

```python
def update_generation(model: str, input_tokens: int, output_tokens: int) -> None:
    """활성 Langfuse generation span에 모델명과 토큰 usage를 기록.

    @observe(as_type="generation") 컨텍스트 안에서 호출해야 한다.
    계측이 no-op(키 미설정/미설치)이면 아무것도 하지 않는다.
    """
```

구현 규칙:

- `observe is _noop_observe`이면 즉시 return — `get_trace_id()`와 동일한 가드.
- Langfuse v3 우선: `from langfuse import get_client` → `get_client().update_current_generation(model=..., usage_details={"input": input_tokens, "output": output_tokens})`. ImportError 시 v2 폴백: `from langfuse.decorators import langfuse_context` → `langfuse_context.update_current_observation(model=..., usage={"input": input_tokens, "output": output_tokens})`.
- 전체를 try/except로 감싸 어떤 예외도 밖으로 새지 않게 한다. 이유: CRITICAL — Langfuse가 없거나 실패해도 온라인 경로가 죽으면 안 된다(ADR-004, `get_trace_id()` 선례).
- 토큰만 기록하면 비용은 Langfuse가 모델 단가로 자동 계산하므로 비용 계산 코드는 쓰지 마라.

테스트 `tests/test_langfuse_setup.py` (신규):

- 키 미설정(no-op) 상태에서 `update_generation("claude-opus-4-8", 10, 20)` 호출이 예외 없이 조용히 통과하는지.
- `get_trace_id()`가 no-op 상태에서 None을 반환하는지(기존 동작 회귀 방지, 이 파일에 테스트가 아직 없으므로 함께 고정).

## Acceptance Criteria

```bash
python -m pytest tests/test_langfuse_setup.py -q   # 신규 테스트 통과
pytest                                             # 전체 스위트 무손상 (integration은 기본 deselect)
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - ARCHITECTURE.md 디렉토리 구조를 따르는가? (observability 레이어만 수정)
   - ADR 기술 스택을 벗어나지 않았는가?
   - CLAUDE.md CRITICAL 규칙을 위반하지 않았는가? (키 없이 import·호출 가능해야 함)
3. 결과에 따라 `phases/1-generate/index.json`의 해당 step을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "산출물 한 줄 요약"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 (API 키, 외부 인증, 수동 설정 등) → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `langfuse`를 모듈 최상단에서 import하지 마라. 이유: langfuse 미설치 환경에서 import가 깨진다 — 반드시 함수 내부에서 지연 import(기존 파일의 선례).
- `app/` 하위 코드를 수정하지 마라. 이유: 이 step은 observability 레이어만 다룬다. app 쪽 사용처는 step 1에서 배선한다.
- 비용(달러) 계산 로직을 추가하지 마라. 이유: Langfuse가 모델명+usage로 자동 계산한다.
- 기존 테스트를 깨뜨리지 마라.
