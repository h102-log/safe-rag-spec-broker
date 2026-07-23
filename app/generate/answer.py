"""검색 문맥 → 근거 기반 답변 조립 (인용 포함, CLAUDE.md CRITICAL).

- no-context 게이트: 근거 없으면 LLM 미호출·고정 거절 — 할루시네이션 방지 (handoff 결정 3).
- citations는 LLM에 전달한 retrieved에서 서버가 구성한다 — LLM 출력에서 출처를
  파싱하지 않아 지어낸 출처를 구조적으로 차단한다 (handoff 결정 2).
- @observe 없음: LLM 계측은 ClaudeGenerator.generate에 있고, 거절 경로는 LLM 호출이 없다.
- Retrieved는 데이터 타입으로만 import — search() 호출은 api(step 3)의 몫 (레이어 경계).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.generate.llm import Generator
from app.retrieve.search import Retrieved

REFUSAL = "제공된 문서에서 근거를 찾지 못했습니다."

SYSTEM = (
    "너는 폐쇄 문서집합 QA 어시스턴트다. 반드시 아래 규칙을 지켜라.\n"
    "1. 주어진 문맥에만 근거해 답하라. 문맥에 없는 지식(파라메트릭 기억)으로 답하지 마라.\n"
    "2. 문맥에 답이 없으면 지어내지 말고 모른다고 답하라.\n"
    "3. 답변 문장 끝에 근거가 된 청크 번호를 [n] 형식으로 표기하라."
)


@dataclass
class Answered:
    answer: str
    citations: list[Retrieved]


def generate_answer(
    question: str, retrieved: list[Retrieved], generator: Generator
) -> Answered:
    from app.config import get_settings

    threshold = get_settings().no_context_threshold
    if not retrieved or max(r.score for r in retrieved) < threshold:
        return Answered(answer=REFUSAL, citations=[])

    context = "\n\n".join(
        f"[{i}] (출처: {r.source}" + (f", p.{r.page}" if r.page is not None else "") + ")\n"
        + r.text
        for i, r in enumerate(retrieved, 1)
    )
    prompt = f"문맥:\n{context}\n\n질문: {question}"
    generated = generator.generate(SYSTEM, prompt)
    return Answered(answer=generated.text, citations=retrieved)
