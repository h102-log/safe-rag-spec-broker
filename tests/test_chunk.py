import tiktoken

from app.ingest.chunk import Chunk, TOKEN_ENCODING, chunk_docs
from app.ingest.parse import ParsedDoc

_enc = tiktoken.get_encoding(TOKEN_ENCODING)


def _long_doc(source: str, page: int | None) -> ParsedDoc:
    # 유니크 단어의 긴 나열 → 여러 청크로 나뉘고, 겹침이 단어 단위로 드러난다.
    text = " ".join(f"word{i}" for i in range(2000))
    return ParsedDoc(text=text, source=source, page=page)


def test_token_size_overlap_and_provenance():
    doc = _long_doc("regulations.docx", 7)
    chunks = chunk_docs([doc], chunk_size=128, overlap=32)

    assert all(isinstance(c, Chunk) for c in chunks)
    assert len(chunks) > 1, "긴 문서는 여러 청크로 나뉘어야 한다"

    # (1) 각 청크 토큰 수 ≤ chunk_size (tiktoken 카운트)
    assert all(len(_enc.encode(c.text)) <= 128 for c in chunks)

    # (3) source/page provenance 전파
    assert all(c.source == "regulations.docx" for c in chunks)
    assert all(c.page == 7 for c in chunks)

    # (4) chunk_index 연속 (0부터)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))

    # (2) 인접 청크 간 overlap 존재 (유니크 단어라 교집합 = 겹친 단어)
    for a, b in zip(chunks, chunks[1:]):
        assert set(a.text.split()) & set(b.text.split()), "인접 청크가 겹쳐야 한다"


def test_chunk_index_resets_per_source():
    docs = [_long_doc("a.docx", 1), _long_doc("b.docx", 2)]
    chunks = chunk_docs(docs, chunk_size=128, overlap=32)

    a = [c for c in chunks if c.source == "a.docx"]
    b = [c for c in chunks if c.source == "b.docx"]
    assert a and b
    # chunk_index는 source별로 0부터 리셋되며 provenance가 섞이지 않는다.
    assert [c.chunk_index for c in a] == list(range(len(a)))
    assert [c.chunk_index for c in b] == list(range(len(b)))
    assert all(c.page == 1 for c in a)
    assert all(c.page == 2 for c in b)
