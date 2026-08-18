import os

from fastapi import APIRouter, Depends, HTTPException
from openai import APIError, OpenAI

from app.auth import require_auth

router = APIRouter(prefix="/api/ai", tags=["ai"], dependencies=[Depends(require_auth)])

MODEL = "openai/gpt-oss-120b"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def get_client() -> OpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY is not configured")
    return OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL)


def ask(client: OpenAI, prompt: str) -> str:
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
    except APIError as exc:
        raise HTTPException(status_code=502, detail=f"OpenRouter request failed: {exc}") from exc

    content = response.choices[0].message.content if response.choices else None
    if not content:
        raise HTTPException(status_code=502, detail="OpenRouter returned an empty response")

    return content


@router.get("/ping")
def ping() -> dict[str, str]:
    client = get_client()
    reply = ask(client, "what is 2+2?")
    return {"reply": reply}
