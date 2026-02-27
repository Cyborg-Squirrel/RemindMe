"""Reminder repository for managing reminders with JSON persistence."""

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from taskuccino._types import ChatProvider


@dataclass
class Reminder:
    """Represents a reminder with its metadata."""

    id: str
    chat_provider: ChatProvider
    user_id: str
    channel_id: Optional[str]
    content: str
    created_at: str
    due_date: Optional[str] = None
    completed_at: Optional[str] = None
    last_reminded_at: Optional[str] = None


class ReminderRepository:
    """Repository for managing reminders with JSON file persistence."""

    def __init__(self, file_path: Optional[Path] = None):
        """
        Initialize the reminder repository.

        Args:
            file_path: Path to the JSON file for storing reminders.
                      Defaults to taskuccino/reminders.json
        """
        if file_path is None:
            file_path = Path(__file__).parent / "reminders.json"
        self.file_path = file_path
        self.reminders: List[Reminder] = []

    def load(self) -> None:
        """Load reminders from the JSON file."""
        if not self.file_path.exists():
            self.reminders = []
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.reminders = [Reminder(**item) for item in data]
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error loading reminders from file: {e}")
            self.reminders = []

    def save_to_file(self) -> None:
        """Save reminders to the JSON file."""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump([asdict(r) for r in self.reminders], f, indent=2)
        except (IOError, TypeError) as e:
            print(f"Error saving reminders to file: {e}")

    def add_reminder(
        self,
        chat_provider: ChatProvider,
        user_id: str,
        channel_id: Optional[str],
        content: str,
        due_date: str,
    ) -> Reminder:
        """
        Add a new reminder.

        Args:
            chat_provider: The chat provider (e.g., "discord", "ollama")
            user_id: User ID who created the reminder
            channel_id: Channel ID where the reminder was created
            reminder: The reminder text
            due_date: Due date string

        Returns:
            The created Reminder object
        """
        id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        new_reminder = Reminder(
            id=id,
            chat_provider=chat_provider,
            user_id=user_id,
            channel_id=channel_id,
            content=content,
            created_at=created_at,
            due_date=due_date,
        )
        self.reminders.append(new_reminder)
        self.save_to_file()
        return new_reminder

    def get_reminder(self, reminder_id: str) -> Optional[Reminder]:
        """
        Get a reminder by its ID.

        Args:
            reminder_id: The ID of the reminder to retrieve

        Returns:
            The Reminder object if found, None otherwise
        """
        for reminder in self.reminders:
            if reminder.id == reminder_id:
                return reminder
        return None

    def get_reminders_by_user(self, user_id: str) -> List[Reminder]:
        """
        Get all reminders for a specific user.

        Args:
            user_id: The user ID to filter by

        Returns:
            List of Reminder objects for the user
        """
        return [r for r in self.reminders if r.user_id == user_id]

    def update_reminder(
        self,
        reminder_id: str,
        **kwargs: Any,
    ) -> Optional[Reminder]:
        """
        Update an existing reminder.

        Args:
            reminder_id: The ID of the reminder to update
            **kwargs: Fields to update (e.g., reminder="New reminder text")

        Returns:
            The updated Reminder object if found, None otherwise
        """
        reminder = self.get_reminder(reminder_id)
        if reminder is None:
            return None

        for key, value in kwargs.items():
            if hasattr(reminder, key):
                setattr(reminder, key, value)

        self.save_to_file()
        return reminder

    def delete_reminder(self, reminder_id: str) -> bool:
        """
        Delete a reminder by its ID.

        Args:
            reminder_id: The ID of the reminder to delete

        Returns:
            True if the reminder was deleted, False if not found
        """
        for i, reminder in enumerate(self.reminders):
            if reminder.id == reminder_id:
                self.reminders.pop(i)
                self.save_to_file()
                return True
        return False

    def clear_all(self) -> None:
        """Clear all reminders."""
        self.reminders = []
        self.save_to_file()
