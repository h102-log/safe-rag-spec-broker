# Step 4: indexing

## 읽어야 할 파일

- `/docs/ARCHITECTURE.md`, `/docs/ADR.md` — ADR-001 (pgvector/HNSW)
- `app/ingest/parse.py`, `app/ingest/chunk.py`, `app/ingest/embed.py` — step 1~3
- `app/config.py` (`database_url`), `docker-compose.yml` — step 0

이전 step 코드를 읽고 `ParsedDoc`/`Chunk`/`Embedder` 구조를 파악한 뒤 작업하라.

## 작업

**`app/ingest/index.py`** + pgvector 스키마 + `python -m app.ingest` CLI.

- 스키마: 테이블 `chunks(id bigserial primary key, source text, page int, chunk_index int, text text, embedding vector(1024))`. `embedding`에 HNSW 인덱스(`vector_cosine_ops`). `CREATE EXTENSION IF NOT EXISTS vector`.
- 인터페이스:

  ```python
  def ensure_schema(conn) -> None: ...
  def index_chunks(chunks: list[Chunk], embedder: Embedder, conn) -> int:   # upsert된 행 수 반환
      ...
  ```

- **`app/ingest/__main__.py`**: `python -m app.ingest --source <dir>` → 디렉토리 순회, 각 파일에 parse→chunk→embed→index 실행.
- CRITICAL (멱등성/데이터 무결성): 같은 문서를 재색인해도 행이 중복되면 안 된다. `(source, chunk_index)`에 UNIQUE 제약 + `ON CONFLICT (source, chunk_index) DO UPDATE`. 이유: 문서 갱신 시 중복 청크는 검색을 오염시킨다.
- `database_url`은 `app/config.py`에서 읽어라.

## Acceptance Criteria

```bash
docker compose up -d db
pytest -m integration tests/test_index.py -q
```

`test_index.py`(`@pytest.mark.integration`): `ensure_schema` → 샘플 `Chunk` N개 `index_chunks` → 테이블 count == N → **같은 입력 재색인 → count 여전히 N**(멱등성 검증). DB에 접속 불가하면 `pytest.skip`.

## 검증 절차

1. `docker compose up -d db` 후 AC 실행.
2. 체크리스트: 디렉토리 구조 / ADR-001(pgvector·HNSW) / 멱등성 CRITICAL.
3. step 4 index.json 업데이트. DB를 띄울 수 없으면 `blocked`(`blocked_reason`: docker/pgvector 미가용) 후 중단.

## 금지사항

- 검색(`search`)·`/query`를 여기서 만들지 마라. 이유: step 5.
- 하이브리드(BM25)·리랭킹을 넣지 마라. 이유: ADR-002 — 이 페이즈는 dense만.
- INSERT-only로 재색인 중복을 방치하지 마라. 이유: 멱등성 CRITICAL.
- 기존 테스트를 깨뜨리지 마라.
