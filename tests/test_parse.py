from pathlib import Path

from app.ingest.parse import ParsedDoc, parse_file

FIXTURE = Path(__file__).parent / "fixtures" / "sample_table.docx"


def test_parse_preserves_table_cells_and_source():
    docs = parse_file(FIXTURE)

    assert docs, "파싱 결과가 비어 있으면 안 된다"
    assert all(isinstance(d, ParsedDoc) for d in docs)
    assert all(d.source for d in docs), "각 ParsedDoc.source(provenance)가 채워져야 한다"

    text = "\n".join(d.text for d in docs)
    # 표 셀 텍스트가 뭉개지지 않고 보존되는지 (CRITICAL: 표 구조 보존)
    assert "보증기간" in text
    assert "24개월" in text
