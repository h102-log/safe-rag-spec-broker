# Step 1: generator

## 읽어야 할 파일

먼저 아래 파일들을 읽고 프로젝트의 아키텍처와 설계 의도를 파악하라:

- `/docs/ARCHITECTURE.md`
- `/docs/ADR.md` (특히 ADR-005: 교체 가능 인터페이스 선례)
- `/docs/next/20260722/handoff.md` (미결 1번·4번의 결정: Claude 기본 + `claude-opus-4-8`, generation 계측)
- `app/ingest/embed.py` — **이 step의 설계 원본.** `Embedder` Protocol + 구체 클래스(지연 import) + `get_embedder()` 팩토리 구조를 그대로 따른다.
- `app/config.py` — 설정 추가 위치. `anthropic_api_key` 필드가 이미 있다.
- `observability/langfuse_setup.py` — step 0에서 추가된 `update_generation(model, input_tokens, output_tokens)`과 `observe` 데코레이터를 사용한다.
- `requirements.txt`

이전 step에서 만들어진 코드를 꼼꼼히 읽고, 설계 의도를 이해한 뒤 작업하라.

## 작업

### 1. `app/generate/__init__.py` (신규, 빈 파일)

### 2. `app/generate/llm.py` (신규)

교체 가능한 LLM 생성 인터페이스(ADR-005의 `Embedder` 선례를 따름):

```python
@dataclass
class Generated:
    text: str
    model: str
    input_tokens: int
    output_tokens: int


class Generator(Protocol):
    def generate(self, system: str, prompt: str) -> Generated: ...


class ClaudeGenerator:
    def __init__(self, model: str | None = None) -> None: ...
    def generate(self, system: str, prompt: str) -> Generated: ...


def get_generator() -> Generator: ...
```

구현 규칙:

- `anthropic` SDK import와 클라이언트 생성은 **`ClaudeGenerator.__init__` 내부로 지연**한다. 이유: 계약 테스트와 소비 측 import가 anthropic 미설치·API 키 없이 가능해야 한다(embed.py의 FlagEmbedding 지연 선례).
- 클라이언트: `anthropic.Anthropic(api_key=get_settings().anthropic_api_key)` — 키가 None이면 SDK가 환경변수로 폴백한다. 키를 코드·커밋에 넣지 마라(.env로만).
- `generate()`는 `@observe(name="generate", as_type="generation")`으로 계측한다. **CRITICAL: 계측 없는 LLM 호출 금지.** 이 데코레이터 덕분에 API의 `query` trace 아래에서 `search` span과 형제인 generation span이 된다.
- `generate()` 내부: `client.messages.create(model=self.model, max_tokens=2048, system=system, messages=[{"role": "user", "content": prompt}])` 호출 → 응답 content 블록 중 `type == "text"`인 블록의 텍스트를 이어붙여 answer 텍스트로 삼는다(블록 타입을 확인하지 않고 `content[0].text`를 읽지 마라 — thinking 블록이 섞일 수 있다). `max_tokens=2048`은 근거 기반 단답이 목적이라 충분하다.
- 호출 직후 `update_generation(model=self.model, input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens)`로 usage를 기록하고, 같은 값으로 `Generated`를 채워 반환한다.
- `get_generator()`: `get_settings().generation_model`을 읽어 `ClaudeGenerator`를 반환(get_embedder 선례). 소비 측은 반환값(`Generator`)에만 의존한다.
- OpenAI 구현체는 만들지 마라 — 인터페이스만 있으면 나중에 클래스 하나로 추가 가능(handoff 결정 1, YAGNI).

### 3. `app/config.py` 수정

`Settings`에 한 줄 추가:

```python
generation_model: str = "claude-opus-4-8"
```

### 4. `requirements.txt` 수정

`anthropic` 한 줄 추가.

### 5. 테스트 `tests/test_generate.py` (신규)

실제 LLM 호출 없이 검증한다(handoff AC):

- **계약 테스트**: `Generator` Protocol을 만족하는 `FakeGenerator`(고정 `Generated` 반환)를 만들어 시그니처·반환 타입 계약을 고정한다(test_embed.py의 FakeEmbedder 선례).
- **import 테스트**: `from app.generate.llm import ClaudeGenerator, Generated, Generator, get_generator`가 anthropic 미설치·키 없는 환경에서 성공하는지(지연 import 검증).
- `ClaudeGenerator`를 인스턴스화하거나 실제 API를 호출하는 테스트는 쓰지 마라.

## Acceptance Criteria

```bash
python -m pytest tests/test_generate.py -q   # 계약·import 테스트 통과
pytest                                       # 전체 스위트 무손상
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - ARCHITECTURE.md 디렉토리 구조를 따르는가? (`app/generate` 레이어 신설)
   - ADR 기술 스택을 벗어나지 않았는가? (생성 모델: Claude, 교체 가능)
   - CLAUDE.md CRITICAL 규칙을 위반하지 않았는가? (LLM 호출 계측, 키는 .env로만)
3. 결과에 따라 `phases/1-generate/index.json`의 해당 step을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "산출물 한 줄 요약"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 (API 키, 외부 인증, 수동 설정 등) → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 답변 조합 로직(프롬프트 구성, no-context 처리, citations)을 여기 만들지 마라. 이유: step 2(`answer`)의 범위다. 이 step은 LLM 호출 인터페이스만 다룬다.
- `app/api.py`를 수정하지 마라. 이유: API 배선은 step 3의 범위다.
- `anthropic`을 모듈 최상단에서 import하지 마라. 이유: 미설치 환경에서 소비 측 import가 전부 깨진다.
- OpenAI 구현체·retry·streaming 등 요청받지 않은 기능을 추가하지 마라.
- 기존 테스트를 깨뜨리지 마라.
