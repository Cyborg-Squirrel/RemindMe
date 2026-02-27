"""AI response cog for Discord bot."""

import multiprocessing as mp

from discord.ext import commands, tasks

from taskuccino._types import DiscordBackgroundBotRequest


class BackgroundReminderCog(commands.Cog):
    """Cog for periodically waking up the bot to send reminders to the user."""

    def __init__(self, bot: commands.Bot, request_queue: mp.Queue):
        self.bot = bot
        self.request_queue = request_queue

    async def cog_load(self):
        self.my_task.start()

    async def cog_unload(self):
        self.my_task.stop()

    @tasks.loop(minutes=5)
    async def my_task(self):
        """Background task that processes AI responses from the queue."""
        # TODO load guild or user from configured reminder
        user = await self.bot.fetch_user(149341947474083840)
        channel = await self.bot.create_dm(user)
        await self.bot.fetch_channel(1)
        await channel.send(f"{user.mention} test ping")
        request = DiscordBackgroundBotRequest(None, user, [])
        self.request_queue.put(request)
