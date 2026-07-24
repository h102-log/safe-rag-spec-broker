"""eval.dataset.load_questions — jsonl 로더 + golden 데이터셋 회귀."""
import json
from pathlib import Path

from eval.dataset import load_questions


def _write_jsonl(path, questions):
    path.write_text(
        "\n".join(json.dumps({"question": q}, ensure_ascii=False) for q in questions),
        encoding="utf-8",
    )


def test_load_questions_returns_list(tmp_path):
    f = tmp_path / "questions.jsonl"
    _write_jsonl(f, ["질문1", "질문2"])
    assert load_questions(f) == ["질문1", "질문2"]


def test_load_questions_accepts_directory(tmp_path):
    _write_jsonl(tmp_path / "questions.jsonl", ["질문1"])
    assert load_questions(tmp_path) == ["질문1"]


def test_load_questions_skips_blank_lines(tmp_path):
    f = tmp_path / "questions.jsonl"
    f.write_text('{"question": "a"}\n\n  \n{"question": "b"}\n', encoding="utf-8")
    assert load_questions(f) == ["a", "b"]


def test_golden_questions_file_loads():
    questions = load_questions(Path(__file__).parent.parent / "eval" / "golden")
    assert len(questions) >= 10
    assert all(isinstance(q, str) and q for q in questions)
