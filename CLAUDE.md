# 프로젝트: domain-rag-eval-obs

평가(RAGAS)와 관측(Langfuse)을 얹은 도메인 RAG 시스템. 폐쇄 문서집합(사내규정·매뉴얼·법령·기술문서)에 대해 근거 기반으로 답하고, 답의 품질을 정량화하며, 모든 요청을 추적·계측한다.

## 기술 스택
- Python 3.11+
- API: FastAPI + uvicorn
- 오케스트레이션: LangChain / LangGraph
- 임베딩: BGE-M3 (한국어·다국어) — 교체 가능 (ADR-005)
- 벡터DB: pgvector (Postgres) — MVP 규모(<5M)
- 검색: 하이브리드 (pgvector dense + BM25) + RRF
- 평가: RAGAS + LLM-as-a-Judge
- 관측: Langfuse (self-host)
- 생성 모델: Claude / OpenAI (교체 가능)
- 테스트: pytest

## 아키텍처 규칙
- CRITICAL: 생성 답변은 반드시 검색된 문맥(retrieved context)에 근거해야 한다. 파라메트릭 기억만으로 답하거나 출처 없는 주장을 만들지 마라.
- CRITICAL: 답변에는 인용(citation, 문서/청크 provenance)을 포함한다.
- CRITICAL: 모든 온라인 요청(검색·생성·툴 호출)은 Langfuse @observe로 계층형 trace에 계측한다. 계측 없는 LLM/검색 호출을 추가하지 마라. (Langfuse 미설정 시 no-op이어도 데코레이터는 유지)
- 레이어 분리: `app/ingest`(오프라인) / `app/retrieve` / `app/generate` / `app/api.py` / `eval` / `observability`. 레이어 경계를 넘는 직접 호출을 만들지 마라.
- 비밀키는 `.env`로만 다룬다. 코드·커밋에 키를 넣지 마라.

## 개발 프로세스
- CRITICAL: 새 기능은 테스트 먼저(TDD). 검색·평가 로직은 골든셋/픽스처로 검증한다.
- 커밋 메시지는 conventional commits 형식(feat:, fix:, docs:, refactor:, chore:). Harness의 execute.py가 이 규약으로 커밋한다.

## 명령어
docker compose up -d                             # Postgres(pgvector) + Langfuse
pip install -r requirements.txt                  # 의존성
python -m app.ingest --source ./docs             # 문서 파싱→청킹→임베딩→pgvector 색인 (오프라인)
uvicorn app.api:app --reload                     # API 서버
pytest                                           # 테스트
python -m eval.ragas_run --dataset eval/golden   # RAGAS 지표 → Langfuse
python -m eval.ci_gate --threshold faithfulness=0.9   # 회귀 게이트
