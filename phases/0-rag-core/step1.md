# Step 1: parsing

## 읽어야 할 파일

- `/docs/ARCHITECTURE.md`, `/docs/ADR.md` — provenance/인용 맥락
- `/CLAUDE.md` — CRITICAL(citation/provenance)
- `app/config.py` — step 0에서 생성됨. 컨벤션을 따르라.

이전 step에서 만들어진 코드를 읽고 설계 의도를 이해한 뒤 작업하라.

## 작업

**`app/ingest/parse.py`** — 문서 파일을 텍스트로 변환하되 표·레이아웃·출처를 보존한다.

- **Docling** `DocumentConverter`로 파싱한다.
- 인터페이스(시그니처 수준, 구현은 재량):

  ```python
  @dataclass
  class ParsedDoc:
      text: str
      source: str          # 원본 파일 경로
      page: int | None     # 페이지 번호(있으면)

  def parse_file(path: str | Path) -> list[ParsedDoc]:
      ...
  ```

  페이지/섹션 단위로 여러 `ParsedDoc`를 반환해도 되고, 문서 1개=1 `ParsedDoc`여도 된다.
- CRITICAL: 표는 Docling의 구조 보존 출력(markdown 등)으로 유지하라. 표를 뭉갠 평문으로 만들지 마라. 이유: 표 깨짐이 이후 청킹·검색·생성 전 단계를 오염시킨다.
- CRITICAL: `source`(원본 경로)를 반드시 채워라. 이후 인용(citation)의 근거다.

지원 포맷: PDF 우선(표 포함). Docling이 지원하는 다른 포맷도 통과하면 좋다.

**테스트 픽스처**: `tests/fixtures/`에 표가 포함된 작은 샘플 문서 1개를 추가하라(작은 PDF 등 Docling이 처리하는 포맷). 표 셀 텍스트 보존 검증에 쓴다.

## Acceptance Criteria

```bash
pytest tests/test_parse.py -q
```

`test_parse.py`: 픽스처를 `parse_file`로 파싱 → 결과가 비어있지 않고, 각 `ParsedDoc.source`가 채워졌으며, 표 안의 알려진 셀 텍스트가 결과 텍스트에 포함되는지 assert.

## 검증 절차

1. AC 실행.
2. 체크리스트: ARCHITECTURE 디렉토리 구조(`app/ingest/`) / ADR 파싱 결정(Docling) / CLAUDE.md CRITICAL(provenance) 준수.
3. `phases/0-rag-core/index.json`의 step 1 업데이트(completed+summary / error / blocked).

## 금지사항

- 청킹/임베딩을 여기서 하지 마라. 이유: step 2~3의 범위.
- Docling을 우회해 단순 텍스트 추출(예: PyPDF 평문)로 대체하지 마라. 이유: 표·레이아웃 보존이 이 프로젝트 파싱 설계의 근거(ADR/README)다.
- 기존 테스트를 깨뜨리지 마라.
