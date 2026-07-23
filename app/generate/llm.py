"""프롬프트 → LLM 답변 생성. 교체 가능한 Generator 인터페이스(ADR-005 선례).

모델 교체(Claude ↔ OpenAI)가 답변 조립·API 코드 변경 없이 가능하도록,
소비 측은 구체 클래스가 아니라 `Generator` 프로토콜에만 의존한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from observability.langfuse_setup import observe, update_generation


@dataclass
class Generated:
    text: str
    model: str
    input_tokens: int
    output_tokens: int


class Generator(Protocol):
    def generate(self, system: str, prompt: str) -> Generated: ...


class ClaudeGenerator:
    """Anthropic Messages API 생성. 근거 기반 단답이 목적이라 max_tokens=2048."""

    def __init__(self, model: str | None = None) -> None:
        # anthropic SDK는 지연 import — 계약 테스트와 소비 측 import가
        # 미설치·API 키 없는 환경에서 가능해야 한다(embed.py의 FlagEmbedding 선례).
        import anthropic

        from app.config import get_settings

        settings = get_settings()
        self.model = model or settings.generation_model
        # 키가 None이면 SDK가 ANTHROPIC_API_KEY 환경변수로 폴백한다. 키는 .env로만.
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    @observe(name="generate", as_type="generation")
    def generate(self, system: str, prompt: str) -> Generated:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        # thinking 블록이 섞일 수 있으므로 text 블록만 이어붙인다(content[0] 직접 접근 금지).
        text = "".join(b.text for b in response.content if b.type == "text")
        update_generation(
            model=self.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        return Generated(
            text=text,
            model=self.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )


def get_generator() -> Generator:
    """config.generation_model 기반 팩토리. 소비 측은 반환값(Generator)에만 의존한다."""
    from app.config import get_settings

    return ClaudeGenerator(model=get_settings().generation_model)
