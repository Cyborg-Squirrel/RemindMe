"""A Discord chat bot powered by AI"""

import multiprocessing as mp
from datetime import datetime
from typing import Optional

import discord
from discord.abc import Messageable
from discord.ext import commands

from taskuccino import (DiscordResponseCog, OllamaClient, load_config,
                        load_system_prompt)
from taskuccino._types import (ChatMessage, ChatRole, DiscordChatBotRequest,
                               DiscordMessage)
from taskuccino.background_reminder_cog import BackgroundReminderCog
from taskuccino.ollama_processor import OllamaProcessor

intents = discord.Intents.default()
intents.message_content = True

system_prompt = load_system_prompt()
bot_config = load_config()
bot = commands.Bot(
    command_prefix=commands.when_mentioned,
    description="Nothing to see here!",
    intents=intents,
)
ollama_client = OllamaClient(
    api_url=bot_config.api_url, models=bot_config.models
)

ollama_request_queue = mp.Queue()
ollama_response_queue = mp.Queue()

ollama_processor = OllamaProcessor(
    ollama_request_queue, ollama_response_queue, system_prompt, ollama_client
)

@bot.event
async def on_guild_join(self, guild):
    print(f"Joined guild {guild}")
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)

@bot.event
async def on_ready():
    """Called when the bot has successfully connected to Discord"""
    print(f"{bot.user} has connected to Discord!")
    print(f"Bot is in {len(bot.guilds)} guild(s)")
    await bot.add_cog(DiscordResponseCog(bot, ollama_response_queue))
    await bot.add_cog(BackgroundReminderCog(bot, ollama_request_queue))
    for guild in bot.guilds:
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)


async def on_bot_mentioned(message: discord.Message):
    """Called when the bot is mentioned in a message"""
    if not isinstance(message.channel, discord.abc.Messageable):
        print(f"Channel {message.channel} is not messageable, cannot respond")
        return
    if bot_config.react_to_messages:
        reaction_emoji = bot_config.reaction_emoji
        await message.add_reaction(reaction_emoji)

    image_attachments = [
        a
        for a in message.attachments
        if a.content_type and a.content_type.startswith("image/")
    ]
    image_attachment_bytes = []

    if len(image_attachments) > 0:
        await message.reply("Give me a moment to look at what you sent")

    for image_attachment in image_attachments:
        if (
            image_attachment.content_type
            and image_attachment.content_type.startswith("image/")
        ):
            image_bytes = await image_attachment.read()
            image_attachment_bytes.append(image_bytes)

    channel = message.channel
    history: list[ChatMessage] = []
    if isinstance(channel, Messageable):
        async for history_message in channel.history(limit=100):
            if len(history) < 20:
                role: Optional[ChatRole] = None
                if history_message.author == message.author:
                    role = ChatRole.user
                elif history_message.author == bot.user:
                    role = ChatRole.assistant
                if role is not None:
                    history.append(
                        ChatMessage(
                            role, history_message.content, message.created_at
                        )
                    )
            else:
                break

    message_channel_id = message.channel.id  # type: ignore
    ollama_request = DiscordChatBotRequest(
        message=DiscordMessage(
            ChatRole.user,
            message.content,
            message.created_at,
            message_channel_id,
            message.id,
            image_attachment_bytes,
        ),
        history=history,
    )
    ollama_request_queue.put(ollama_request)


@bot.event
async def on_message(message):
    """Called when any message is sent where the bot has access"""
    if message.author == bot.user:
        return

    if isinstance(message.channel, discord.DMChannel):
        bot.loop.create_task(on_bot_mentioned(message))
        return

    if isinstance(message.channel, discord.TextChannel):
        bot_mentioned = [user for user in message.mentions if user == bot.user]
        if bot_mentioned:
            await on_bot_mentioned(message)


class ReminderSlashCommandOption(discord.Enum, str):
    add = "add"
    remove = "remove"
    list = "list"


@bot.tree.command()
@discord.app_commands.describe(
    option="""
    Add, remove, or list all configured reminders.
    """,
    reminder="""The reminder to add or remove""",
)
async def reminder(
    interaction: discord.Interaction,
    option: Optional[ReminderSlashCommandOption],
    reminder: Optional[str] = None,
):
    """Adds or removes a reminder"""
    if option is None:
        await interaction.response.send_message(f"An option is required.")
    elif option == ReminderSlashCommandOption.list:
        print(f"{option} {reminder}")
        await interaction.response.send_message(f"TODO")
    else:
        if reminder is not None:
            print(f"{option} {reminder}")
            await interaction.response.send_message(f"{option} {reminder}")
        await interaction.response.send_message(f"No reminder specified.")


def main():
    """Main entry point"""
    token = bot_config.token

    if bot_config.token is None or bot_config.token == "":
        raise ValueError(
            "Discord token is required in config.json."
            "Please update the config file with your bot token."
        )

    try:
        ollama_processor.start()
        bot.run(token)
    except discord.errors.LoginFailure:
        print("Error: Invalid Discord token")


if __name__ == "__main__":
    main()
