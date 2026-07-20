"""문서 파일 → 텍스트(표·레이아웃·출처 보존). Docling DocumentConverter 기반.

Docling 우회(PyPDF 평문 추출 등) 금지 — 표/레이아웃 보존이 파싱 설계의 근거(ADR).
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# docling은 무거운 ML 스택(transformers/torch)을 끌어온다. ParsedDoc만 쓰는
# 하위 레이어(chunk 등)가 이를 로드하지 않도록 실제 파싱 시점까지 지연 import한다.


@dataclass
class ParsedDoc:
    text: str            # 표는 markdown으로 구조 보존
    source: str          # 원본 파일 경로 (citation provenance)
    page: int | None     # 페이지 번호(있으면)


@lru_cache
def _converter() -> "DocumentConverter":
    # 파이프라인 로딩이 무거워 재사용(step 4 디렉토리 색인 루프에서 유효).
    from docling.document_converter import DocumentConverter

    return DocumentConverter()


def parse_file(path: str | Path) -> list[ParsedDoc]:
    result = _converter().convert(path)
    text = result.document.export_to_markdown()
    # ponytail: 문서 1개=1 ParsedDoc(page=None). 페이지 단위 provenance는
    # 인용에서 페이지가 실제로 필요해지는 step 4/5에서 분리.
    return [ParsedDoc(text=text, source=str(path), page=None)]
