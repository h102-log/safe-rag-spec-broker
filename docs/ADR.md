# Architecture Decision Records

## 철학
프로덕션 성숙도의 RAG — "돌아가는 데모"가 아니라 신뢰성·비용·지연을 상시 계측한다. 평가·관측은 프로덕션이면 항상 얹는다. 단, 과잉 엔지니어링을 경계한다: 20만 토큰 미만 문서집합이면 RAG 대신 프롬프트 캐싱이 더 싸고 정확하다.

---

### ADR-001: 벡터DB = pgvector (Postgres)
**결정**: 벡터 저장·검색에 pgvector 사용, HNSW 인덱스.
**이유**: MVP 규모(<5M 청크)에 충분하고 Postgres 단일 스택으로 운영이 단순하다. Langfuse도 Postgres를 쓴다.
**트레이드오프**: 10M+ 규모에선 Qdrant 등으로 이전이 필요하다. HNSW 빌드 시 OOM에 주의.

### ADR-002: 하이브리드 검색 (dense + BM25) + RRF
**결정**: pgvector dense와 BM25를 병렬 실행해 RRF(k=60)로 융합.
**이유**: 벡터 단독은 제품코드·고유명사를 놓친다. 하이브리드가 검색 실패율을 크게 낮춘다.
**트레이드오프**: 두 인덱스 유지 비용. MVP 1주차(`0-rag-core`)는 dense 기본 검색부터 구현하고, 하이브리드+RRF는 다음 페이즈로 미룬다.

### ADR-003: 평가 = RAGAS, 검색축/생성축 분리
**결정**: 생성축(Faithfulness·Answer Relevancy, reference-free) + 검색축(Context Precision·Recall, 골든셋 필요).
**이유**: "검색이 놓쳤나 / 생성이 지어냈나"를 분리 진단해야 근본원인을 특정할 수 있다.
**트레이드오프**: 검색축은 골든셋(질문-문맥-정답 50~200개, 사람 검수 필수)이 있어야 한다.

### ADR-004: 관측 = Langfuse (self-host)
**결정**: `@observe`로 계층형 trace를 자동 생성하고, RAGAS 점수를 `create_score`로 trace에 push.
**이유**: MIT 오픈소스, self-host 가능, 프롬프트 버저닝·비용·지연 집계 내장. 국내 대기업 채택 레퍼런스.
**트레이드오프**: Postgres·ClickHouse·Redis·MinIO 스택 운영 부담. 키 미설정 시 no-op으로 로컬 개발은 가능해야 한다.

### ADR-005: 임베딩 = BGE-M3 (교체 가능)
**결정**: 기본 임베딩 모델로 BGE-M3(한국어·다국어).
**이유**: 한국어 도메인 문서 대응. 최상위 모델 간 격차가 <1점이라 도메인 평가셋으로 직접 비교해야 한다.
**트레이드오프**: 로컬 실행 시 torch 등 무거운 의존성. OpenAI `text-embedding-3`로 교체 가능(가볍게 시작). 임베딩 인터페이스를 두어 모델을 갈아끼울 수 있게 한다.
