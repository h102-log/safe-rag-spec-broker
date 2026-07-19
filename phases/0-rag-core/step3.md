# Step 3: embedding

## 읽어야 할 파일

- `/docs/ADR.md` — ADR-005 (BGE-M3, 교체 가능 인터페이스)
- `app/ingest/chunk.py` — step 2. `Chunk` 구조.
- `app/config.py` — `embedding_model`

이전 step 코드를 읽고 작업하라.

## 작업

**`app/ingest/embed.py`** — 텍스트를 dense 벡터로 변환한다.

- 교체 가능한 인터페이스(ADR-005):

  ```python
  class Embedder(Protocol):
      dim: int
      def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

  class BGEM3Embedder:          # 기본 구현
      dim = 1024
      # FlagEmbedding BGEM3FlagModel 사용, dense 벡터, 정규화
      def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

  def get_embedder() -> Embedder:   # config.embedding_model 기반 팩토리
      ...
  ```

- BGE-M3 dense 차원 = **1024**.
- CRITICAL: 임베딩은 `Embedder` 인터페이스를 통해서만 소비하라. 모델 교체(BGE-M3 ↔ OpenAI)가 색인/검색 코드 변경 없이 가능해야 한다. 이유: ADR-005.

## Acceptance Criteria

```bash
pytest tests/test_embed.py -q                 # 인터페이스 계약 (fast)
pytest -m integration tests/test_embed.py -q  # 실제 BGE-M3 로드 (opt-in, 최초 모델 다운로드 큼)
```

- 계약 테스트(비-integration): 고정 `dim`의 fake `Embedder`로 `embed_texts` 반환이 (개수==입력 수, 각 벡터 길이==`dim`)인지 검증.
- integration 테스트(`@pytest.mark.integration`): `BGEM3Embedder`로 실제 임베딩 → 각 벡터 길이==1024, 값이 float.

`ponytail: 실제 모델 로드는 무겁다 → integration 마커로 분리, 기본 pytest는 빠르게. 업그레이드 경로: CI에서 -m integration 별도 잡.`

## 검증 절차

1. AC 실행(계약 테스트는 필수 통과, integration은 환경 되면 통과).
2. 체크리스트: 디렉토리 구조 / ADR-005 교체성 인터페이스 / dim 1024.
3. step 3 index.json 업데이트.

## 금지사항

- 임베딩을 pgvector에 쓰지 마라. 이유: 색인은 step 4.
- 모델을 코드에 하드코딩해 인터페이스를 우회하지 마라. 이유: ADR-005 교체성.
- 기존 테스트를 깨뜨리지 마라.
