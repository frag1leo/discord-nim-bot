"""
Tool registry for the Discord bot.

Each tool has:
  - a JSON schema (OpenAI-compatible "function" format) describing it to the LLM
  - a Python function that actually executes it

Add new tools by writing a function + schema, then registering it in TOOLS at
the bottom of this file. Tools that need Discord context (e.g. server info)
receive an optional `discord_message` kwarg — the raw discord.Message that
triggered the request.
"""

import ast
import operator
import datetime
from zoneinfo import ZoneInfo


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def get_current_time(timezone: str = "UTC", **_) -> str:
    """Return the current date/time in the given IANA timezone."""
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        return f"Unknown timezone '{timezone}'. Use an IANA name like 'Asia/Ho_Chi_Minh' or 'UTC'."
    now = datetime.datetime.now(tz)
    return now.strftime("%Y-%m-%d %H:%M:%S %Z")


# Safe arithmetic evaluator (no eval() on arbitrary input)
_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("Unsupported expression")


def calculate(expression: str, **_) -> str:
    """Safely evaluate a basic arithmetic expression."""
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)
        return str(result)
    except Exception as e:
        return f"Could not evaluate '{expression}': {e}"


def get_server_info(discord_message=None, **_) -> str:
    """Return basic info about the Discord server the message came from."""
    if discord_message is None or discord_message.guild is None:
        return "No server context available (this may be a DM)."
    guild = discord_message.guild
    return (
        f"Server: {guild.name}\n"
        f"Members: {guild.member_count}\n"
        f"Created: {guild.created_at.strftime('%Y-%m-%d')}\n"
        f"Owner: {guild.owner}"
    )


def get_user_info(discord_message=None, **_) -> str:
    """Return basic info about the user who sent the message."""
    if discord_message is None:
        return "No user context available."
    author = discord_message.author
    joined = getattr(author, "joined_at", None)
    return (
        f"User: {author.display_name} ({author})\n"
        f"Joined server: {joined.strftime('%Y-%m-%d') if joined else 'N/A'}\n"
        f"Account created: {author.created_at.strftime('%Y-%m-%d')}"
    )


# ---------------------------------------------------------------------------
# Schemas (OpenAI-compatible function format, works with NIM tool-calling)
# ---------------------------------------------------------------------------

TOOLS = {
    "get_current_time": {
        "func": get_current_time,
        "schema": {
            "type": "function",
            "function": {
                "name": "get_current_time",
                "description": "Get the current date and time in a given timezone.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "timezone": {
                            "type": "string",
                            "description": "IANA timezone name, e.g. 'Asia/Ho_Chi_Minh' or 'UTC'. Defaults to UTC.",
                        }
                    },
                    "required": [],
                },
            },
        },
    },
    "calculate": {
        "func": calculate,
        "schema": {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": "Evaluate a basic arithmetic expression (+, -, *, /, %, **).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Arithmetic expression to evaluate, e.g. '(3 + 5) * 2'.",
                        }
                    },
                    "required": ["expression"],
                },
            },
        },
    },
    "get_server_info": {
        "func": get_server_info,
        "schema": {
            "type": "function",
            "function": {
                "name": "get_server_info",
                "description": "Get info about the current Discord server (name, member count, owner, creation date).",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
    },
    "get_user_info": {
        "func": get_user_info,
        "schema": {
            "type": "function",
            "function": {
                "name": "get_user_info",
                "description": "Get info about the Discord user who sent the current message.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
    },
}


def get_tool_schemas():
    """Return the list of tool schemas to pass to the LLM's `tools` param."""
    return [t["schema"] for t in TOOLS.values()]


def execute_tool(name: str, arguments: dict, discord_message=None) -> str:
    """Look up and run a tool by name, returning its string result."""
    tool = TOOLS.get(name)
    if tool is None:
        return f"Error: unknown tool '{name}'"
    try:
        return tool["func"](discord_message=discord_message, **arguments)
    except Exception as e:
        return f"Error running tool '{name}': {e}"
