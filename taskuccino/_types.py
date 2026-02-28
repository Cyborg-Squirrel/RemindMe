"""
Type definitions.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Union

from discord import Thread
from discord.abc import GuildChannel, PrivateChannel, Snowflake, User


class ChatProvider(str, Enum):
    discord = "discord"


class ModelCapabilities(str, Enum):
    """LLM capabilities"""

    tools = "tools"
    vision = "vision"


class ChatRole(str, Enum):
    """Role of a message author in a chat conversation."""

    user = "user"
    assistant = "assistant"
    system = "system"
    tool = "tool"


@dataclass
class ChatMessage:
    """Represents a chat message from the user or the bot."""

    role: ChatRole
    content: str
    timestamp: datetime


@dataclass
class DiscordMessage(ChatMessage):
    """Represents a Discord chat message"""

    user_id: int
    channel_id: int
    message_id: int
    image_attachments: list[bytes]


@dataclass
class DiscordChatBotRequest:
    """A request from a Discord chat."""

    message: DiscordMessage
    history: list[ChatMessage]


@dataclass
class DiscordBackgroundBotRequest:
    """A request from a background task."""

    channel_id: Optional[int]
    user_id: int
    history: list[ChatMessage]


@dataclass
class DiscordChatBotResponse:
    """Represents a response from the bot."""

    content: str
    request: DiscordChatBotRequest


@dataclass
class DiscordBackgroundBotResponse:
    """Represents a response from the bot."""

    content: str
    request: DiscordBackgroundBotRequest
