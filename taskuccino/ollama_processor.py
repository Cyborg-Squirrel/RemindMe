import multiprocessing as mp
import threading
from datetime import datetime
from time import sleep
from typing import Callable

from discord.abc import Snowflake, User

from taskuccino._types import (ChatProvider, ChatRole,
                               DiscordBackgroundBotRequest,
                               DiscordBackgroundBotResponse,
                               DiscordChatBotRequest, DiscordChatBotResponse)
from taskuccino.ollama_client import (OllamaClient, OllamaTool,
                                      OllamaToolParameter)
from taskuccino.reminder_repository import ReminderRepository


class OllamaProcessor:  # pylint: disable=too-few-public-methods
    """Background task processor for Ollama requests."""

    def __init__(
        self,
        request_queue: mp.Queue,
        response_queue: mp.Queue,
        system_prompt: str,
        ollama_client: OllamaClient,
        reminder_repository: ReminderRepository,
    ):
        self.request_queue = request_queue
        self.response_queue = response_queue
        self.system_prompt = system_prompt
        self.ollama_client = ollama_client
        self.reminder_repository = reminder_repository

    def _system_prompt_message(self) -> list[dict]:
        return [{"role": ChatRole.system.value, "content": self.system_prompt}]

    def start(self) -> threading.Thread:
        t = threading.Thread(target=self._process_messages)
        t.start()
        return t

    def _process_images(self, request_message):
        """Process image attachments and return descriptions."""
        image_descriptions = ""
        attachment_number = 1
        image_attachments = request_message.image_attachments

        if image_attachments is None or len(image_attachments) == 0:
            return image_descriptions

        for attachment in image_attachments:
            image_description = self.ollama_client.generate(
                prompt="Describe this image", images=[attachment]
            )
            img_response = (
                image_description.response  # pylint: disable=no-member
            )
            image_descriptions += f"Image {attachment_number}: {img_response}\n"
            attachment_number += 1

        return image_descriptions

    def _create_tools(
        self,
        user: User,
        channel_id,
        chat_provider: ChatProvider,
    ):
        """Create the shared set of tools."""
        return [
            OllamaTool(
                "ping_user",
                "Sends a notification to the user",
                lambda message: self.response_queue.put(message),
            ),
            OllamaTool(
                "add_reminder",
                "Adds a reminder to storage",
                lambda reminder, due_date: self.reminder_repository.add_reminder(
                    chat_provider,
                    str(user.id),
                    channel_id,
                    reminder,
                    due_date,
                ),
                parameters=[
                    OllamaToolParameter(
                        "reminder",
                        "string",
                        "The reminder text",
                        True,
                    ),
                    OllamaToolParameter(
                        "due_date",
                        "string",
                        "The due date in ISO 8601 format",
                    ),
                ],
            ),
            OllamaTool(
                "get_reminders",
                "Retrieves all reminders for a user",
                lambda: self.reminder_repository.get_reminders_by_user(
                    str(user.id)
                ),
            ),
            OllamaTool(
                "modify_reminder",
                "Modifies an existing reminder",
                lambda id, reminder, due_date: self.reminder_repository.update_reminder(
                    id, reminder=reminder, due_date=due_date
                ),
                parameters=[
                    OllamaToolParameter(
                        "id", "string", "The reminder ID", True
                    ),
                    OllamaToolParameter(
                        "reminder", "string", "The reminder text"
                    ),
                    OllamaToolParameter(
                        "due_date",
                        "string",
                        "The due date in ISO 8601 format",
                    ),
                ],
            ),
            OllamaTool(
                "complete_reminder",
                "Marks a reminder as completed",
                lambda id: self.reminder_repository.update_reminder(
                    id, completed_at=datetime.now().isoformat()
                ),
                parameters=[
                    OllamaToolParameter(
                        "id", "string", "The reminder ID", True
                    ),
                ],
            ),
        ]

    def _process_messages(self):
        """
        Background task that processes requests from the request_queue using the
        Ollama client and puts responses in the response_queue.
        """
        while True:
            if self.request_queue.empty():
                sleep(5)
                continue

            ollama_request = self.request_queue.get_nowait()
            if ollama_request is None:
                sleep(5)
                continue

            try:
                if isinstance(ollama_request, DiscordChatBotRequest):
                    chat_response = self._handle_chat_request(ollama_request)
                    response = DiscordChatBotResponse(
                        content=chat_response, request=ollama_request
                    )
                elif isinstance(ollama_request, DiscordBackgroundBotRequest):
                    chat_response = self._handle_background_request(
                        ollama_request
                    )
                    response = DiscordBackgroundBotResponse(
                        content=chat_response, request=ollama_request
                    )
                else:
                    continue

                self.response_queue.put(response)
            except Exception as e:  # pylint: disable=broad-exception-caught
                if isinstance(ollama_request, DiscordChatBotRequest):
                    error_response = DiscordChatBotResponse(
                        str(e), ollama_request
                    )
                else:
                    print(f"Got error while doing background task {e}")
                    error_response = DiscordBackgroundBotResponse(
                        str(e), ollama_request
                    )
                self.response_queue.put(error_response)

    def _handle_chat_request(self, request: DiscordChatBotRequest) -> str:
        messages = self._system_prompt_message()
        for history_message in request.history:
            messages.append(
                {
                    "role": history_message.role.value,
                    "content": history_message.content,
                }
            )

        image_descriptions = self._process_images(request.message)
        if image_descriptions:
            messages.append(
                {
                    "role": ChatRole.system.value,
                    "content": f"The user attached an image with the following description: {image_descriptions}",
                }
            )

        messages.append(
            {
                "role": ChatRole.user.value,
                "content": request.message.content,
            }
        )

        
        tools = self._create_tools(request.message.user, request.message.channel_id, ChatProvider.discord)
        chat_response = self.ollama_client.chat_with_tools(messages=self._system_prompt_message(), tools=tools)
        return chat_response.message.content or ""

    def _handle_background_request(
        self, request: DiscordBackgroundBotRequest
    ) -> str:
        user = request.user
        channel = request.channel
        channel_id = channel.id if channel is Snowflake else None

        tools = self._create_tools(user, channel_id, ChatProvider.discord)

        chat_response = self.ollama_client.chat_with_tools(
            messages=self._system_prompt_message(), tools=tools
        )
        return chat_response.message.content or ""
