"""ParsedDoc → 검색 단위 청크. 토큰 기준 분할 + provenance 전파.

인용 추적이 청킹에서 끊기면 안 되므로 source/page를 각 Chunk로 전파한다(CLAUDE.md CRITICAL).
문자수가 아닌 토큰 기준(from_tiktoken_encoder)으로 자른다(README·ADR).
"""
from __future__ import annotations

from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.ingest.parse import ParsedDoc

# 토큰 카운팅 인코딩. 테스트도 이 값으로 카운트해 chunk_size 검증을 일치시킨다.
TOKEN_ENCODING = "cl100k_base"


@dataclass
class Chunk:
    text: str
    source: str
    page: int | None
    chunk_index: int     # source 내 순번 (0부터, 페이지를 넘어가도 연속)


def chunk_docs(
    docs: list[ParsedDoc], *, chunk_size: int = 512, overlap: int = 64
) -> list[Chunk]:
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name=TOKEN_ENCODING,
        chunk_size=chunk_size,
        chunk_overlap=overlap,
    )
    # chunk_index는 source별 연속 카운터. 한 source가 페이지별 여러 ParsedDoc로
    # 쪼개져 와도 인덱스가 겹치지 않아 UNIQUE(source, chunk_index) 멱등성이 유지된다.
    chunks: list[Chunk] = []
    next_index: dict[str, int] = {}
    for doc in docs:
        for piece in splitter.split_text(doc.text):
            i = next_index.get(doc.source, 0)
            chunks.append(
                Chunk(text=piece, source=doc.source, page=doc.page, chunk_index=i)
            )
            next_index[doc.source] = i + 1
    return chunks
