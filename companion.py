"""Reply providers for the RSpace companion.

Keep this module independent of FastAPI and speech providers.  Replacing the
temporary OpenAI implementation later only requires another ReplyProvider.
"""

import os
from typing import Protocol

import httpx


COMPANION_INSTRUCTIONS = """You are RSpace, a warm, patient companion for an older adult who may be lonely.
Listen first. Respond in plain, gentle English using one to three short sentences.
Reflect one feeling or detail they shared, then ask one easy, open-ended follow-up question when appropriate.
Do not rush to fix things, diagnose, lecture, or make promises you cannot keep.
Never claim to be human, a professional, or a replacement for loved ones.
If they mention immediate danger, self-harm, abuse, or a medical emergency, gently encourage them to call local emergency services now or contact a trusted person nearby.
"""


class ReplyProvider(Protocol):
    async def reply(self, user_text: str) -> str: ...


class OpenAIReplyProvider:
    """Temporary implementation; replace this class when the custom algorithm is ready."""

    def __init__(self, client: httpx.AsyncClient, api_key: str, model: str) -> None:
        self.client = client
        self.api_key = api_key
        self.model = model

    async def reply(self, user_text: str) -> str:
        response = await self.client.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "instructions": COMPANION_INSTRUCTIONS,
                "input": user_text,
                # Keep reasoning light for a fast conversational turn while
                # leaving enough budget for both reasoning and the spoken reply.
                "reasoning": {"effort": "minimal"},
                "max_output_tokens": 500,
                # Do not retain these sensitive conversations in this temporary layer.
                "store": False,
            },
        )
        response.raise_for_status()
        answer = extract_output_text(response.json())
        if not answer:
            raise ValueError("The reply provider returned no text.")
        return answer


def extract_output_text(data: dict) -> str:
    """Read text from both SDK-shaped and raw Responses API payloads."""
    if data.get("output_text"):
        return str(data["output_text"]).strip()

    parts: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(content["text"])
    return "\n".join(parts).strip()


def create_reply_provider(client: httpx.AsyncClient) -> ReplyProvider:
    """Single seam to switch providers later (for example, to a custom service)."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("your_"):
        raise RuntimeError("OPENAI_API_KEY is not configured. Add it to your .env file.")
    return OpenAIReplyProvider(client, api_key, os.getenv("OPENAI_MODEL", "gpt-5-mini"))
