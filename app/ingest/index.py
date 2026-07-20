"""Chunk + embedding → pgvector 색인. 오프라인 인덱싱의 종착점(ADR-001).

멱등성 CRITICAL: 같은 문서를 재색인해도 행이 중복되면 검색이 오염된다.
(source, chunk_index) UNIQUE + ON CONFLICT DO UPDATE로 upsert한다.

conn을 인자로 받아 DB 드라이버 import를 CLI(__main__)로 격리한다 — parse/chunk/embed
선례처럼 소비 측이 무거운/외부 의존성 없이 이 모듈을 import할 수 있게 한다.
"""
from __future__ import annotations

from app.ingest.chunk import Chunk
from app.ingest.embed import Embedder

# BGE-M3 dense 차원(ADR-005). 스키마 vector(N)과 임베더 dim이 일치해야 한다.
EMBED_DIM = 1024


def ensure_schema(conn) -> None:
    """vector 확장 + chunks 테이블 + HNSW 인덱스 생성(멱등)."""
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS chunks (
                id bigserial PRIMARY KEY,
                source text NOT NULL,
                page int,
                chunk_index int NOT NULL,
                text text NOT NULL,
                embedding vector({EMBED_DIM}),
                UNIQUE (source, chunk_index)
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw "
            "ON chunks USING hnsw (embedding vector_cosine_ops)"
        )
    conn.commit()


def _vector_literal(vec: list[float]) -> str:
    # pgvector 텍스트 포맷 '[a,b,c]' → ::vector 캐스팅. 드라이버 어댑터 등록 없이
    # 버전 독립적으로 벡터를 넘긴다.
    return "[" + ",".join(map(str, vec)) + "]"


def index_chunks(chunks: list[Chunk], embedder: Embedder, conn) -> int:
    """chunks를 임베딩해 pgvector에 upsert. upsert된 행 수를 반환한다."""
    if not chunks:
        return 0
    vecs = embedder.embed_texts([c.text for c in chunks])
    rows = [
        (c.source, c.page, c.chunk_index, c.text, _vector_literal(v))
        for c, v in zip(chunks, vecs)
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO chunks (source, page, chunk_index, text, embedding)
            VALUES (%s, %s, %s, %s, %s::vector)
            ON CONFLICT (source, chunk_index) DO UPDATE
            SET page = EXCLUDED.page,
                text = EXCLUDED.text,
                embedding = EXCLUDED.embedding
            """,
            rows,
        )
    conn.commit()
    return len(rows)
