"""
Slash commands for the bot (/poll, /vote, etc).

Registered onto a discord.app_commands.CommandTree via setup_commands(tree).
Add new slash commands here by writing a new @tree.command function inside
setup_commands, following the same pattern as poll/vote below.
"""

import discord
from discord import app_commands

# Number emojis used for poll reactions, in order (supports up to 10 options)
NUMBER_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


def _build_poll_embed(question: str, options: list[str], author: discord.abc.User) -> discord.Embed:
    description = "\n".join(f"{NUMBER_EMOJIS[i]} {opt}" for i, opt in enumerate(options))
    embed = discord.Embed(title=f"📊 {question}", description=description, color=discord.Color.blurple())
    embed.set_footer(text=f"Poll by {author.display_name} • React to vote")
    return embed


def setup_commands(tree: app_commands.CommandTree):
    @tree.command(name="poll", description="Create a quick reaction poll with up to 10 options")
    @app_commands.describe(
        question="The poll question",
        options="Options separated by | (e.g. Pizza | Sushi | Burgers), 2-10 options",
    )
    async def poll(interaction: discord.Interaction, question: str, options: str):
        opts = [o.strip() for o in options.split("|") if o.strip()]

        if len(opts) < 2:
            await interaction.response.send_message(
                "Need at least 2 options, separated by `|` — e.g. `Pizza | Sushi | Burgers`",
                ephemeral=True,
            )
            return
        if len(opts) > 10:
            await interaction.response.send_message(
                "Max 10 options for a reaction poll — trim it down a bit.",
                ephemeral=True,
            )
            return

        embed = _build_poll_embed(question, opts, interaction.user)
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        for i in range(len(opts)):
            await message.add_reaction(NUMBER_EMOJIS[i])

    @tree.command(name="vote", description="Alias for /poll — create a quick reaction poll")
    @app_commands.describe(
        question="The poll question",
        options="Options separated by | (e.g. Yes | No | Maybe), 2-10 options",
    )
    async def vote(interaction: discord.Interaction, question: str, options: str):
        await poll.callback(interaction, question, options)

    @tree.command(name="yesno", description="Quick yes/no poll")
    @app_commands.describe(question="The question to ask")
    async def yesno(interaction: discord.Interaction, question: str):
        opts = ["Yes", "No"]
        embed = _build_poll_embed(question, opts, interaction.user)
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        await message.add_reaction("✅")
        await message.add_reaction("❌")
