"""계측 진입점.

Langfuse 키가 설정돼 있으면 langfuse의 `@observe`를 그대로 export하고,
없으면 함수를 통과시키는 no-op 데코레이터를 export한다.

CRITICAL: 키가 없거나 langfuse가 설치돼 있지 않아도 import·호출이 실패하면 안 된다.
로컬 개발/테스트가 Langfuse 없이 가능해야 하기 때문이다(CLAUDE.md, ADR-004).
"""
from __future__ import annotations

from typing import Any, Callable

from app.config import get_settings


def _noop_observe(*d_args: Any, **d_kwargs: Any):
    """`@observe`(맨몸)와 `@observe(name=...)`(호출형)을 모두 지원하는 no-op."""
    if len(d_args) == 1 and callable(d_args[0]) and not d_kwargs:
        return d_args[0]

    def _decorator(fn: Callable) -> Callable:
        return fn

    return _decorator


def _resolve_observe():
    settings = get_settings()
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return _noop_observe
    try:
        try:
            from langfuse import observe  # langfuse v3
        except ImportError:
            from langfuse.decorators import observe  # langfuse v2
        return observe
    except Exception:
        return _noop_observe


# import 시점에 1회 해석. 서버 부팅 시 .env가 로드된 뒤 app.api가 import되므로 충분.
observe = _resolve_observe()


def update_generation(model: str, input_tokens: int, output_tokens: int) -> None:
    """활성 Langfuse generation span에 모델명과 토큰 usage를 기록.

    @observe(as_type="generation") 컨텍스트 안에서 호출해야 한다.
    계측이 no-op(키 미설정/미설치)이면 아무것도 하지 않는다.
    토큰만 기록하면 비용은 Langfuse가 모델 단가로 자동 계산한다.
    """
    if observe is _noop_observe:
        return
    try:
        try:
            from langfuse import get_client  # v3

            get_client().update_current_generation(
                model=model,
                usage_details={"input": input_tokens, "output": output_tokens},
            )
        except ImportError:
            from langfuse.decorators import langfuse_context  # v2

            langfuse_context.update_current_observation(
                model=model, usage={"input": input_tokens, "output": output_tokens}
            )
    except Exception:
        pass


def get_trace_id() -> str | None:
    """활성 Langfuse trace의 id. 계측이 no-op(키 미설정/미설치)이면 None.

    @observe 컨텍스트 안에서 호출해야 현재 trace가 잡힌다.
    """
    if observe is _noop_observe:
        return None
    try:
        try:
            from langfuse import get_client  # v3

            return get_client().get_current_trace_id()
        except ImportError:
            from langfuse.decorators import langfuse_context  # v2

            return langfuse_context.get_current_trace_id()
    except Exception:
        return None
