"""eval.ragas_run — 지연 import 검증 + build_samples(실 LLM·DB·ragas 없이).

score_samples·main을 실 judge LLM으로 호출하는 테스트는 두지 않는다(handoff §4·금지사항).
"""
import builtins
import importlib
import sys

from app.generate.llm import Generated
from app.retrieve.search import Retrieved


class FakeGenerator:
    """test_answer.py FakeGenerator 선례 — 실 LLM 없이 고정 답변."""

    def generate(self, system: str, prompt: str) -> Generated:
        return Generated(
            text="보증기간은 24개월입니다. [1]",
            model="fake-model",
            input_tokens=10,
            output_tokens=5,
        )


def _fake_search(question, **kwargs):
    # score=0.9로 no-context 게이트(threshold 0.4) 통과
    return [Retrieved(text="근거 텍스트", source="doc.md", page=1, score=0.9)]


def test_import_without_ragas(monkeypatch):
    """ragas·langchain_anthropic·datasets 미설치 환경에서도 import가 성공해야 한다."""
    blocked = {"ragas", "langchain_anthropic", "datasets"}
    for name in list(sys.modules):
        if name.split(".")[0] in blocked:
            monkeypatch.delitem(sys.modules, name, raising=False)

    real_import = builtins.__import__

    def guarded(name, *a, **k):
        if name.split(".")[0] in blocked:
            raise ImportError(f"blocked: {name}")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guarded)
    monkeypatch.delitem(sys.modules, "eval.ragas_run", raising=False)

    mod = importlib.import_module("eval.ragas_run")
    assert hasattr(mod, "build_samples")
    assert hasattr(mod, "score_samples")


def test_build_samples_with_fakes():
    """fake searcher·generator 주입 → Sample 채워지고, no-op 환경 trace_id는 None."""
    from eval.ragas_run import build_samples

    samples = build_samples(
        ["보증기간은?"], generator=FakeGenerator(), searcher=_fake_search
    )

    assert len(samples) == 1
    s = samples[0]
    assert s.question == "보증기간은?"
    assert s.answer == "보증기간은 24개월입니다. [1]"
    assert s.contexts == ["근거 텍스트"]
    assert s.trace_id is None
