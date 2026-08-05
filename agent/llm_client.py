"""Thin wrapper around the Anthropic Messages API with tool use.

Model is configurable via the PATCHPILOT_MODEL env var, never hardcoded
into the reasoning loop. This module only knows how to talk to the API -
it has no opinion about the agent loop's control flow.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import anthropic

from agent.tools import TOOL_SCHEMAS

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_MAX_TOKENS = 4096


@dataclass
class LLMResponse:
    content_blocks: list[dict]
    stop_reason: str
    input_tokens: int
    output_tokens: int
    raw_text: str


class LLMClient:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model or os.environ.get("PATCHPILOT_MODEL", DEFAULT_MODEL)

    def send(self, system_prompt: str, messages: list[dict]) -> LLMResponse:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=DEFAULT_MAX_TOKENS,
            system=system_prompt,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        content_blocks = []
        text_parts = []
        for block in response.content:
            if block.type == "text":
                content_blocks.append({"type": "text", "text": block.text})
                text_parts.append(block.text)
            elif block.type == "tool_use":
                content_blocks.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )

        return LLMResponse(
            content_blocks=content_blocks,
            stop_reason=response.stop_reason,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            raw_text="\n".join(text_parts),
        )
