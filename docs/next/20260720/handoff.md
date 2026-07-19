# 이어서 작업 — 2026-07-20 (phase 0-rag-core)

전날(2026-07-19) 작업을 이어받기 위한 핸드오프 노트. 이 문서만 읽어도 맥락을 잡고 바로 시작할 수 있게 정리한다.

> 참고: 이 파일은 `docs/next/...` 아래라 `execute.py`의 가드레일 로더(`docs/*.md` 비재귀 glob)에 걸리지 않는다. step 프롬프트에 주입되지 않으니 안심하고 자유롭게 적어도 된다.

---

## 1. 지금까지 (2026-07-19 완료분)

- **브랜치:** `feat-0-rag-core` (여기서 계속 작업). `main`에는 아직 머지 안 함.
- **Step 0 (project-setup) 완료 + 커밋됨.** phase 0-rag-core 6단계 중 1개 완료.
- **오늘 만든 커밋 (오래된 순):**
  - `c2542fd feat(0-rag-core): step 0 — project-setup` — 코드 뼈대 14파일
  - `75e8a57 chore(0-rag-core): step 0 output` — `phases/0-rag-core/index.json` step0 → `completed`
  - `b025b8b fix(harness): 파일 I/O에 encoding=utf-8 명시` — Windows cp949 디코드 버그 수정 (아래 3번)
- **Step 0 산출물:** `app/config.py`(`get_settings`), `app/api.py`(`GET /health`), `observability/langfuse_setup.py`(키 없으면 no-op `observe`), `docker-compose.yml`(pgvector `db`만), `requirements.txt`, `.env.example`, `pyproject.toml`(pytest `integration` 마커 + `addopts=-m "not integration"`, `pythonpath=["."]`), `tests/test_health.py`, 각 패키지 `__init__.py`.

## 2. 환경 (재개 시 필수)

- **가상환경:** `.venv/` (Python 3.12.10). 이미 전체 의존성(docling·FlagEmbedding·torch 포함) 설치 완료.
  - 실행 예: `./.venv/Scripts/python.exe -m pytest ...` (Windows / Git Bash 기준)
- **기본 테스트:** `./.venv/Scripts/python.exe -m pytest -q` → `integration` 마커는 기본 제외됨(DB 불필요).
- **DB(step 4·5용):** Docker 29.5.3 설치돼 있음. 데몬 기동 여부는 미확인 — step 4 시작 시 `docker compose up -d db`로 pgvector 띄우고 healthcheck 확인.
- **Langfuse:** 키 없음 → `observe`는 no-op. 로컬 개발/테스트는 키 없이 그대로 가능.

## 3. 짚고 넘어갈 것: harness 인코딩 버그 (해결됨)

- 어제 `scripts/execute.py`가 한글 UTF-8 파일(CLAUDE.md·docs·step md)을 `read_text()`로 **encoding 없이** 읽어 Windows cp949로 디코드하다 `UnicodeDecodeError`로 죽던 버그를 발견·수정했다(커밋 `b025b8b`).
- 이제 `./.venv/Scripts/python.exe -m pytest scripts/test_execute.py -q` → **52 passed**.
- 시사점: 이 Windows 환경에서 `python scripts/execute.py 0-rag-core`를 실제로 돌려도 가드레일/step 로딩 단계에서 안 깨진다(이 버그 때문에 예전엔 깨졌을 것).

## 4. 내일 할 일 — Step 1: parsing (다음 타깃)

스펙 원본: **`phases/0-rag-core/step1.md`** (반드시 이걸 열어 그대로 따를 것).

- **산출물:** `app/ingest/parse.py`
  - Docling `DocumentConverter`로 문서 → `ParsedDoc(text, source, page)` 리스트.
  - 인터페이스(시그니처만, 구현은 재량):
    ```python
    @dataclass
    class ParsedDoc:
        text: str
        source: str          # 원본 파일 경로 (provenance)
        page: int | None
    def parse_file(path: str | Path) -> list[ParsedDoc]: ...
    ```
- **CRITICAL(어기지 말 것):**
  - 표는 Docling 구조 보존 출력(markdown 등)으로 유지 — 평문으로 뭉개지 마라.
  - `source`(원본 경로) 반드시 채워라 — 이후 인용(citation)의 근거.
  - Docling 우회(PyPDF 평문 추출 등) 금지.
- **테스트 픽스처:** `tests/fixtures/`에 **표가 포함된 작은 샘플 문서 1개**(작은 PDF 등 Docling이 처리하는 포맷)를 추가. 표 셀 텍스트 보존 검증용.
- **AC:** `./.venv/Scripts/python.exe -m pytest tests/test_parse.py -q`
  - `test_parse.py`: 픽스처를 `parse_file`로 파싱 → 결과 비어있지 않음 + 각 `ParsedDoc.source` 채워짐 + 표 안 알려진 셀 텍스트가 결과에 포함됨 assert.
- **주의(파서 특성):** Docling은 최초 실행 시 레이아웃/OCR 모델을 내려받을 수 있어 첫 파싱이 느리거나 네트워크가 필요할 수 있다. 느린 건 실패가 아니다. OCR 없이도 되는 텍스트 기반 PDF 픽스처를 쓰면 가장 안전.
- **완료 처리:** `phases/0-rag-core/index.json`의 step1 → `"completed"` + `"summary"`(생성 파일·핵심 결정 한 줄), 그리고 harness 규약 2단계 커밋(`feat(0-rag-core): step 1 — parsing` → `chore(0-rag-core): step 1 output`).

## 5. 남은 로드맵 (step 2~5) 개요

의존 사슬은 **1 → 2 → 3 → 4 → 5** 완전 순차. 각 step은 시작 시 해당 `stepN.md`를 열어 그대로 따른다.

| Step | 산출물 | 핵심 규칙 | DB |
|---|---|---|---|
| 2 chunking | `app/ingest/chunk.py` — `Chunk(text,source,page,chunk_index)`, 토큰 기준 512/overlap 64(`from_tiktoken_encoder`) | provenance(`source`,`page`) 전파 | 불필요 |
| 3 embedding | `app/ingest/embed.py` — `Embedder` Protocol + `BGEM3Embedder(dim=1024)` + `get_embedder()` | 교체 가능 인터페이스(ADR-005), 계약 테스트 필수·실모델은 `-m integration` | 불필요 |
| 4 indexing | `app/ingest/index.py` + `app/ingest/__main__.py`(`python -m app.ingest --source <dir>`) + pgvector 스키마(HNSW) | **멱등성**: `(source,chunk_index)` UNIQUE + `ON CONFLICT DO UPDATE` | **필요** |
| 5 retrieval | `app/retrieve/search.py` + `POST /query` | `@observe` 계측 필수, 결과에 provenance, dense-only(ADR-002) | **필요** |

- **Step 4·5는 pgvector가 떠 있어야** integration 테스트가 돈다. 못 띄우면 스펙상 `blocked`(사유 기록) 후 중단하도록 설계돼 있음.
- 이 페이즈는 **dense 검색까지만**. 하이브리드(BM25)·리랭킹·LLM 생성은 다음 페이즈.

## 6. 진행 방식 (어제 합의)

- **한 세션에서 직접 한 step씩 구현 → 검증 → 브리핑 → 승인** 후 다음 step. (`execute.py` 무정지 자율 실행이 아니라 체크포인트 방식)
- 각 step 완료 시 harness 규약 커밋(feat→chore) + `index.json` 상태 갱신.
- 검증은 각 step의 AC(`test_*.py`) + `scripts/test_execute.py`(회귀 없음) 실행.
- 대안: 원하면 `./.venv/Scripts/python.exe scripts/execute.py 0-rag-core`로 남은 step을 자동 실행할 수도 있음(인코딩 버그 고쳐서 이제 이 Windows에서도 동작). 단 이 경우 step별 승인 없이 쭉 진행됨.

## 7. 열린 항목 / 판단 필요

- **Docling 픽스처 준비:** 표 포함 작은 PDF를 어떻게 확보할지(직접 생성 vs 샘플 반입). 텍스트 기반(비-OCR) PDF 권장.
- **`.venv`는 gitignore됨** — 새 머신에서 재개하면 `pip install -r requirements.txt` 다시 필요.
- **push 대상 remote 확인** — 이 repo는 `origin`(템플릿)과 `safe-rag`(실제 repo)가 있음. 실제 작업은 `safe-rag`로 push.
