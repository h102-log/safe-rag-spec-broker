# domain-rag-eval-obs

> 평가(evaluation)와 관측(observability)을 얹은 **도메인 RAG 시스템**.
> "돌아가는 데모"가 아니라 **품질을 숫자로 재고, 모든 요청을 추적·계측하는 프로덕션 RAG**.

특정 폐쇄 문서집합(사내규정·매뉴얼·법령·기술문서 등)에 대해 LLM이 근거 기반으로 답하고,
그 답의 품질을 RAGAS 지표로 정량화하며, Langfuse로 추적한다.

---

## 왜 이 프로젝트인가

RAG 데모는 흔하다. **평가·관측까지 얹은 RAG는 드물다.** 그리고 그게 국내 대기업이 실무에서 실제로 쓰는 것이다.

- **배민(우아한형제들)**: MLflow·LangSmith 등 7개 LLMOps 툴 비교 끝에 **Langfuse를 AI플랫폼 2.0 기반으로 공식 채택**. 핵심 4기능 = 프롬프트관리·Observability·크레덴셜·Evaluation. ([techblog 22839](https://techblog.woowahan.com/22839/))
- **배민 '물어보새'**(RAG+Text-to-SQL): 자체 리더보드로 **500회+ A/B 테스트**, 단계별 평가. ([18144](https://techblog.woowahan.com/18144/))
- **카카오**: 국내 최초 function calling 평가 벤치마크 **FunctionChat-Bench 오픈소스 공개**. ([kakao 11253](https://www.kakaocorp.com/page/detail/11253))
- **LINE(LY)**: RAG 챗봇 + 평가 정량화 LLMOps 사내표준.

흔한 챗봇 데모는 "retrieval이 한 번 작동함"만 보여준다.
이 프로젝트는 **신뢰성·비용·지연을 지속 측정·모니터링하는 프로덕션 성숙도**를 증명한다.

---

## 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1: RAG 파이프라인 (제품 본체)                          │
│                                                               │
│  [오프라인 인덱싱]  문서 → 파싱 → 청킹 → 임베딩 → 벡터DB       │
│  [온라인 질의]      질문 → 검색 → 리랭킹 → 프롬프트 → 생성 → 인용│
└───────────────┬─────────────────────────────┬───────────────┘
                │ 모든 단계를 trace로 감싼다     │ 결과를 채점한다
                ▼                             ▼
┌───────────────────────────┐   ┌───────────────────────────────┐
│ LAYER 3: 관측 (Langfuse)   │   │ LAYER 2: 평가 (RAGAS)          │
│ - 요청별 trace (검색·생성)  │   │ - 검색축: context precision/recall│
│ - 토큰·비용·지연 집계       │   │ - 생성축: faithfulness/relevancy │
│ - 프롬프트 버저닝·롤백      │   │ - 골든셋 회귀 테스트 (CI 게이트) │
│ - score 저장 (사람/LLM판정) │   │ - 점수를 trace에 push ──────────┘
└───────────────────────────┘   └───────────────────────────────┘
```

### Layer 1 — RAG 파이프라인

두 국면으로 나뉜다 (정본 "표준 단계 수"는 없음 — 개념적 분해).

| 단계 | 하는 일 | 표준 선택 | 흔한 실패 |
|---|---|---|---|
| ① 파싱 | 문서→텍스트, 표·레이아웃 보존 | Docling(로컬, 표 97.9%), LlamaParse, Unstructured | 표 깨짐·다단 텍스트 뒤섞임 → 이후 전 단계 오염 |
| ② 청킹 | 문서를 조각으로 | `RecursiveCharacterTextSplitter`, 400~512토큰·10~20% 오버랩부터 | 의미 경계 무시. semantic 청킹은 잘 설정됐을 때만 우세 |
| ③ 임베딩 | 청크→벡터 | BGE-M3(한국어·다국어), OpenAI `text-embedding-3-large`(3072D) / `-small`(1536D) | 최상위 모델 격차 <1점 → 도메인 평가셋으로 직접 비교 |
| ④ 벡터DB | 저장·인덱싱 | HNSW 인덱스. <5M=pgvector, 10M+=Qdrant | HNSW 빌드 시 OOM |
| ⑤ 검색 | 후보 뽑기 | 하이브리드: dense + BM25 병렬 → RRF(k=60) 융합 | 벡터만 쓰면 제품코드·고유명사 놓침 |
| ⑥ 리랭킹 | 정밀 재정렬 | cross-encoder (Cohere Rerank 3.5, Voyage rerank-2.5) | 후보 너무 적게 넘기면 recall 상한에 갇힘 |
| ⑦ 생성·인용 | LLM 답변+출처 | Anthropic Citations API (문자/페이지 단위 provenance) | 문서 있어도 파라메트릭 기억으로 답·오귀속 |

> **가성비 개선**: Anthropic Contextual Retrieval (청크마다 50~100토큰 맥락 부착)
> → 검색 실패율 35%↓, BM25 병행 49%↓, 리랭킹까지 67%↓.

### Layer 2 — 평가 (RAGAS)

"답이 맞는지"를 숫자로. **검색 실패인지 생성 실패인지 분리 진단**하는 게 핵심.

| 메트릭 | 축 | 측정 | 정답 필요? |
|---|---|---|---|
| **Faithfulness** | 생성 | 답의 각 주장이 검색문맥으로 뒷받침되는 비율. 환각 정량화 | ❌ (온라인 가능) |
| **Answer/Response Relevancy** | 생성 | 답에서 역생성한 질문과 원 질문의 임베딩 유사도 | ❌ |
| **Context Precision** | 검색 | 관련 청크가 상위에 랭크됐나 (Precision@k) | 기본형 필요 |
| **Context Recall** | 검색 | 정답 주장 중 검색이 놓치지 않은 비율 | ✅ (골든셋) |

- 완전 reference-free = **Faithfulness + Answer Relevancy 2개**. 검색축은 골든셋 필요.
- **골든셋**: `질문-문맥-정답` 삼중항 50~200개. 합성 생성 가능하나 **사람 검수 필수**.
- **회귀 테스트**: 프롬프트·모델·청킹 변경 시 같은 골든셋 재실행 → 점수 하락 감지 → CI 배포 차단.

### Layer 3 — 관측 (Langfuse)

블랙박스를 유리상자로. 없으면 "어느 요청이 왜 실패했는지·비용이 어디서 터지는지" 사후 재구성 불가.

- **계층형 trace**: 요청 1건 = 부모 trace + 자식 observation(검색·LLM·툴). `@observe()`로 자동.
- **토큰·비용·지연**: observation 단위 자동 집계, p50/p95 지연.
- **프롬프트 버저닝**: label 재지정만으로 코드 배포 없이 롤백 (클라이언트 캐시 TTL 60s).
- **score 객체**: 사람/LLM judge/코드체크 판정을 trace에 부착 → 추이·회귀 분석.
- **RAGAS 연동**: `langfuse.create_score(name, value, trace_id)`로 점수 push → Layer 2↔3 접착.
- MIT 오픈소스, self-host (Postgres·ClickHouse·Redis·MinIO `docker-compose`).

---

## 기술 스택

| 영역 | 선택 |
|---|---|
| API | FastAPI (Python) |
| 오케스트레이션 | LangChain / LangGraph |
| 임베딩 | BGE-M3 (한국어·다국어) |
| 벡터DB | pgvector (Postgres) — MVP 규모(<5M) |
| 검색 | 하이브리드 (pgvector dense + BM25) + RRF |
| 평가 | RAGAS + LLM-as-a-Judge |
| 관측 | Langfuse (self-host) |
| 생성 모델 | Claude / OpenAI (교체 가능) |

---

## 디렉토리 구조 (예정)

```
.
├── app/
│   ├── ingest/          # 파싱·청킹·임베딩·색인 (오프라인)
│   ├── retrieve/        # 하이브리드 검색 + 리랭킹
│   ├── generate/        # 프롬프트 조립·생성·인용
│   └── api.py           # FastAPI 엔드포인트 (@observe 계측)
├── eval/
│   ├── golden/          # 골든 데이터셋 (질문-문맥-정답)
│   ├── ragas_run.py     # RAGAS 4대 지표 실행 → Langfuse push
│   └── ci_gate.py       # 임계값 회귀 게이트 (pytest 호환)
├── observability/
│   └── langfuse_setup.py
├── docker-compose.yml   # Postgres(pgvector) + Langfuse 스택
├── .env.example
└── README.md
```

---

## 시작하기

### 1. 환경

```bash
git clone <repo>
cd domain-rag-eval-obs
cp .env.example .env        # API 키, DB URL, Langfuse 키 입력
```

`.env` 필수 항목:

```
OPENAI_API_KEY=...          # 또는 ANTHROPIC_API_KEY
DATABASE_URL=postgresql://...
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=http://localhost:3000
```

### 2. 인프라 (Postgres+pgvector, Langfuse)

```bash
docker compose up -d
```

### 3. 의존성 · 문서 색인

```bash
pip install -r requirements.txt
python -m app.ingest --source ./docs   # 문서 파싱→청킹→임베딩→pgvector
```

### 4. 실행

```bash
uvicorn app.api:app --reload
# POST /query  { "question": "..." }  → 답변 + 출처 + trace_id
```

### 5. 평가 실행

```bash
python -m eval.ragas_run --dataset eval/golden   # RAGAS 지표 → Langfuse
python -m eval.ci_gate --threshold faithfulness=0.9   # 회귀 게이트
```

---

## 언제 쓰나 (주의)

- **20만 토큰(약 500페이지) 미만이면 RAG를 만들지 마라.** 문서 전체를 프롬프트에 넣고 프롬프트 캐싱 쓰는 게 더 싸고 정확 (Anthropic 권고). VectorDB·임베딩·청킹이 과잉 엔지니어링.
- RAG 적합: ① 자주 바뀌는 데이터, ② 출처·근거 필수 규제 도메인, ③ 사내 지식 QA. 축 = **최신성 + 추적성 + 리소스 제약**.
- **평가·관측은 프로덕션이면 항상 얹는다.** RAG는 문서 갱신·모델 교체마다 조용히 무너지는(freshness gap) 상시 계측 대상.

---

## 효과

| 효과 | 메커니즘 |
|---|---|
| 근본원인 즉시 특정 | 검색축 vs 생성축 지표 분리 → "검색이 놓쳤나 / 생성이 지어냈나" 판별 |
| 회귀 조기 발견 | 골든셋 CI 게이트 → 사용자 불만 아니라 자체 알림으로 |
| 비용·지연 가시화 | observation 단위 토큰·비용·p95 |
| 반복 개발 가속 | 컴포넌트 격리 평가 (전체 LLM 호출 없이 청크크기 A/B) |
| 모델 선택 손해 방지 | 같은 컨텍스트라도 생성모델만으로 환각율 0.7%~11.2% 차이 |

> 운영지표 개선 사례(MTTR 반감 등)는 단일 벤더 자기보고 — "계측 방법"의 근거로만 인용, 검증된 벤치마크로 취급 금지.

---

## 로드맵 (2-4주 MVP)

- [ ] **1주** — RAG 골격: 파싱·청킹·임베딩·pgvector 색인 + 기본 검색
- [ ] **2주** — 하이브리드 검색(BM25+dense, RRF) + 리랭킹 + Langfuse trace 계측
- [ ] **3주** — RAGAS 골든셋 50~100개 + CI 회귀 게이트 + 비용/지연 대시보드
- [ ] **4주** — A/B 실험(청크크기·모델) 리포트 + "평가 수치로 개선한 과정" 문서화

---

## 참고

- Anthropic — [Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)
- [RAGAS 공식 문서](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/)
- [Langfuse — RAG observability & evals](https://langfuse.com/blog/2025-10-28-rag-observability-and-evals)
- 우아한형제들 — [LLMOps로 확장하는 AI플랫폼 2.0](https://techblog.woowahan.com/22839/) · [물어보새](https://techblog.woowahan.com/18144/)
- 카카오 — [FunctionChat-Bench](https://www.kakaocorp.com/page/detail/11253)

---

## 라이선스

MIT
