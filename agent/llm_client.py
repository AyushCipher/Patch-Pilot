"""Thin wrapper around the Groq chat-completions API with tool use.

Groq exposes an OpenAI-compatible Chat Completions API. This module owns
the one place that translates between PatchPilot's internal, provider-
agnostic message/content-block shape (used by agent/core.py) and Groq's
wire format (system-role message, assistant tool_calls, role="tool"
results). agent/core.py never has to know which provider is behind it.

Model is configurable via the PATCHPILOT_MODEL env var, never hardcoded
into the reasoning loop.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from groq import Groq

from agent.tools import TOOL_SCHEMAS

DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_MAX_TOKENS = 4096


@dataclass
class LLMResponse:
    content_blocks: list[dict]
    stop_reason: str
    input_tokens: int
    output_tokens: int
    raw_text: str


def _to_groq_tool_schemas() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }
        for tool in TOOL_SCHEMAS
    ]


def _translate_messages(messages: list[dict], system_prompt: str) -> list[dict]:
    """Convert PatchPilot's internal message list (role + content-block
    list, see agent/core.py) into Groq/OpenAI-style chat messages."""
    wire: list[dict] = [{"role": "system", "content": system_prompt}]

    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if role == "assistant":
            text_parts = []
            tool_calls = []
            for block in content:
                if block["type"] == "text":
                    text_parts.append(block["text"])
                elif block["type"] == "tool_use":
                    tool_calls.append(
                        {
                            "id": block["id"],
                            "type": "function",
                            "function": {
                                "name": block["name"],
                                "arguments": json.dumps(block["input"]),
                            },
                        }
                    )
            assistant_msg: dict = {"role": "assistant", "content": "\n".join(text_parts) or None}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            wire.append(assistant_msg)

        elif role == "user":
            if isinstance(content, str):
                wire.append({"role": "user", "content": content})
                continue
            trailing_text = []
            for block in content:
                if block.get("type") == "tool_result":
                    wire.append(
                        {
                            "role": "tool",
                            "tool_call_id": block["tool_use_id"],
                            "content": block["content"],
                        }
                    )
                elif block.get("type") == "text":
                    trailing_text.append(block["text"])
            if trailing_text:
                wire.append({"role": "user", "content": "\n".join(trailing_text)})
        else:
            wire.append(msg)

    return wire


class LLMClient:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.client = Groq(api_key=api_key or os.environ.get("GROQ_API_KEY"))
        self.model = model or os.environ.get("PATCHPILOT_MODEL", DEFAULT_MODEL)

    def send(self, system_prompt: str, messages: list[dict]) -> LLMResponse:
        wire_messages = _translate_messages(messages, system_prompt)
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=DEFAULT_MAX_TOKENS,
            messages=wire_messages,
            tools=_to_groq_tool_schemas(),
        )

        choice = response.choices[0]
        message = choice.message

        content_blocks = []
        text_parts = []
        if message.content:
            content_blocks.append({"type": "text", "text": message.content})
            text_parts.append(message.content)

        for tool_call in message.tool_calls or []:
            try:
                tool_input = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
            except json.JSONDecodeError:
                tool_input = {}
            content_blocks.append(
                {
                    "type": "tool_use",
                    "id": tool_call.id,
                    "name": tool_call.function.name,
                    "input": tool_input,
                }
            )

        usage = response.usage
        return LLMResponse(
            content_blocks=content_blocks,
            stop_reason=choice.finish_reason,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            raw_text="\n".join(text_parts),
        )
