"""
Discord chatbot entrypoint.

- Listens for messages (mention-gated by default, see REQUIRE_MENTION)
- Keeps a short rolling conversation history per channel
- Sends the conversation to NVIDIA NIM via llm_client, including tool-calling
- Replies in Discord with the model's final answer

Run:
    pip install -r requirements.txt
    cp .env.example .env   # fill in DISCORD_BOT_TOKEN and NIM_API_KEY
    python bot.py
"""

import os
import logging
from collections import defaultdict, deque

import discord
from dotenv import load_dotenv

from llm_client import NimClient

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

DISCORD_BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
REQUIRE_MENTION = os.environ.get("REQUIRE_MENTION", "true").lower() == "true"

HISTORY_LIMIT = 20  # messages kept per channel (user+assistant turns combined)

intents = discord.Intents.default()
intents.message_content = True  # required to read message text

client = discord.Client(intents=intents)
llm = NimClient()

# channel_id -> deque of {"role": ..., "content": ...}
conversations: dict[int, deque] = defaultdict(lambda: deque(maxlen=HISTORY_LIMIT))


def strip_mention(content: str, bot_user: discord.ClientUser) -> str:
    return content.replace(f"<@{bot_user.id}>", "").replace(f"<@!{bot_user.id}>", "").strip()


@client.event
async def on_ready():
    logger.info("Logged in as %s (id=%s)", client.user, client.user.id)


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    is_mentioned = client.user in message.mentions
    if REQUIRE_MENTION and not is_mentioned:
        return

    content = strip_mention(message.content, client.user) if is_mentioned else message.content
    if not content:
        return

    history = conversations[message.channel.id]
    history.append({"role": "user", "content": content})

    async with message.channel.typing():
        try:
            reply = llm.chat(list(history), discord_message=message)
        except Exception as e:
            logger.exception("LLM call failed")
            reply = f"Sorry, something went wrong talking to the model: {e}"

    history.append({"role": "assistant", "content": reply})

    # Discord message length cap is 2000 chars — split if needed.
    for i in range(0, len(reply), 2000):
        await message.channel.send(reply[i : i + 2000])


if __name__ == "__main__":
    client.run(DISCORD_BOT_TOKEN)
