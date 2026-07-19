# Step 2: chunking

## 읽어야 할 파일

- `/docs/ARCHITECTURE.md`, `/docs/ADR.md`
- `app/ingest/parse.py` — step 1. `ParsedDoc`를 입력으로 받는다.
- `app/config.py`

이전 step 코드를 읽고 `ParsedDoc` 구조·컨벤션을 파악한 뒤 작업하라.

## 작업

**`app/ingest/chunk.py`** — `ParsedDoc`를 검색 단위 청크로 분할한다.

- LangChain `RecursiveCharacterTextSplitter`를 **토큰 기준**으로 사용한다(`from_tiktoken_encoder`). `chunk_size`≈512 토큰, `overlap`≈64 토큰(10~20%).
- 인터페이스:

  ```python
  @dataclass
  class Chunk:
      text: str
      source: str
      page: int | None
      chunk_index: int     # source 내 순번 (0부터)

  def chunk_docs(docs: list[ParsedDoc], *, chunk_size: int = 512, overlap: int = 64) -> list[Chunk]:
      ...
  ```

- CRITICAL: `ParsedDoc`의 provenance(`source`, `page`)를 각 `Chunk`로 전파하라. 이유: 인용 추적이 청킹에서 끊기면 안 된다.

## Acceptance Criteria

```bash
pytest tests/test_chunk.py -q
```

`test_chunk.py`: 긴 텍스트를 담은 합성 `ParsedDoc` 입력 → (1) 각 청크 토큰 수 ≤ `chunk_size`(tiktoken으로 카운트), (2) 인접 청크 간 overlap 존재, (3) `source`/`page`가 청크로 전파, (4) `chunk_index` 연속.

## 검증 절차

1. AC 실행.
2. 체크리스트: 디렉토리 구조 / 토큰 기준·오버랩(README·ADR) / provenance 전파(CLAUDE.md CRITICAL).
3. step 2 index.json 업데이트.

## 금지사항

- 순수 문자수 분할로 되돌리지 마라. 이유: README가 토큰 기준·오버랩을 명시한다.
- semantic 청킹을 넣지 마라. 이유: 이 페이즈 범위 밖(잘 설정됐을 때만 우세 — 나중에).
- 파싱/임베딩 로직을 손대지 마라. 이유: step 1·3 범위.
- 기존 테스트를 깨뜨리지 마라.
