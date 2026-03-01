import multiprocessing as mp
import threading
import traceback
from datetime import datetime
from time import localtime, sleep, tzname

from discord import Optional

from taskuccino._types import (ChatProvider, ChatRole,
                               DiscordBackgroundBotRequest,
                               DiscordBackgroundBotResponse,
                               DiscordChatBotRequest, DiscordChatBotResponse)
from taskuccino.ollama_client import (OllamaClient, OllamaTool,
                                      OllamaToolParameter)
from taskuccino.task_repository import TaskRepository


class OllamaProcessor:  # pylint: disable=too-few-public-methods
    """Background task processor for Ollama requests."""

    def __init__(
        self,
        request_queue: mp.Queue,
        response_queue: mp.Queue,
        system_prompt: str,
        ollama_client: OllamaClient,
        task_repository: TaskRepository,
    ):
        self.request_queue = request_queue
        self.response_queue = response_queue
        self.system_prompt = system_prompt
        self.ollama_client = ollama_client
        self.task_repository = task_repository

    def _system_prompt_message(self) -> list[dict]:
        return [
            {"role": ChatRole.system.value, "content": self.system_prompt},
            {
                "role": ChatRole.system.value,
                "content": f"The system timezone configuration is {self._get_timezone()}",
            },
        ]

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

    def _ping_user(self, task_id, message):
        self.response_queue.put(message)
        self.task_repository.update_task(task_id, updated_at=datetime.now())

    def _get_timezone(self) -> str:
        isdst = localtime().tm_isdst
        return tzname[isdst]

    def _create_tools(
        self,
        user_id: int,
        channel_id: Optional[int],
        chat_provider: ChatProvider,
    ):
        """Create the shared set of tools."""
        return [
            OllamaTool(
                "current_time",
                "Gets the current system time",
                lambda: datetime.now().isoformat(),
            ),
            OllamaTool(
                "new_task",
                "Creates a new task",
                lambda task, due_date: self.task_repository.add_task(
                    chat_provider,
                    str(user_id),
                    str(channel_id) if channel_id is not None else None,
                    task,
                    due_date,
                ),
                parameters=[
                    OllamaToolParameter(
                        "task",
                        "string",
                        "The task text",
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
                "get_tasks",
                "Retrieves all tasks for a user",
                lambda: self.task_repository.get_tasks_by_user(str(user_id)),
            ),
            OllamaTool(
                "update_task",
                "Updates a task",
                lambda id, task, due_date: self.task_repository.update_task(
                    id, task=task, due_date=due_date
                ),
                parameters=[
                    OllamaToolParameter("id", "string", "The task ID", True),
                    OllamaToolParameter("task", "string", "The task text"),
                    OllamaToolParameter(
                        "due_date",
                        "string",
                        "The due date in ISO 8601 format",
                    ),
                ],
            ),
            OllamaTool(
                "complete_task",
                "Marks a task as completed",
                lambda id: self.task_repository.update_task(
                    id, completed_at=datetime.now().isoformat()
                ),
                parameters=[
                    OllamaToolParameter("id", "string", "The task ID", True),
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
                print(f"Got error while processing request {e}")
                traceback.print_exc()
                if isinstance(ollama_request, DiscordChatBotRequest):
                    error_response = DiscordChatBotResponse(
                        str(e), ollama_request
                    )
                else:
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

        tools = self._create_tools(
            request.message.user_id,
            request.message.channel_id,
            ChatProvider.discord,
        )
        chat_response = self.ollama_client.chat_with_tools(
            messages=messages, tools=tools
        )
        return chat_response.message.content or ""

    def _handle_background_request(
        self, request: DiscordBackgroundBotRequest
    ) -> str:
        tools = self._create_tools(
            request.user_id, request.channel_id, ChatProvider.discord
        )
        tools.append(
            OllamaTool(
                "ping_user",
                "Sends a notification to the user",
                lambda id, message: self._ping_user(id, message),
                parameters=[
                    OllamaToolParameter("id", "string", "The task ID", True),
                    OllamaToolParameter(
                        "message",
                        "string",
                        "The message to send to the user",
                        True,
                    ),
                ],
            ),
        )
        messages = self._system_prompt_message()
        messages.append(
            {
                "role": ChatRole.system.value,
                "content": "Use the available tools to process the user's tasks. Make sure to only notify the user if it is necessary.",
            }
        )

        chat_response = self.ollama_client.chat_with_tools(
            messages=messages, tools=tools
        )
        return chat_response.message.content or ""
