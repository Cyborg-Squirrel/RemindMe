"""AI response cog for Discord bot."""
import multiprocessing as mp

from discord.abc import Messageable
from discord.ext import commands, tasks

from taskuccino._types import (DiscordBackgroundBotResponse,
                               DiscordChatBotResponse)


class DiscordResponseCog(commands.Cog):
    """Cog for sending bot responses to Discord."""

    def __init__(self, bot: commands.Bot, queue: mp.Queue):
        self.bot = bot
        self.queue = queue

    async def cog_load(self):
        self.my_task.start()

    async def cog_unload(self):
        self.my_task.stop()

    @tasks.loop(seconds=5)
    async def my_task(self):
        """Background task that processes AI responses from the queue."""
        if self.queue.empty():
            return
        bot_response = self.queue.get_nowait()
        users_message = None
        users_channel = None
        user = None
        if isinstance(bot_response, DiscordChatBotResponse):
            for msg in self.bot.cached_messages:
                if msg.id == bot_response.request.message.message_id:
                    users_message = msg
                    break
        elif isinstance(bot_response, DiscordBackgroundBotResponse):
            if bot_response.request.channel is not None:
                users_channel = bot_response.request.channel
            if bot_response.request.user is not None:
                user = bot_response.request.user

        if users_message is not None:
            # Discord has a max message length of 2000 characters, split if needed
            start = 0
            end = (
                2000
                if len(bot_response.content) > 2000
                else len(bot_response.content)
            )
            while start < len(bot_response.content):
                response_chunk = bot_response.content[start:end]
                if users_message is not None:
                    await users_message.reply(response_chunk)
                elif isinstance(users_channel, Messageable) and user is not None:
                    await users_channel.send(f"{user.mention} {response_chunk}")
                start = end
                end = start + 2000
