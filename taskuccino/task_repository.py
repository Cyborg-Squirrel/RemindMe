"""task repository for managing tasks with JSON persistence."""

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from taskuccino._types import ChatProvider


@dataclass
class task:
    """Represents a task with its metadata."""

    id: str
    chat_provider: ChatProvider
    user_id: str
    channel_id: Optional[str]
    content: str
    created_at: str
    due_date: Optional[str] = None
    completed_at: Optional[str] = None
    last_reminded_at: Optional[str] = None


class TaskRepository:
    """Repository for managing tasks with JSON file persistence."""

    def __init__(self, file_path: Optional[Path] = None):
        """
        Initialize the task repository.

        Args:
            file_path: Path to the JSON file for storing tasks.
                      Defaults to taskuccino/tasks.json
        """
        if file_path is None:
            file_path = Path(__file__).parent / "tasks.json"
        self.file_path = file_path
        self.tasks: List[task] = []

    def load(self) -> None:
        """Load tasks from the JSON file."""
        if not self.file_path.exists():
            self.tasks = []
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.tasks = [task(**item) for item in data]
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error loading tasks from file: {e}")
            self.tasks = []

    def save_to_file(self) -> None:
        """Save tasks to the JSON file."""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump([asdict(r) for r in self.tasks], f, indent=2)
        except (IOError, TypeError) as e:
            print(f"Error saving tasks to file: {e}")

    def add_task(
        self,
        chat_provider: ChatProvider,
        user_id: str,
        channel_id: Optional[str],
        content: str,
        due_date: str,
    ) -> task:
        """
        Add a new task.

        Args:
            chat_provider: The chat provider (e.g., "discord", "ollama")
            user_id: User ID who created the task
            channel_id: Channel ID where the task was created
            task: The task text
            due_date: Due date string

        Returns:
            The created task object
        """
        id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        new_task = task(
            id=id,
            chat_provider=chat_provider,
            user_id=user_id,
            channel_id=channel_id,
            content=content,
            created_at=created_at,
            due_date=due_date,
        )
        self.tasks.append(new_task)
        self.save_to_file()
        return new_task

    def get_task(self, task_id: str) -> Optional[task]:
        """
        Get a task by its ID.

        Args:
            task_id: The ID of the task to retrieve

        Returns:
            The task object if found, None otherwise
        """
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def get_tasks_by_user(self, user_id: str) -> List[task]:
        """
        Get all tasks for a specific user.

        Args:
            user_id: The user ID to filter by

        Returns:
            List of task objects for the user
        """
        return [r for r in self.tasks if r.user_id == user_id]

    def update_task(
        self,
        task_id: str,
        **kwargs: Any,
    ) -> Optional[task]:
        """
        Update an existing task.

        Args:
            task_id: The ID of the task to update
            **kwargs: Fields to update (e.g., task="New task text")

        Returns:
            The updated task object if found, None otherwise
        """
        task = self.get_task(task_id)
        if task is None:
            return None

        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)

        self.save_to_file()
        return task

    def delete_task(self, task_id: str) -> bool:
        """
        Delete a task by its ID.

        Args:
            task_id: The ID of the task to delete

        Returns:
            True if the task was deleted, False if not found
        """
        for i, task in enumerate(self.tasks):
            if task.id == task_id:
                self.tasks.pop(i)
                self.save_to_file()
                return True
        return False

    def clear_all(self) -> None:
        """Clear all tasks."""
        self.tasks = []
        self.save_to_file()
