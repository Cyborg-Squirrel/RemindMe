"""Configuration management for Taskuccino bot."""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

CONFIG_FILE = Path(__file__).parent.parent / "config.json"
SYSTEM_PROMPT_FILE = Path(__file__).parent.parent / "system.md"


@dataclass
class Model:
    """Represents an AI model with its capabilities."""

    name: str
    capabilities: List[str] = field(default_factory=list)


@dataclass
class ModelsConfig:
    """Configuration for primary and backup AI models."""

    primary_model: Model
    backup_models: List[Model] = field(default_factory=list)


@dataclass
class BotConfig:
    """Configuration for the Taskuccino bot."""

    token: str
    api_url: str
    models: Optional[ModelsConfig]
    reaction_emoji: str
    react_to_messages: bool
    workspace: Path


DEFAULT_CONFIG = BotConfig("", "http://localhost:11434", None, "👋", True, Path("./workspace"))


def load_system_prompt() -> str:
    """Load the system prompt from the system.md file."""
    if not SYSTEM_PROMPT_FILE.exists():
        print("The system prompt file was not found! Using default.")
        return """You are a Discord bot.
                  Text formatting is supported but you can only use bold, italics, 
                  underline, strikethrough, code blocks, and inline code.
                  Do not use any other markdown syntax as it will not render properly."""

    try:
        with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
            system_prompt = f.read()
            return system_prompt
    except OSError as e:
        print(f"Error loading system prompt: {e}. Using default.")
        return DEFAULT_CONFIG.__doc__ or ""


def _is_valid_path(path_str):
    p = Path(path_str)
    try:
        p.resolve(strict=False)
    except OSError:
        return False
    return True

def load_config() -> BotConfig:
    """Load configuration from config.json."""
    if not CONFIG_FILE.exists():
        print(
            "Config file does not exist, falling back to defaults. "
            "Please create a config.json file with your settings."
        )
        return DEFAULT_CONFIG

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config_data = json.load(f)

        models = _load_models(config_data.get("models", DEFAULT_CONFIG.models))
        workspace_string = config_data.get("workspace", "./workspace")
        workspace: Path
        if _is_valid_path(workspace_string):
            workspace = Path(workspace_string)
            if not workspace.exists():
                workspace.mkdir(parents=True, exist_ok=True)
        else:
            raise Exception(f'{workspace_string} is an invalid workspace directory!')

        config = BotConfig(
            token=config_data.get("token", DEFAULT_CONFIG.token),
            api_url=config_data.get("api_url", DEFAULT_CONFIG.api_url),
            models=models,
            reaction_emoji=config_data.get(
                "reaction_emoji", DEFAULT_CONFIG.reaction_emoji
            ),
            react_to_messages=config_data.get(
                "react_to_messages", DEFAULT_CONFIG.react_to_messages
            ),
            workspace=workspace
        )

        return config

    except json.JSONDecodeError as e:
        print(f"Error: config.json is not valid JSON. Using defaults. {e}")
        return DEFAULT_CONFIG
    except OSError as e:
        print(f"Error loading config: {e}. Using defaults.")
        return DEFAULT_CONFIG


def save_config(config: Dict[str, Any]) -> bool:
    """Save configuration to config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return True
    except OSError as e:
        print(f"Error saving config: {e}")
        return False


def _load_models(model_config: dict) -> Optional[ModelsConfig]:
    """Load models from config and return a ModelsConfig object.
    
    The first model with 'primary': true is set as the primary model.
    If no primary model is specified, the first model is used as primary.
    """
    if model_config is None:
        return None

    primary_model = None
    backup_models = []

    for model_data in model_config:
        model = Model(
            name=model_data.get("name"), capabilities=model_data.get("capabilities", [])
        )

        is_primary = model_data.get("primary", False)

        if is_primary and primary_model is None:
            primary_model = model
        else:
            backup_models.append(model)

    if primary_model is None:
        if backup_models:
            primary_model = backup_models.pop(0)
        else:
            raise ValueError("At least one model must be configured")

    return ModelsConfig(primary_model=primary_model, backup_models=backup_models)
