# Discord NIM Chatbot (Railway)

A Discord chatbot backed by an LLM served via NVIDIA NIM's hosted cloud API,
with basic tool-calling support. Deployed on Railway as a persistent worker
process (no HTTP server — it holds an outbound Discord gateway connection).

## Files

- `bot.py` — Discord entrypoint: message events, per-channel history, replies
- `llm_client.py` — NIM client + the tool-calling loop (ReAct-style)
- `tools.py` — Tool registry: schemas + implementations (time, calculator,
  server info, user info)
- `Dockerfile` — container image Railway builds and runs
- `.env.example` — reference for which env vars are needed (on Railway these
  are set as Variables in the dashboard, not a `.env` file)
- `requirements.txt`
- `fly.toml` — leftover from an earlier Fly.io attempt, unused now; safe to
  delete or ignore

## 1. Create a Discord bot

- https://discord.com/developers/applications → New Application
- Bot tab → Reset Token → copy it (this is `DISCORD_BOT_TOKEN`)
- Enable "Message Content Intent" under Privileged Gateway Intents
- OAuth2 → URL Generator → scope `bot` → permissions: Send Messages,
  Read Message History → open the generated URL to invite it to your server

## 2. Get a NIM API key

- https://build.nvidia.com → pick a model that supports tool calling
  (e.g. Llama 3.3 70B Instruct, a Nemotron model) → generate an API key
  (this is `NIM_API_KEY`)

## 3. Push this project to a GitHub repo

Railway deploys from a Git repo (or you can use the Railway CLI to deploy
straight from this folder — see the CLI option below). If using GitHub:
```bash
git init
git add .
git commit -m "Initial commit"
# create a repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/discord-nim-bot.git
git branch -M main
git push -u origin main
```
Make sure `.env` is NOT committed — only `.env.example` should be. Add a
`.gitignore` with `.env` in it if you haven't already.

## 4. Create the Railway project

**Option A — Dashboard (easiest)**
1. Go to https://railway.app → New Project → "Deploy from GitHub repo"
2. Select your `discord-nim-bot` repo
3. Railway detects the `Dockerfile` automatically and builds from it

**Option B — Railway CLI (deploy directly from this folder, no GitHub needed)**
```bash
npm i -g @railway/cli
railway login
railway init
railway up
```

## 5. Set environment variables

In the Railway dashboard → your service → **Variables** tab, add:
| Key | Value |
|---|---|
| `DISCORD_BOT_TOKEN` | your Discord bot token |
| `NIM_API_KEY` | your NVIDIA NIM API key |
| `NIM_BASE_URL` | `https://integrate.api.nvidia.com/v1` |
| `NIM_MODEL` | `nvidia/nemotron-3-super-120b-a12b` (or another tool-calling model) |
| `REQUIRE_MENTION` | `true` |

(Or via CLI: `railway variables set DISCORD_BOT_TOKEN=... NIM_API_KEY=...` etc.)

## 6. Deploy

- Dashboard: pushing to your connected GitHub branch auto-deploys. Or click
  **Deploy** manually in the dashboard.
- CLI: `railway up`

Railway runs the Docker container's `CMD` (`python bot.py`) as a long-lived
process — no port needs to be exposed, and this repo doesn't declare one.

## 7. Check it's alive

- Dashboard → your service → **Deployments** tab → view logs, look for
  `Logged in as <bot name>`
- Or via CLI: `railway logs`

## How it works

1. `on_message` fires → message appended to that channel's rolling history
2. `NimClient.chat()` sends the history to NIM with the tool schemas from
   `tools.py`
3. If the model requests a tool call, `execute_tool()` runs it and the
   result is fed back to the model — this loops until the model gives a
   final text answer (capped at `MAX_TOOL_ITERATIONS` to avoid runaway loops)
4. The final answer is sent back to the Discord channel

## Adding a new tool

In `tools.py`:
1. Write a function `def my_tool(arg1: str, discord_message=None, **_) -> str`
2. Add its OpenAI-style schema + function to the `TOOLS` dict
3. That's it — `get_tool_schemas()` and `execute_tool()` pick it up automatically

## Persistence (optional upgrade)

Conversation history is in-memory per channel — it resets on redeploy or a
container restart. If you need it to survive restarts, add a Railway-hosted
Redis or Postgres plugin (one click in the dashboard's "New" → Database
menu) and swap the in-memory `conversations` dict in `bot.py` for
reads/writes to that store, keyed by channel ID. Not included by default to
keep the base deployment simple.

## Local development (optional)

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in values
python bot.py
```

## Notes

- Not every NIM-hosted model supports tool/function calling — check the
  model card on build.nvidia.com before picking one.
- Railway's free trial gives $5 of credit (no card required to start) —
  enough for roughly a month of a small bot like this one. Beyond that,
  you'll need to add a payment method to keep it running.
- This is a separate project from Mystique — no shared code, on purpose.
