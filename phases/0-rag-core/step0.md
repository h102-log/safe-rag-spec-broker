# Step 0: project-setup

## 읽어야 할 파일

먼저 아래를 읽고 아키텍처·설계 의도를 파악하라:

- `/docs/ARCHITECTURE.md` — 디렉토리 구조, 데이터 흐름
- `/docs/ADR.md` — 기술 결정 (ADR-001 pgvector, ADR-005 BGE-M3, ADR-004 Langfuse)
- `/CLAUDE.md` — CRITICAL 규칙, 명령어

아직 코드가 없다. 이 step이 실행·테스트 뼈대를 만든다.

## 작업

프로젝트가 실행·테스트되는 최소 기반을 만든다.

1. **`requirements.txt`** — 이 페이즈에 필요한 의존성만:
   - `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `python-dotenv`
   - `docling` (파싱), `FlagEmbedding` (BGE-M3 임베딩)
   - `langchain-text-splitters` (청킹), `tiktoken`
   - `psycopg[binary]`, `pgvector` (벡터DB)
   - `langfuse` (관측)
   - `pytest`, `httpx` (TestClient)

   버전 핀은 재량. 서로 설치 가능한 조합으로.

2. **`.env.example`** — 키/값 자리만. `DATABASE_URL`, `EMBEDDING_MODEL=BAAI/bge-m3`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`. 실제 키 값은 넣지 마라.

3. **`docker-compose.yml`** — **pgvector 서비스(`db`)만**. 이미지 `pgvector/pgvector:pg16`, 포트 5432, healthcheck 포함.
   `ponytail: pgvector만. Langfuse 스택(ClickHouse·Redis·MinIO)은 관측 페이즈에서 추가.` 이유: 이 페이즈는 pgvector만 읽고 쓴다. 쓰지 않는 서비스를 띄우는 건 낭비.

4. **`app/config.py`** — `pydantic-settings` 기반 `Settings`(`.env` 로드). 필드: `database_url`, `embedding_model`, LLM 키, Langfuse 키(모두 옵셔널 가능). `get_settings()`로 캐시 반환.

5. **`app/api.py`** — FastAPI `app`, `GET /health` → `{"status": "ok"}`.

6. **`observability/langfuse_setup.py`** — 계측 진입점. `observe` 데코레이터를 export한다.
   - CRITICAL: LANGFUSE 키가 있으면 langfuse의 `@observe`를 적용하고, 없으면 함수를 그대로 통과시키는 **no-op**이어야 한다. 키 없이도 import·호출이 실패하면 안 된다. 이유: 로컬 개발/테스트가 Langfuse 없이 가능해야 한다.

7. **`pyproject.toml`** (또는 `pytest.ini`) — pytest 설정:
   - `markers`에 `integration: DB 등 외부 인프라가 필요한 테스트` 등록
   - `addopts = -m "not integration"` — 기본 `pytest`는 integration 제외

8. **`tests/test_health.py`** — TestClient로 `GET /health` == 200, body `{"status":"ok"}`.

패키지 `__init__.py`를 `app/`, `app/ingest/`, `app/retrieve/`, `observability/`, `tests/`에 둔다(빈 파일이라도).

## Acceptance Criteria

```bash
pip install -r requirements.txt
docker compose config -q
pytest tests/test_health.py -q
```

주의: `docling`·`FlagEmbedding`은 torch 등을 끌어와 설치가 무겁다(최초 수백 MB~). 시간이 걸려도 실패가 아니다.

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 체크리스트: ARCHITECTURE.md 디렉토리 구조를 따르는가 / ADR 스택(pgvector·BGE-M3)을 벗어나지 않았는가 / CLAUDE.md CRITICAL(비밀키 커밋 금지) 위반 없는가.
3. `phases/0-rag-core/index.json`의 step 0 업데이트: 성공 → `"completed"` + `"summary"`(생성 파일 목록·주요 결정) / 3회 실패 → `"error"` + `"error_message"` / 인프라 개입 필요 → `"blocked"` + `"blocked_reason"` 후 중단.

## 금지사항

- Langfuse의 ClickHouse/Redis/MinIO 서비스를 docker-compose에 넣지 마라. 이유: 이 페이즈는 pgvector만 사용하며 관측 스택은 별도 페이즈 소관이다.
- 파싱/청킹/임베딩/검색 로직을 구현하지 마라. 이유: 각각 step 1~5의 범위다. 여기선 빈 패키지 뼈대까지만.
- 실제 키가 든 `.env` 파일을 만들지 마라. `.env.example`만. 이유: 비밀 유출.
- 기존 테스트를 깨뜨리지 마라.
