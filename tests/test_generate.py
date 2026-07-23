"""Generator 계약·지연 import 검증 — 실제 LLM 호출 없이 (handoff AC).

이 모듈 최상단 import 자체가 지연 import 검증이다: anthropic 미설치·API 키
없는 환경에서 ClaudeGenerator를 인스턴스화하지 않는 한 import는 성공해야 한다.
"""
from app.generate.llm import ClaudeGenerator, Generated, Generator, get_generator


class FakeGenerator:
    """고정 Generated 반환 계약 검증용 — anthropic·API 키 없이 인터페이스만 확인."""

    def generate(self, system: str, prompt: str) -> Generated:
        return Generated(
            text="보증기간은 24개월입니다.",
            model="fake-model",
            input_tokens=10,
            output_tokens=5,
        )


def test_generator_contract():
    gen: Generator = FakeGenerator()

    result = gen.generate("문맥에 근거해 답하라.", "보증기간은?")

    assert isinstance(result, Generated)
    assert result.text == "보증기간은 24개월입니다."
    assert result.model == "fake-model"
    assert result.input_tokens == 10
    assert result.output_tokens == 5


def test_import_lazy_without_anthropic():
    # 최상단 import가 이미 성공했음을 고정 — 심볼 존재만 확인한다.
    # ClaudeGenerator() 인스턴스화·실제 API 호출은 금지(스텝 규칙).
    assert callable(get_generator)
    assert callable(ClaudeGenerator)
