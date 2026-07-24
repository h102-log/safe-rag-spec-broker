"""평가용 질문 데이터셋 로더 (1차: 생성축 reference-free, question만)."""
import json
from pathlib import Path


def load_questions(path: str | Path) -> list[str]:
    """jsonl에서 question 문자열 목록을 로드.

    path가 디렉토리면 그 안의 questions.jsonl을 읽는다
    (CLI 계약: --dataset eval/golden).
    """
    p = Path(path)
    if p.is_dir():
        p = p / "questions.jsonl"
    questions = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        questions.append(json.loads(line)["question"])
    return questions
