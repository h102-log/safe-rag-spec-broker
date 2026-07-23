"""langfuse_setup의 no-op 안전성 — 키 미설정이어도 조용히 통과해야 한다 (ADR-004)."""
from observability import langfuse_setup


def test_update_generation_noop_silent(monkeypatch):
    monkeypatch.setattr(langfuse_setup, "observe", langfuse_setup._noop_observe)
    langfuse_setup.update_generation("claude-opus-4-8", 10, 20)  # 예외 없으면 통과


def test_get_trace_id_noop_returns_none(monkeypatch):
    monkeypatch.setattr(langfuse_setup, "observe", langfuse_setup._noop_observe)
    assert langfuse_setup.get_trace_id() is None
