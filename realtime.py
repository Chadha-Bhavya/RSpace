"""Small helpers shared by the realtime voice pipeline."""

from __future__ import annotations

import re


class SentenceChunker:
    """Turn model deltas into natural chunks suitable for streaming TTS."""

    def __init__(self, soft_limit: int = 110) -> None:
        self.buffer = ""
        self.soft_limit = soft_limit

    def push(self, delta: str) -> list[str]:
        self.buffer += delta
        ready: list[str] = []
        while True:
            sentence = re.match(r"^(.+?[.!?])(?:\s+|$)", self.buffer, re.DOTALL)
            if sentence:
                value = sentence.group(1).strip()
                self.buffer = self.buffer[sentence.end():]
                if value:
                    ready.append(value)
                continue

            if len(self.buffer) >= self.soft_limit:
                boundary = max(
                    self.buffer.rfind(", ", 0, self.soft_limit),
                    self.buffer.rfind("; ", 0, self.soft_limit),
                )
                if boundary >= 35:
                    ready.append(self.buffer[: boundary + 1].strip())
                    self.buffer = self.buffer[boundary + 2 :]
                    continue
            break
        return ready

    def finish(self) -> str:
        value = self.buffer.strip()
        self.buffer = ""
        return value
