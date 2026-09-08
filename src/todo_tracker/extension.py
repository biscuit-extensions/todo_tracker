from __future__ import annotations

import os
import re
import typing
from dataclasses import dataclass
from pathlib import Path

from biscuit.extensions import Extension

if typing.TYPE_CHECKING:
    from biscuit.api import ExtensionsAPI


DEFAULT_TAGS = ["TODO", "FIXME", "HACK", "BUG", "NOTE", "XXX"]

DEFAULT_IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    ".deps",
    ".gemini",
    ".idea",
    ".vscode",
}

TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".htm", ".css", ".scss", ".sass",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".go", ".rs", ".java", ".kt", ".rb", ".php",
    ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd", ".md", ".txt", ".rst", ".json",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml", ".sql", ".lua", ".swift",
}


@dataclass
class TodoItem:
    file_path: str
    line_number: int
    tag: str
    message: str
    raw_line: str = ""

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "tag": self.tag,
            "message": self.message,
            "raw_line": self.raw_line,
        }


class TodoTracker(Extension):
    """Scan workspace for TODO, FIXME, HACK, BUG, and NOTE annotations with line navigation."""

    def __init__(self, api: ExtensionsAPI) -> None:
        super().__init__(api)
        self.api = api
        self.tags: list[str] = list(DEFAULT_TAGS)
        self.ignore_dirs: set[str] = set(DEFAULT_IGNORE_DIRS)
        self.items: list[TodoItem] = []
        self.statusbar_button = None
        self.sidebar_view = None
        self._regex = self._compile_regex(self.tags)
        if hasattr(self.api, "logger") and self.api.logger:
            self.api.logger.info("TODO Tracker extension initialised.")

    def _compile_regex(self, tags: list[str]) -> re.Pattern:
        tag_pattern = "|".join(re.escape(t) for t in tags)
        # Matches: comment symbols, optional author in parens/brackets, followed by separator and message
        pattern = (
            r"(?:#|//|--|;|%|\*|<!--)\s*"
            rf"(?P<tag>{tag_pattern})"
            r"(?:\([^)]*\)|\[[^\]]*\])?"
            r"[:\s\-]+(?P<message>.*?)(?:-->|\*/)?$"
        )
        return re.compile(pattern, re.IGNORECASE)

    def set_tags(self, tags: list[str]) -> None:
        """Configure list of recognized annotation tags."""
        self.tags = [t.strip().upper() for t in tags if t.strip()]
        self._regex = self._compile_regex(self.tags)

    def scan_content(self, content: str, file_path: str = "", tags: list[str] | None = None) -> list[TodoItem]:
        """Scan string content for todo annotations."""
        regex = self._compile_regex(tags) if tags else self._regex
        results: list[TodoItem] = []
        lines = content.splitlines()

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            match = regex.search(stripped)
            if match:
                matched_tag = match.group("tag").upper()
                msg = match.group("message").strip()
                results.append(
                    TodoItem(
                        file_path=file_path,
                        line_number=idx,
                        tag=matched_tag,
                        message=msg,
                        raw_line=line,
                    )
                )
        return results

    def scan_file(self, file_path: str | Path, tags: list[str] | None = None) -> list[TodoItem]:
        """Scan a single file on disk."""
        path_obj = Path(file_path).resolve()
        if not path_obj.is_file():
            return []

        # Check binary by extension or quick read
        if path_obj.suffix.lower() not in TEXT_EXTENSIONS and path_obj.suffix != "":
            return []

        try:
            with open(path_obj, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return self.scan_content(content, file_path=str(path_obj), tags=tags)
        except Exception as e:
            if hasattr(self.api, "logger") and self.api.logger:
                self.api.logger.warning(f"TODO Tracker failed reading {file_path}: {e}")
            return []

    def scan_workspace(
        self,
        root_dir: str | Path | None = None,
        tags: list[str] | None = None,
        ignore_dirs: set[str] | None = None,
    ) -> list[TodoItem]:
        """Recursively scan directory tree for all annotations."""
        if root_dir is None:
            root_dir = getattr(getattr(self.api, "base", None), "active_directory", None) or os.getcwd()
        root_path = Path(root_dir).resolve()
        ignored = self.ignore_dirs if ignore_dirs is None else ignore_dirs

        scanned: list[TodoItem] = []
        for current_root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in ignored and not d.startswith(".")]
            for filename in files:
                file_path = Path(current_root) / filename
                if file_path.suffix.lower() in TEXT_EXTENSIONS or filename in ("Dockerfile", "Makefile", "CMakeLists.txt"):
                    items = self.scan_file(file_path, tags=tags)
                    scanned.extend(items)

        self.items = scanned
        self.update_statusbar()
        if hasattr(self.api, "logger") and self.api.logger:
            self.api.logger.info(f"TODO Tracker found {len(scanned)} items across workspace.")
        return list(self.items)

    def filter_by_tag(self, tag: str) -> list[TodoItem]:
        """Return items matching a specific tag category."""
        target = tag.strip().upper()
        return [item for item in self.items if item.tag == target]

    def group_by_file(self) -> dict[str, list[TodoItem]]:
        """Return items grouped by file path."""
        grouped: dict[str, list[TodoItem]] = {}
        for item in self.items:
            grouped.setdefault(item.file_path, []).append(item)
        for path in grouped:
            grouped[path].sort(key=lambda x: x.line_number)
        return grouped

    def group_by_tag(self) -> dict[str, list[TodoItem]]:
        """Return items grouped by tag type."""
        grouped: dict[str, list[TodoItem]] = {}
        for item in self.items:
            grouped.setdefault(item.tag, []).append(item)
        for tag in grouped:
            grouped[tag].sort(key=lambda x: (x.file_path, x.line_number))
        return grouped

    def next_todo(self, current_file: str, current_line: int) -> TodoItem | None:
        """Find next todo item in active file or subsequent files with wrap-around."""
        if not self.items:
            return None

        norm_current = str(Path(current_file).resolve()) if current_file else ""
        file_groups = self.group_by_file()
        all_files = sorted(file_groups.keys())

        if norm_current in file_groups:
            # Check after current line in current file
            for item in file_groups[norm_current]:
                if item.line_number > current_line:
                    return item

            # Check next files in order
            cur_idx = all_files.index(norm_current)
            for i in range(1, len(all_files) + 1):
                next_f = all_files[(cur_idx + i) % len(all_files)]
                if file_groups[next_f]:
                    return file_groups[next_f][0]
        else:
            if all_files:
                return file_groups[all_files[0]][0]

        return None

    def prev_todo(self, current_file: str, current_line: int) -> TodoItem | None:
        """Find previous todo item in active file or preceding files with wrap-around."""
        if not self.items:
            return None

        norm_current = str(Path(current_file).resolve()) if current_file else ""
        file_groups = self.group_by_file()
        all_files = sorted(file_groups.keys())

        if norm_current in file_groups:
            # Check before current line in current file
            reversed_items = sorted(file_groups[norm_current], key=lambda x: x.line_number, reverse=True)
            for item in reversed_items:
                if item.line_number < current_line:
                    return item

            # Check previous files in reverse order
            cur_idx = all_files.index(norm_current)
            for i in range(1, len(all_files) + 1):
                prev_f = all_files[(cur_idx - i) % len(all_files)]
                if file_groups[prev_f]:
                    return file_groups[prev_f][-1]
        else:
            if all_files:
                return file_groups[all_files[-1]][-1]

        return None

    def update_statusbar(self) -> None:
        """Update total todo counter in statusbar button."""
        if not self.statusbar_button:
            return
        total = len(self.items)
        text = f"TODOs: {total}"
        if hasattr(self.statusbar_button, "change_text"):
            self.statusbar_button.change_text(text)
        elif hasattr(self.statusbar_button, "set_text"):
            self.statusbar_button.set_text(text)

    def jump_to_next(self) -> None:
        """Command handler: Jump to next TODO."""
        editor = getattr(getattr(self.api, "editors", None), "active_editor", None)
        path = getattr(editor, "path", "")
        cur_line = 1
        text_widget = getattr(editor, "text", None) or getattr(getattr(editor, "content", None), "text", None)
        if text_widget and hasattr(text_widget, "index"):
            try:
                cur_line = int(str(text_widget.index("insert")).split(".")[0])
            except Exception:
                cur_line = 1

        target = self.next_todo(str(path), cur_line)
        if target:
            if hasattr(self.api, "editors") and hasattr(self.api.editors, "open_editor"):
                self.api.editors.open_editor(target.file_path)
            if hasattr(self.api, "notifications") and self.api.notifications:
                self.api.notifications.info(f"[{target.tag}] line {target.line_number}: {target.message}")

    def jump_to_prev(self) -> None:
        """Command handler: Jump to previous TODO."""
        editor = getattr(getattr(self.api, "editors", None), "active_editor", None)
        path = getattr(editor, "path", "")
        cur_line = 1
        text_widget = getattr(editor, "text", None) or getattr(getattr(editor, "content", None), "text", None)
        if text_widget and hasattr(text_widget, "index"):
            try:
                cur_line = int(str(text_widget.index("insert")).split(".")[0])
            except Exception:
                cur_line = 1

        target = self.prev_todo(str(path), cur_line)
        if target:
            if hasattr(self.api, "editors") and hasattr(self.api.editors, "open_editor"):
                self.api.editors.open_editor(target.file_path)
            if hasattr(self.api, "notifications") and self.api.notifications:
                self.api.notifications.info(f"[{target.tag}] line {target.line_number}: {target.message}")

    def scan_active_file(self) -> list[TodoItem]:
        """Command handler: Scan only current active editor file."""
        editor = getattr(getattr(self.api, "editors", None), "active_editor", None)
        path = getattr(editor, "path", None)
        if not path:
            return []
        items = self.scan_file(path)
        # Update workspace list: remove old items for this file and add new ones
        norm = str(Path(path).resolve())
        self.items = [it for it in self.items if it.file_path != norm] + items
        self.update_statusbar()
        if hasattr(self.api, "notifications") and self.api.notifications:
            self.api.notifications.info(f"Found {len(items)} annotations in {Path(path).name}")
        return items

    def find_all_fixmes(self) -> list[TodoItem]:
        """Command handler: Find all FIXME annotations."""
        fixmes = self.filter_by_tag("FIXME")
        if hasattr(self.api, "notifications") and self.api.notifications:
            self.api.notifications.info(f"Found {len(fixmes)} FIXME annotations in workspace")
        return fixmes

    def install(self) -> None:
        """Register commands and UI components for Todo Tracker."""
        if hasattr(self.api, "commands") and hasattr(self.api.commands, "register_command"):
            self.api.commands.register_command("todo_tracker.scan_workspace", self.scan_workspace)
            self.api.commands.register_command("todo_tracker.scan_active_file", self.scan_active_file)
            self.api.commands.register_command("todo_tracker.next_todo", self.jump_to_next)
            self.api.commands.register_command("todo_tracker.prev_todo", self.jump_to_prev)
            self.api.commands.register_command("todo_tracker.find_fixmes", self.find_all_fixmes)

        if hasattr(self.api, "statusbar") and hasattr(self.api.statusbar, "add_button"):
            try:
                self.statusbar_button = self.api.statusbar.add_button(
                    text="TODOs: 0",
                    callback=self.scan_workspace,
                    description="TODO Tracker: Workspace annotations",
                )
                if hasattr(self.statusbar_button, "show"):
                    self.statusbar_button.show()
            except Exception:
                pass

        if hasattr(self.api, "logger") and self.api.logger:
            self.api.logger.info("TODO Tracker installed successfully.")
