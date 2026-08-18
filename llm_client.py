"""
Thin wrapper around NVIDIA NIM's OpenAI-compatible chat completions API,
including the tool-calling (ReAct-style) loop.

NIM exposes /v1/chat/completions in the same shape as OpenAI, so the
official `openai` Python SDK works as-is by just pointing base_url at NIM.
"""

import json
import os
import logging

from openai import OpenAI

from tools import get_tool_schemas, execute_tool

logger = logging.getLogger("llm_client")

MAX_TOOL_ITERATIONS = 5  # safety cap so a stuck loop can't run forever

SYSTEM_PROMPT = (
    "You are a helpful assistant in a Discord server. Be concise and friendly. "
    "Use the available tools when they would give a more accurate or up-to-date "
    "answer than you could give from memory alone. Don't call a tool if you "
    "already know the answer."
)


class NimClient:
    def __init__(self):
        api_key = os.environ["NIM_API_KEY"]
        base_url = os.environ.get("NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")
        self.model = os.environ.get("NIM_MODEL", "nvidia/nemotron-3-super-120b-a12b")
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def chat(self, history: list[dict], discord_message=None) -> str:
        """
        Run one turn of the conversation, including any tool calls the model
        makes along the way. `history` is a list of {"role", "content"} dicts
        (without the system prompt — that's added here). Returns the final
        assistant text reply.
        """
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history]
        tools = get_tool_schemas()

        for _ in range(MAX_TOOL_ITERATIONS):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
            choice = response.choices[0]
            msg = choice.message

            if not msg.tool_calls:
                # Model gave a final answer — done.
                return msg.content or "(no response)"

            # Model wants to call one or more tools. Append its request,
            # execute each tool, append the results, then loop back so the
            # model can see the results and respond.
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
            )

            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                logger.info("Calling tool %s with args %s", tc.function.name, args)
                result = execute_tool(tc.function.name, args, discord_message=discord_message)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )

        # Hit MAX_TOOL_ITERATIONS without a final answer — force one last
        # call with no tools so we still return something useful.
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return response.choices[0].message.content or "(no response after tool calls)"
