"""Taskuccino Discord bot library."""

from taskuccino._types import DiscordChatBotRequest, DiscordChatBotResponse
from taskuccino.config import (BotConfig, Model, ModelsConfig, load_config,
                               load_system_prompt)
from taskuccino.discord_response_cog import DiscordResponseCog
from taskuccino.ollama_client import OllamaClient
from taskuccino.ollama_processor import OllamaProcessor

__version__ = "0.1.0"
__all__ = [
    "BotConfig",
    "Model",
    "ModelsConfig",
    "load_config",
    "load_system_prompt",
    "OllamaClient",
    "DiscordResponseCog",
    "DiscordChatBotRequest",
    "DiscordChatBotResponse",
]
