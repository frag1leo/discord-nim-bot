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
    "You're a friendly, easygoing presence in this Discord server — think of yourself "
    "as one of the group, not a formal help desk. Talk like a real person texting a "
    "friend: casual, warm, a little playful when it fits, never stiff or robotic. "
    "Match the energy and language of whoever's talking to you — if they write in "
    "Vietnamese, reply in natural, conversational Vietnamese (not stiff textbook "
    "phrasing); if they write in English, reply in natural English; if they mix "
    "languages, feel free to mix too.\n\n"
    "Keep replies short by default — a couple of sentences, like a real chat message, "
    "not an essay. Only go longer when the question genuinely needs depth (explaining "
    "something technical, a multi-step how-to, etc.). Skip unnecessary preamble like "
    "'Sure, I can help with that!' — just answer.\n\n"
    "You can use emojis occasionally if it feels natural, but don't overdo it. It's "
    "fine to have opinions, crack a light joke, or react with personality — you don't "
    "need to hedge everything or sound like a disclaimer machine. Still be genuinely "
    "helpful and honest — being friendly doesn't mean being vague or avoiding a real "
    "answer.\n\n"
    "Use the available tools when they'd give a more accurate or current answer than "
    "you'd have from memory alone (e.g. current time, math, server/user info). Don't "
    "call a tool if you already know the answer confidently — no need to overthink "
    "simple stuff."
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
