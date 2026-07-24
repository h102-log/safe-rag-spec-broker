"""RAGAS 생성축 러너 — 질문 → search()+generate_answer() → Faithfulness·Answer Relevancy.

`python -m eval.ragas_run --dataset eval/golden` (CLAUDE.md 커맨드 계약).

- 평가 경로는 app 공개 함수(search·generate_answer)를 직접 조합한다 — /query HTTP나
  검색·생성 재구현이 아니다(handoff §4 결정 5). @observe 계측은 그 함수들에 이미 붙어 있다.
- ragas·langchain_anthropic·datasets는 score_samples 내부로 지연 import — 미설치 환경에서
  import·build_samples가 가능해야 한다(docling·FlagEmbedding·anthropic 지연 선례).
- judge LLM은 claude-sonnet-5(config judge_model), Answer Relevancy 임베딩은 BGE-M3 재사용
  (ADR-003·handoff §4 결정 3). 점수 push는 키 없으면 no-op(ADR-004).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.generate.answer import generate_answer
from app.generate.llm import get_generator
from app.retrieve.search import search
from observability.langfuse_setup import create_score, get_trace_id, observe

RESULTS_PATH = "eval/results/latest.json"


@dataclass
class Sample:
    question: str
    answer: str
    contexts: list[str]      # 검색된 청크 텍스트
    trace_id: str | None     # Langfuse no-op이면 None


@observe(name="eval_query")
def _eval_query(question: str, generator, searcher) -> Sample:
    """질문 1건 처리 — search·generate가 이 span의 자식이 되고 trace_id를 수집한다."""
    retrieved = searcher(question)
    answered = generate_answer(question, retrieved, generator)
    return Sample(
        question=question,
        answer=answered.answer,
        contexts=[r.text for r in retrieved],
        trace_id=get_trace_id(),
    )


def build_samples(
    questions: list[str], *, generator=None, searcher=None
) -> list[Sample]:
    """질문마다 search() + generate_answer()를 조합해 평가 샘플 생성."""
    generator = generator or get_generator()
    searcher = searcher or search
    return [_eval_query(q, generator, searcher) for q in questions]


def score_samples(samples: list[Sample]) -> list[dict[str, float]]:
    """RAGAS 생성축 채점 — 샘플별 {faithfulness, answer_relevancy}."""
    from langchain_anthropic import ChatAnthropic
    from langchain_core.embeddings import Embeddings
    from ragas import EvaluationDataset, SingleTurnSample, evaluate
    from ragas.embeddings.base import LangchainEmbeddingsWrapper
    from ragas.llms.base import LangchainLLMWrapper
    from ragas.metrics import Faithfulness, ResponseRelevancy

    from app.config import get_settings
    from app.ingest.embed import get_embedder

    judge = LangchainLLMWrapper(ChatAnthropic(model=get_settings().judge_model))

    embedder = get_embedder()

    class _EmbedderAdapter(Embeddings):
        """BGE-M3 Embedder → langchain Embeddings 인터페이스(ragas가 감쌀 수 있게)."""

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return embedder.embed_texts(texts)

        def embed_query(self, text: str) -> list[float]:
            return embedder.embed_texts([text])[0]

    embeddings = LangchainEmbeddingsWrapper(_EmbedderAdapter())

    dataset = EvaluationDataset(
        samples=[
            SingleTurnSample(
                user_input=s.question, response=s.answer, retrieved_contexts=s.contexts
            )
            for s in samples
        ]
    )
    result = evaluate(
        dataset,
        metrics=[Faithfulness(), ResponseRelevancy()],
        llm=judge,
        embeddings=embeddings,
    )
    return [dict(sc) for sc in result.scores]


def main(argv: list[str] | None = None) -> None:
    import argparse
    import json
    from pathlib import Path

    from eval.dataset import load_questions

    parser = argparse.ArgumentParser(prog="eval.ragas_run")
    parser.add_argument("--dataset", default="eval/golden")
    args = parser.parse_args(argv)

    samples = build_samples(load_questions(args.dataset))
    scores = score_samples(samples)

    # ① 샘플별 점수를 trace에 push (trace_id 없으면 no-op, ADR-004)
    for sample, score in zip(samples, scores):
        if sample.trace_id is not None:
            for name, value in score.items():
                create_score(trace_id=sample.trace_id, name=name, value=value)

    # ② 집계(평균) + 샘플별 점수를 결과 파일에 저장 (step 3 ci_gate 입력 계약)
    metric_names = sorted({k for score in scores for k in score})
    metrics = {
        name: sum(score[name] for score in scores) / len(scores)
        for name in metric_names
    } if scores else {}
    output = {
        "n": len(samples),
        "metrics": metrics,
        "samples": [
            {"question": s.question, "trace_id": s.trace_id, **score}
            for s, score in zip(samples, scores)
        ],
    }
    path = Path(RESULTS_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    # ③ stdout 요약
    print(f"n={output['n']}  →  {RESULTS_PATH}")
    for name in metric_names:
        print(f"  {name}: {metrics[name]:.3f}")


if __name__ == "__main__":
    main()
