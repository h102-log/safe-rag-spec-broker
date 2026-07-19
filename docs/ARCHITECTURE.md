# 아키텍처

## 3-레이어 구조
- **Layer 1 — RAG 파이프라인 (제품 본체)**: 오프라인 인덱싱(파싱→청킹→임베딩→벡터DB) + 온라인 질의(검색→리랭킹→프롬프트→생성→인용)
- **Layer 2 — 평가 (RAGAS)**: 검색축/생성축 지표로 품질 정량화, 골든셋 회귀 게이트
- **Layer 3 — 관측 (Langfuse)**: 요청별 계층형 trace, 토큰·비용·지연, 프롬프트 버저닝, score 저장

관계: Layer 1의 모든 단계를 Layer 3 trace로 감싸고, Layer 2가 결과를 채점해 score를 trace에 push한다.

## 디렉토리 구조
```
app/
├── ingest/          # 파싱·청킹·임베딩·색인 (오프라인). `python -m app.ingest`로 실행
├── retrieve/        # 하이브리드 검색 + 리랭킹
├── generate/        # 프롬프트 조립·생성·인용
├── config.py        # 환경변수 로더 (.env)
└── api.py           # FastAPI 엔드포인트 (@observe 계측)
eval/
├── golden/          # 골든 데이터셋 (질문-문맥-정답)
├── ragas_run.py     # RAGAS 지표 실행 → Langfuse push
└── ci_gate.py       # 임계값 회귀 게이트 (pytest 호환)
observability/
└── langfuse_setup.py   # Langfuse 클라이언트 초기화 (키 없으면 no-op)
tests/                   # pytest
docker-compose.yml       # Postgres(pgvector) + Langfuse 스택
.env.example
requirements.txt
```

## 데이터 흐름
```
[오프라인 인덱싱]  문서 → 파싱 → 청킹 → 임베딩 → pgvector 색인
[온라인 질의]      질문 → (검색: dense + BM25 → RRF) → 리랭킹 → 프롬프트 조립 → LLM 생성 → 인용
                   └ 전 단계를 Langfuse trace로 계측하고, 결과를 RAGAS로 채점해 score를 trace에 push
```

## 상태 관리
- 영속 상태: Postgres(pgvector) — 청크·임베딩·메타데이터.
- 관측 상태: Langfuse(self-host) — Postgres·ClickHouse·Redis·MinIO.
- 애플리케이션 자체는 무상태(stateless). 요청별 trace로 사후 재구성한다.
