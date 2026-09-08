from __future__ import annotations

import sys
import typing
from pathlib import Path
from unittest.mock import MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class MockCommands:
    def __init__(self):
        self._commands: dict[str, typing.Callable] = {}

    def register_command(self, name: str, callback: typing.Callable) -> None:
        self._commands[name] = callback

    @property
    def commands(self) -> dict[str, typing.Callable]:
        return self._commands.copy()


class MockStatusbarButton:
    def __init__(self, **kwargs):
        self.text = kwargs.get("text", "")
        self.icon = kwargs.get("icon", "")
        self.callback = kwargs.get("callback")
        self.description = kwargs.get("description", "")
        self.visible = False

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def change_text(self, text: str):
        self.text = text


class MockStatusbar:
    def __init__(self):
        self.buttons: list[MockStatusbarButton] = []

    def add_button(self, **kwargs):
        btn = MockStatusbarButton(**kwargs)
        self.buttons.append(btn)
        return btn


class MockExtensionsAPI:
    def __init__(self):
        self.base = MagicMock()
        self.logger = MagicMock()
        self.notifications = MagicMock()
        self.commands = MockCommands()
        self.statusbar = MockStatusbar()
        self.views = MagicMock()
        self.editors = MagicMock()
        self.registered_extensions: dict[str, typing.Any] = {}

    def register(self, name: str, extension: typing.Any) -> None:
        self.registered_extensions[name] = extension


@pytest.fixture
def mock_api():
    return MockExtensionsAPI()


@pytest.fixture(scope="session")
def app_instance():
    try:
        from biscuit import get_app_instance
        app = get_app_instance()
        yield app
    except Exception:
        mock = MagicMock()
        mock.api = MockExtensionsAPI()
        yield mock
