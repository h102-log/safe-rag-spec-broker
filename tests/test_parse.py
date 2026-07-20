from pathlib import Path

from app.ingest.parse import ParsedDoc, _to_parsed_docs, parse_file

FIXTURE = Path(__file__).parent / "fixtures" / "sample_table.docx"


class _FakeDoc:
    """Docling 계약 흉내: pages(dict)와 page_no 필터 export. 모델 로드 없이 분기 검증."""

    def __init__(self, pages: dict, texts: dict):
        self.pages = pages
        self._texts = texts

    def export_to_markdown(self, page_no=None):
        return self._texts[page_no]


def test_to_parsed_docs_splits_pages_and_fills_page_number():
    # 페이지 정보가 있으면(PDF 등) 페이지별 ParsedDoc + 실제 page 채움.
    doc = _FakeDoc(pages={1: object(), 2: object()},
                   texts={1: "first page", 2: "second page"})
    docs = _to_parsed_docs(doc, "manual.pdf")
    assert [(d.page, d.text) for d in docs] == [(1, "first page"), (2, "second page")]
    assert all(d.source == "manual.pdf" for d in docs)


def test_to_parsed_docs_flow_document_has_no_page():
    # pages={} (DOCX 등 flow 문서) → page=None 단일.
    doc = _FakeDoc(pages={}, texts={None: "whole doc"})
    docs = _to_parsed_docs(doc, "memo.docx")
    assert len(docs) == 1
    assert docs[0].page is None and docs[0].text == "whole doc"


def test_parse_preserves_table_cells_and_source():
    docs = parse_file(FIXTURE)

    assert docs, "파싱 결과가 비어 있으면 안 된다"
    assert all(isinstance(d, ParsedDoc) for d in docs)
    assert all(d.source for d in docs), "각 ParsedDoc.source(provenance)가 채워져야 한다"

    text = "\n".join(d.text for d in docs)
    # 표 셀 텍스트가 뭉개지지 않고 보존되는지 (CRITICAL: 표 구조 보존)
    assert "보증기간" in text
    assert "24개월" in text
