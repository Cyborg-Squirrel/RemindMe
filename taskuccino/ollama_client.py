"""Ollama client for communicating with Ollama AI models."""

from dataclasses import dataclass
from typing import Callable, Optional

from ollama import ChatResponse, Client, GenerateResponse

from taskuccino.config import ModelsConfig


@dataclass
class OllamaToolParameter:
    """
    Dataclass for Ollama tool parameters
    """

    def __init__(
        self, name: str, type: str, description: str, required: bool = False
    ):
        self.name = name
        self.type = type
        self.description = description
        self.isRequired = required

    def to_dict(self) -> dict:
        return {"type": self.type, "description": self.description}


@dataclass
class OllamaTool:
    """
    Dataclass for Ollama tools.

    This class represents a tool that can be used with Ollama models.

    Attributes:
        name (str): The name of the tool
        description (str): A description of what the tool does
        callback (Callable): The function to call when the tool is invoked
        parameters (list[OllamaToolParameter]): The parameters that the tool accepts
    """

    def __init__(
        self,
        name: str,
        description: str,
        callback: Callable,
        parameters: list[OllamaToolParameter] = [],
    ):
        """
        Initialize an OllamaTool.

        Args:
            name (str): The name of the tool
            description (str): A description of what the tool does
            callback (Callable): The function to call when the tool is invoked
            parameters (list[OllamaToolParameter]): The parameters that the tool accepts
        """
        self.name = name
        self.description = description
        self.callback = callback
        self.parameters = parameters

    def to_dict(self):
        """
        Convert the tool to a dictionary format for Ollama.

        Returns:
            dict: A dictionary representation of the tool in Ollama format
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        p.name: p.to_dict() for p in self.parameters
                    },
                    "required": [
                        p.name for p in self.parameters if p.isRequired
                    ],
                },
            },
        }


class OllamaClient:
    """
    Client for interacting with Ollama AI models.

    This class provides methods to communicate with Ollama AI models for chat and generation tasks.

    Attributes:
        api_url (str): The URL of the Ollama API
        models (Optional[ModelsConfig]): Configuration for available models
        client (Client): The underlying Ollama client instance
    """

    def __init__(self, api_url: str, models: Optional[ModelsConfig]):
        """
        Initialize the OllamaClient.

        Args:
            api_url (str): The URL of the Ollama API
            models (Optional[ModelsConfig]): Configuration for available models
        """
        self.api_url = api_url
        self.models = models
        self.client = Client(host=api_url)

    def _get_model_for_capability(self, capability: str = "tools") -> str:
        """Return the name of a model that has the specified capability."""
        if self.models is None:
            list_response = self.client.list()
            all_models = list_response.models  # pylint: disable=no-member
            for model in all_models:
                if model.model is not None:
                    model_info = self.client.show(model.model)
                    if model_info.capabilities is not None:
                        if capability in model_info.capabilities:
                            return model.model
        else:
            if (
                self.models.primary_model
                and capability in self.models.primary_model.capabilities
            ):
                return self.models.primary_model.name
            for model in self.models.backup_models:
                if capability in model.capabilities:
                    return model.name
        raise RuntimeError(f"No model found with capability: {capability}")

    def chat_with_tools(
        self, messages: list, tools: list[OllamaTool]
    ) -> ChatResponse:
        """
        Send a chat request to the Ollama model. Tools are required.
        """
        model = self._get_model_for_capability("tools")
        print(
            f'Using model {model} to fulfil chat request {messages[-1]["content"]}'
        )
        tool_definitions = [t.to_dict() for t in tools]
        print(f"tool_definitions {tool_definitions}")
        response = self.client.chat(
            model=model, messages=messages, tools=tool_definitions
        )

        do_followup_chat = True
        while do_followup_chat:
            # Reset to false
            do_followup_chat = False
            if response.message.tool_calls:
                for called_tool in response.message.tool_calls:
                    matching_tool = lambda tools: next(
                        (
                            t
                            for t in tools
                            if t.name == called_tool.function.name
                        ),
                        None,
                    )
                    if matching_tool is not None:
                        do_followup_chat = True
                        print(f"Tool callback {called_tool}")
                        output = matching_tool(**called_tool.function.arguments)
                        messages.append(
                            {
                                "role": "tool",
                                "content": str(output),
                                "tool_name": called_tool.function.name,
                            }
                        )

            if do_followup_chat:
                response = self.client.chat(model=model, messages=messages)
        return response

    def generate(
        self, prompt: str, images: Optional[list] = None
    ) -> GenerateResponse:
        """Generate a response using the Ollama model."""
        model = self._get_model_for_capability(
            images is not None and len(images) > 0 and "vision" or "tools"
        )
        print(f"Using model {model} to fulfil generate request {prompt}")
        return self.client.generate(model=model, prompt=prompt, images=images)
