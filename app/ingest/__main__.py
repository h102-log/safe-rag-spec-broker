"""python -m app.ingest --source <dir> → 디렉토리 순회, 각 파일 parse→chunk→embed→index."""
from __future__ import annotations

import argparse
from pathlib import Path

import psycopg

from app.config import get_settings
from app.ingest.chunk import chunk_docs
from app.ingest.embed import get_embedder
from app.ingest.index import ensure_schema, index_chunks
from app.ingest.parse import parse_file


def main() -> None:
    ap = argparse.ArgumentParser(prog="app.ingest")
    ap.add_argument("--source", required=True, help="색인할 문서 디렉토리")
    args = ap.parse_args()

    embedder = get_embedder()
    total = 0
    with psycopg.connect(get_settings().database_url) as conn:
        ensure_schema(conn)
        for path in sorted(Path(args.source).rglob("*")):
            if not path.is_file():
                continue
            chunks = chunk_docs(parse_file(path))
            n = index_chunks(chunks, embedder, conn)
            total += n
            print(f"{path}: {n} chunks")
    print(f"총 {total} chunks 색인 완료")


if __name__ == "__main__":
    main()
