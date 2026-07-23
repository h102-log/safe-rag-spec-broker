# Step 3: ci-gate

## 읽어야 할 파일

먼저 아래 파일들을 읽고 프로젝트의 아키텍처와 설계 의도를 파악하라:

- `/docs/ARCHITECTURE.md`
- `/docs/ADR.md` (특히 ADR-003)
- `/docs/next/20260724/handoff.md` (§4 결정 5: ci_gate 계약 — threshold 파싱, 미달 시 exit 1)
- `eval/ragas_run.py` — step 2의 결과 파일 포맷(`eval/results/latest.json`의 `metrics` 키). **이 포맷이 이 step의 입력 계약이다.**
- `eval/dataset.py`, `tests/test_eval_dataset.py` — eval 레이어 테스트 선례.

이전 step에서 만들어진 코드를 꼼꼼히 읽고, 설계 의도를 이해한 뒤 작업하라.

## 작업

### 1. `eval/ci_gate.py` (신규)

`python -m eval.ci_gate --threshold faithfulness=0.9` 진입점(CLAUDE.md 커맨드 계약).

```python
def parse_thresholds(specs: list[str]) -> dict[str, float]:
    """["faithfulness=0.9", "answer_relevancy=0.7"] → {지표: 임계값}. 형식 오류는 예외."""


def check(metrics: dict[str, float], thresholds: dict[str, float]) -> list[str]:
    """위반 사유 목록. 통과면 빈 리스트."""


def main(argv: list[str] | None = None) -> int:
    """0=통과, 1=미달. 사유는 stdout에 출력."""
```

구현 규칙:

- `--threshold`는 복수 지정 허용(`--threshold faithfulness=0.9 answer_relevancy=0.7` 또는 옵션 반복 — argparse 재량).
- `--results` 옵션으로 결과 파일 경로를 받되 기본값은 `eval/results/latest.json`.
- **게이트는 보수적으로 실패한다**: 결과 파일이 없거나, threshold에 지정한 지표가 결과의 `metrics`에 없으면 통과가 아니라 사유 출력 + exit 1. 이유: 회귀 게이트가 "평가를 안 돌렸는데 통과"를 내면 존재 의미가 없다.
- 판정은 `metrics`의 집계값 기준. `metrics[지표] >= 임계값`이면 통과.
- LLM·DB·ragas 어디에도 의존하지 않는다 — 결과 파일만 읽는다.

### 2. 테스트 `tests/test_ci_gate.py` (신규)

- `parse_thresholds`: 정상 파싱, 형식 오류(`=` 없음, 숫자 아님) 시 예외.
- `check`: 통과 / 미달 / 지표 없음 각 케이스.
- `main`: tmp_path의 결과 파일 픽스처로 exit code 0/1, 결과 파일 없음 → 1.

## Acceptance Criteria

```bash
python -m pytest tests/test_ci_gate.py -q   # 신규 테스트 통과 (LLM·DB·ragas 불필요)
pytest                                      # 전체 스위트 무손상 (integration은 기본 deselect)
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - ARCHITECTURE.md 디렉토리 구조를 따르는가? (eval 레이어만)
   - ADR 기술 스택을 벗어나지 않았는가?
   - CLAUDE.md CRITICAL 규칙을 위반하지 않았는가?
3. 결과에 따라 `phases/2-eval/index.json`의 해당 step을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "산출물 한 줄 요약"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 (API 키, 외부 인증, 수동 설정 등) → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `ragas`·LLM SDK를 import하지 마라. 이유: 게이트는 결과 파일만 읽는다 — CI에서 무거운 의존성 없이 실행 가능해야 한다.
- 게이트 안에서 평가를 직접 실행(ragas_run 호출)하지 마라. 이유: 실행과 판정을 분리해야 CI에서 캐시된 결과로 판정만 재실행할 수 있다.
- `app/` 하위 코드를 수정하지 마라. 이유: eval 레이어는 app과 분리된다(CLAUDE.md 레이어 규칙).
- 기존 테스트를 깨뜨리지 마라.
