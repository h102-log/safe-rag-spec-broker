"""FastAPI 엔드포인트. 온라인 질의 경로는 @observe로 계측한다(CLAUDE.md CRITICAL)."""
from __future__ import annotations

from dataclasses import asdict
from uuid import uuid4

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from app.generate.answer import generate_answer
from app.generate.llm import get_generator
from app.ingest.embed import get_embedder
from app.retrieve.search import search
from observability.langfuse_setup import get_trace_id, observe

app = FastAPI(title="domain-rag-eval-obs")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class QueryRequest(BaseModel):
    question: str


@app.post("/query")
@observe(name="query")
def query(
    req: QueryRequest,
    embedder=Depends(get_embedder),
    generator=Depends(get_generator),
) -> dict:
    # embedder·generator는 Depends로 주입 — 테스트가 실제 BGE-M3 로드·Claude
    # 클라이언트 생성 없이 오버라이드할 수 있게.
    results = search(req.question, embedder=embedder)
    ans = generate_answer(req.question, results, generator)
    trace_id = get_trace_id() or str(uuid4())
    # 청크 뭉치(results) 대신 {답변 + 인용} — citations가 같은 provenance를 담는다.
    return {
        "answer": ans.answer,
        "citations": [asdict(c) for c in ans.citations],
        "trace_id": trace_id,
    }
