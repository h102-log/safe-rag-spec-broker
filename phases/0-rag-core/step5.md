# Step 5: retrieval

## 읽어야 할 파일

- `/docs/ARCHITECTURE.md`(데이터 흐름), `/docs/ADR.md`(ADR-002 dense-first), `/CLAUDE.md`(CRITICAL: @observe, citation)
- `app/ingest/index.py`(스키마), `app/ingest/embed.py`(`get_embedder`)
- `app/api.py`(step 0), `observability/langfuse_setup.py`(`observe`)

이전 step 코드를 읽고 스키마·임베딩 인터페이스를 파악한 뒤 작업하라.

## 작업

**`app/retrieve/search.py`** + **`POST /query`**.

- 검색:

  ```python
  @dataclass
  class Retrieved:
      text: str
      source: str
      page: int | None
      score: float

  def search(query: str, *, top_k: int = 5, conn=None, embedder=None) -> list[Retrieved]:
      # query 임베딩 → pgvector cosine ANN: ORDER BY embedding <=> %s LIMIT top_k
      ...
  ```

- `app/api.py`에 `POST /query {"question": "..."}` → `{"results": [Retrieved...], "trace_id": "..."}`.
- CRITICAL: `/query` 처리 경로를 `observe`(observability/langfuse_setup)로 계측하라. 이유: CLAUDE.md — 모든 온라인 요청은 trace로 계측. Langfuse 미설정이면 no-op이어도 데코레이터는 유지.
- CRITICAL: 결과에 provenance(`source`, `page`)를 담아라. 이유: 인용.
- `trace_id`: Langfuse 계측 시 그 trace id, 없으면 생성한 uuid를 반환한다.
- 이 페이즈는 **검색 결과(청크)만** 반환한다. LLM 생성 답변은 다음 페이즈다.

## Acceptance Criteria

```bash
docker compose up -d db
pytest -m integration tests/test_query.py -q
```

`test_query.py`(`@pytest.mark.integration`): 알려진 픽스처를 색인(step 4 경로 재사용) → `search("...")`가 관련 청크를 `top_k` 안에 반환 → TestClient로 `POST /query`가 200 + `results` 비어있지 않음 + `trace_id` 존재. DB 접속 불가하면 `pytest.skip`.

## 검증 절차

1. `docker compose up -d db` 후 AC 실행.
2. 체크리스트: 디렉토리 구조(`app/retrieve/`) / ADR-002(dense-only) / CLAUDE.md CRITICAL(@observe, citation).
3. step 5 index.json 업데이트. DB 미가용 시 `blocked` 후 중단.

## 금지사항

- LLM 호출/생성·인용 문장 합성을 여기서 하지 마라. 이유: 생성은 다음 페이즈. 이 step은 검색까지.
- 하이브리드/리랭킹을 추가하지 마라. 이유: ADR-002.
- `/query`를 계측 없이 두지 마라. 이유: CRITICAL @observe.
- 기존 테스트를 깨뜨리지 마라.
