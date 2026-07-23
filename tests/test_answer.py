"""generate_answer 검증 — DB·LLM 없이 (no-context 게이트·프롬프트 구성·서버 구성 citations)."""
from app.generate.answer import REFUSAL, generate_answer
from app.generate.llm import Generated
from app.retrieve.search import Retrieved


class FakeGenerator:
    """호출 여부와 받은 system/prompt를 기록 — test_generate.py의 FakeGenerator 선례."""

    def __init__(self) -> None:
        self.called = False
        self.system: str | None = None
        self.prompt: str | None = None

    def generate(self, system: str, prompt: str) -> Generated:
        self.called = True
        self.system = system
        self.prompt = prompt
        return Generated(
            text="보증기간은 24개월입니다. [1]",
            model="fake-model",
            input_tokens=10,
            output_tokens=5,
        )


def _chunk(score: float, text: str = "보증기간은 24개월", page: int | None = 3) -> Retrieved:
    return Retrieved(text=text, source="manual.pdf", page=page, score=score)


def test_empty_retrieved_refuses_without_llm():
    gen = FakeGenerator()

    result = generate_answer("보증기간은?", [], gen)

    assert result.answer == REFUSAL
    assert result.citations == []
    assert not gen.called


def test_all_low_score_refuses_without_llm():
    gen = FakeGenerator()

    result = generate_answer("보증기간은?", [_chunk(0.1), _chunk(0.05)], gen)

    assert result.answer == REFUSAL
    assert result.citations == []
    assert not gen.called


def test_answer_with_server_built_citations():
    gen = FakeGenerator()
    retrieved = [_chunk(0.9), _chunk(0.5, text="반품은 14일 이내")]

    result = generate_answer("보증기간은?", retrieved, gen)

    assert result.answer == "보증기간은 24개월입니다. [1]"
    # citations는 LLM 출력이 아니라 입력 retrieved 그대로 (지어낸 출처 차단)
    assert result.citations == retrieved


def test_prompt_contains_numbered_chunks():
    gen = FakeGenerator()

    generate_answer("보증기간은?", [_chunk(0.9)], gen)

    assert gen.prompt is not None
    assert "[1]" in gen.prompt
    assert "보증기간은 24개월" in gen.prompt
    assert "manual.pdf" in gen.prompt
    assert "보증기간은?" in gen.prompt
