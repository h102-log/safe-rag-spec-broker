# Step 1: eval-dataset

## 읽어야 할 파일

먼저 아래 파일들을 읽고 프로젝트의 아키텍처와 설계 의도를 파악하라:

- `/docs/ARCHITECTURE.md` (레이어 분리: `eval`은 `app/*`과 별도 레이어)
- `/docs/ADR.md` (특히 ADR-003: 생성축은 reference-free — 1차 데이터셋은 질문만 있으면 된다)
- `/docs/next/20260724/handoff.md` (§4 결정 1·2·5: 1차는 생성축만, 데이터셋은 jsonl, 골든셋은 2차)
- `docs/PRD.md`, `docs/ADR.md`, `docs/ARCHITECTURE.md`, `docs/wiki/README.md` — 현재 색인된 문서집합(`python -m app.ingest --source ./docs` 대상). **질문은 반드시 이 문서들에서 답을 찾을 수 있어야 한다.**

이전 step에서 만들어진 코드를 꼼꼼히 읽고, 설계 의도를 이해한 뒤 작업하라.

## 작업

### 1. `eval/__init__.py` (신규, 빈 파일)

### 2. `eval/golden/questions.jsonl` (신규)

평가용 질문 데이터셋. 한 줄에 JSON 객체 하나:

```jsonl
{"question": "임베딩 모델은 무엇을 쓰고 왜 선택했나?"}
```

- 현재 색인된 프로젝트 docs(`./docs` 하위, 8문서)에서 **답을 찾을 수 있는 질문 10~20개**를 작성한다.
- 질문 주제는 문서 전반에 고르게: 기술 스택 선택 이유(ADR), 아키텍처·데이터 흐름, 평가·관측 방침 등.
- 1차는 생성축(reference-free)이므로 `question` 필드만 둔다. 정답·문맥 필드를 추가하지 마라(골든셋은 2차).
- 이 파일은 **사람 검수 대상 산출물**이다 — 문서에 근거한 자연스러운 한국어 질문으로 쓴다.

### 3. `eval/dataset.py` (신규)

```python
def load_questions(path: str | Path) -> list[str]:
    """jsonl에서 question 문자열 목록을 로드.

    path가 디렉토리면 그 안의 questions.jsonl을 읽는다
    (CLI 계약: --dataset eval/golden).
    """
```

- 빈 줄은 건너뛴다. 그 외 파싱 실패는 그대로 예외를 낸다(조용히 삼키지 마라 — 데이터셋 오염을 숨기면 안 된다).

### 4. 테스트 `tests/test_eval_dataset.py` (신규)

- tmp_path에 만든 jsonl 픽스처로 `load_questions` 검증: 질문 목록 반환, 디렉토리 경로 지원, 빈 줄 무시.
- 실제 `eval/golden/questions.jsonl`이 로드되고 질문이 10개 이상인지 검증(데이터셋 파일 자체의 회귀 방지).

## Acceptance Criteria

```bash
python -m pytest tests/test_eval_dataset.py -q   # 신규 테스트 통과
pytest                                           # 전체 스위트 무손상 (integration은 기본 deselect)
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - ARCHITECTURE.md 디렉토리 구조를 따르는가? (`eval` 레이어 신설, `app/*` 무수정)
   - ADR 기술 스택을 벗어나지 않았는가?
   - CLAUDE.md CRITICAL 규칙을 위반하지 않았는가?
3. 결과에 따라 `phases/2-eval/index.json`의 해당 step을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "산출물 한 줄 요약"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 (API 키, 외부 인증, 수동 설정 등) → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 문서에 근거가 없거나 무관한 질문을 넣지 마라. 이유: 생성축 지표(Faithfulness·Answer Relevancy)는 근거 있는 답변을 전제한다 — 거절 경로가 섞이면 지표가 왜곡된다.
- `ragas`를 import하거나 requirements에 추가하지 마라. 이유: RAGAS 배선은 step 2의 범위다. 이 step은 데이터셋과 로더만 다룬다.
- `app/` 하위 코드를 수정하지 마라. 이유: eval 레이어는 app과 분리된다(CLAUDE.md 레이어 규칙).
- 정답(ground truth)·문맥 필드나 그 처리 로직을 추가하지 마라. 이유: 검색축 골든셋은 2차 범위다(handoff §4 결정 1·2, YAGNI).
- 기존 테스트를 깨뜨리지 마라.
