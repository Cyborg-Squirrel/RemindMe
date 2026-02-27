import multiprocessing as mp
import threading
from datetime import datetime
from time import sleep

from discord.abc import Snowflake

import taskuccino.ollama_tools as tools
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

            messages = [
                {"role": ChatRole.system.value, "content": self.system_prompt}
            ]
            if isinstance(ollama_request, DiscordChatBotRequest):
                try:
                    request_message = ollama_request.message

                    for history_message in ollama_request.history:
                        messages.append(
                            {
                                "role": history_message.role.value,
                                "content": history_message.content,
                            }
                        )

                    image_descriptions = self._process_images(request_message)
                    if image_descriptions:
                        messages.append(
                            {
                                "role": ChatRole.system.value,
                                "content": (
                                    f"The user attached an image with the following "
                                    "description: {image_descriptions}"
                                ),
                            }
                        )

                    messages.append(
                        {
                            "role": ChatRole.user.value,
                            "content": request_message.content,
                        }
                    )
                    chat_response = self.ollama_client.chat(messages=messages)
                    message_content = chat_response.message.content
                    response_content = (
                        message_content if message_content is not None else ""
                    )
                    ollama_response = DiscordChatBotResponse(
                        content=response_content, request=ollama_request
                    )
                    self.response_queue.put(ollama_response)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    error_response = DiscordChatBotResponse(
                        str(e), ollama_request
                    )
                    self.response_queue.put(error_response)
            elif isinstance(ollama_request, DiscordBackgroundBotRequest):
                try:
                    user = ollama_request.user
                    channel = ollama_request.channel
                    channel_id = channel.id if channel is Snowflake else None
                    tools = [
                        OllamaTool(
                            "ping_user",
                            "Sends a notification to the user",
                            lambda message: self.response_queue.put(message),
                        ),
                        OllamaTool(
                            "add_reminder",
                            "Adds a reminder to storage",
                            lambda reminder, due_date: self.reminder_repository.add_reminder(
                                ChatProvider.discord,
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

                    chat_response = self.ollama_client.chat_with_tools(
                        messages=messages, tools=tools
                    )
                    message_content = chat_response.message.content
                    response_content = (
                        message_content if message_content is not None else ""
                    )
                    ollama_response = DiscordBackgroundBotResponse(
                        content=response_content, request=ollama_request
                    )
                    self.response_queue.put(ollama_response)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    print(f"Got error while doing background task {e}")
