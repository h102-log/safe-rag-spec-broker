"""FastAPI 엔드포인트. 온라인 질의 경로는 @observe로 계측한다(CLAUDE.md CRITICAL)."""
from __future__ import annotations

from dataclasses import asdict
from uuid import uuid4

from fastapi import Depends, FastAPI
from pydantic import BaseModel

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
def query(req: QueryRequest, embedder=Depends(get_embedder)) -> dict:
    # embedder는 Depends로 주입 — 테스트가 실제 BGE-M3 로드 없이 오버라이드할 수 있게.
    results = search(req.question, embedder=embedder)
    trace_id = get_trace_id() or str(uuid4())
    return {"results": [asdict(r) for r in results], "trace_id": trace_id}
