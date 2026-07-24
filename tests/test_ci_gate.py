"""eval.ci_gate — threshold 파싱 + 판정 + main exit code (LLM·DB·ragas 불필요)."""
import json

import pytest

from eval.ci_gate import check, main, parse_thresholds


def test_parse_thresholds_ok():
    assert parse_thresholds(["faithfulness=0.9", "answer_relevancy=0.7"]) == {
        "faithfulness": 0.9,
        "answer_relevancy": 0.7,
    }


def test_parse_thresholds_no_equals():
    with pytest.raises(ValueError):
        parse_thresholds(["faithfulness"])


def test_parse_thresholds_not_number():
    with pytest.raises(ValueError):
        parse_thresholds(["faithfulness=high"])


def test_check_passes():
    assert check({"faithfulness": 0.95}, {"faithfulness": 0.9}) == []


def test_check_below_threshold():
    assert check({"faithfulness": 0.5}, {"faithfulness": 0.9}) != []


def test_check_missing_metric():
    # 보수적 실패: 지정 지표가 결과에 없으면 위반 사유가 나와야 한다.
    assert check({}, {"faithfulness": 0.9}) != []


def _write_results(path, metrics):
    path.write_text(json.dumps({"metrics": metrics}), encoding="utf-8")


def test_main_passes(tmp_path):
    f = tmp_path / "latest.json"
    _write_results(f, {"faithfulness": 0.95})
    assert main(["--threshold", "faithfulness=0.9", "--results", str(f)]) == 0


def test_main_fails_below(tmp_path):
    f = tmp_path / "latest.json"
    _write_results(f, {"faithfulness": 0.5})
    assert main(["--threshold", "faithfulness=0.9", "--results", str(f)]) == 1


def test_main_fails_missing_results_file(tmp_path):
    f = tmp_path / "nope.json"
    assert main(["--threshold", "faithfulness=0.9", "--results", str(f)]) == 1
