"""FastAPI 엔드포인트. 온라인 질의 경로는 @observe로 계측한다(step 5+)."""
from fastapi import FastAPI

app = FastAPI(title="domain-rag-eval-obs")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
