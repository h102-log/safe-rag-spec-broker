# PRD: domain-rag-eval-obs

## 목표
폐쇄 문서집합에 대해 LLM이 근거 기반으로 답하고, 그 답의 품질을 RAGAS로 정량화하며 Langfuse로 모든 요청을 추적·계측하는, 프로덕션 성숙도의 도메인 RAG 시스템.

## 사용자
- 규제·근거가 필수인 도메인의 지식 QA 사용자 (사내 규정 질의, 매뉴얼·법령 검색)
- 시스템을 운영·개선하는 ML/플랫폼 엔지니어 (평가·관측 지표 소비자)

## 핵심 기능
1. 도메인 RAG 파이프라인 — 파싱·청킹·임베딩·색인(오프라인) + 하이브리드 검색·리랭킹·생성·인용(온라인)
2. 평가 (RAGAS) — 검색축(context precision/recall)과 생성축(faithfulness/answer relevancy)을 분리 진단 + 골든셋 회귀 게이트(CI)
3. 관측 (Langfuse) — 요청별 계층형 trace, 토큰·비용·지연 집계, 프롬프트 버저닝, score push

## MVP 제외 사항
- 사용자 UI/프론트엔드 — 관측·평가는 Langfuse 자체 UI로 대체
- 멀티테넌시·인증/인가
- 대규모(10M+ 청크) 벡터DB(Qdrant 등) — MVP는 pgvector(<5M)
- 20만 토큰(약 500페이지) 미만 문서집합 — 그 경우 RAG 대신 문서 전체를 프롬프트에 넣고 캐싱한다(README 주의사항)

## 디자인
- UI 없음. 백엔드 API(FastAPI) + 오프라인 인덱싱 스크립트 + Langfuse 대시보드로 구성.
- 관측·평가 뷰가 필요해지면 `docs/_deferred/UI_GUIDE.md`를 되살려 별도 페이즈로 설계한다.
