import pytest

from app.ingest.chunk import Chunk
from app.ingest.index import EMBED_DIM, ensure_schema, index_chunks


class FakeEmbedder:
    """스키마 차원(1024)에 맞는 결정적 더미 벡터. 색인/멱등성만 검증하므로 값은 무관."""

    dim = EMBED_DIM

    def embed_texts(self, texts):
        return [[0.0] * self.dim for _ in texts]


@pytest.fixture
def conn():
    psycopg = pytest.importorskip("psycopg")
    from app.config import get_settings

    try:
        c = psycopg.connect(get_settings().database_url, connect_timeout=3)
    except psycopg.OperationalError as e:
        pytest.skip(f"pgvector DB 접속 불가: {e}")
    yield c
    with c.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS chunks")
    c.commit()
    c.close()


@pytest.mark.integration
def test_index_chunks_is_idempotent(conn):
    ensure_schema(conn)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE chunks RESTART IDENTITY")
    conn.commit()

    chunks = [
        Chunk(text=f"청크 {i}", source="doc.docx", page=None, chunk_index=i)
        for i in range(5)
    ]
    emb = FakeEmbedder()

    n = index_chunks(chunks, emb, conn)
    assert n == 5

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM chunks")
        assert cur.fetchone()[0] == 5

    # 같은 입력 재색인 → 행이 중복되지 않고 여전히 5 (멱등성 CRITICAL).
    index_chunks(chunks, emb, conn)
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM chunks")
        assert cur.fetchone()[0] == 5
