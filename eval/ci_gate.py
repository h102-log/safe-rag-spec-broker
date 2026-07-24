"""RAGAS 회귀 게이트 — 결과 파일의 집계 지표를 임계값과 비교.

`python -m eval.ci_gate --threshold faithfulness=0.9` (CLAUDE.md 커맨드 계약).

- 입력은 ragas_run이 남긴 결과 파일(`eval/results/latest.json`)의 `metrics` 키뿐이다 —
  LLM·DB·ragas 어디에도 의존하지 않는다(CI에서 무거운 의존성 없이 판정만 재실행).
- 보수적으로 실패한다: 결과 파일이 없거나 지정 지표가 결과에 없으면 통과가 아니라 exit 1.
  "평가를 안 돌렸는데 통과"를 막는 것이 회귀 게이트의 존재 이유다.
"""
from __future__ import annotations

RESULTS_PATH = "eval/results/latest.json"


def parse_thresholds(specs: list[str]) -> dict[str, float]:
    """["faithfulness=0.9", "answer_relevancy=0.7"] → {지표: 임계값}. 형식 오류는 예외."""
    thresholds: dict[str, float] = {}
    for spec in specs:
        if "=" not in spec:
            raise ValueError(f"threshold 형식 오류(=필요): {spec!r}")
        name, _, raw = spec.partition("=")
        thresholds[name.strip()] = float(raw)  # 숫자 아니면 ValueError
    return thresholds


def check(metrics: dict[str, float], thresholds: dict[str, float]) -> list[str]:
    """위반 사유 목록. 통과면 빈 리스트."""
    reasons = []
    for name, threshold in thresholds.items():
        if name not in metrics:
            reasons.append(f"{name}: 결과에 없음 (threshold={threshold}) - 게이트 실패")
        elif metrics[name] < threshold:
            reasons.append(f"{name}: {metrics[name]:.3f} < {threshold} - 미달")
    return reasons


def main(argv: list[str] | None = None) -> int:
    """0=통과, 1=미달. 사유는 stdout에 출력."""
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(prog="eval.ci_gate")
    parser.add_argument(
        "--threshold",
        nargs="+",
        action="extend",
        required=True,
        metavar="지표=값",
        help="예: --threshold faithfulness=0.9 answer_relevancy=0.7 (복수·반복 허용)",
    )
    parser.add_argument("--results", default=RESULTS_PATH)
    args = parser.parse_args(argv)

    thresholds = parse_thresholds(args.threshold)

    path = Path(args.results)
    if not path.exists():
        print(f"결과 파일 없음: {path} - 평가를 먼저 실행하라 (게이트 실패)")
        return 1

    metrics = json.loads(path.read_text(encoding="utf-8")).get("metrics", {})
    reasons = check(metrics, thresholds)
    if reasons:
        for reason in reasons:
            print(reason)
        return 1

    print("게이트 통과: " + ", ".join(f"{n}>={t}" for n, t in thresholds.items()))
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
