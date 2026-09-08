from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.todo_tracker import setup
from src.todo_tracker.extension import TodoTracker, TodoItem


class TestTodoTrackerExtension:
    def test_setup_and_registration(self, mock_api) -> None:
        setup(mock_api)
        assert "todo_tracker" in mock_api.registered_extensions
        ext = mock_api.registered_extensions["todo_tracker"]
        assert isinstance(ext, TodoTracker)

    def test_commands_registration(self, mock_api) -> None:
        ext = TodoTracker(mock_api)
        ext.install()
        assert "todo_tracker.scan_workspace" in mock_api.commands.commands
        assert "todo_tracker.scan_active_file" in mock_api.commands.commands
        assert "todo_tracker.next_todo" in mock_api.commands.commands
        assert "todo_tracker.prev_todo" in mock_api.commands.commands
        assert "todo_tracker.find_fixmes" in mock_api.commands.commands

    def test_scan_content_multi_language(self, mock_api) -> None:
        ext = TodoTracker(mock_api)
        content = """
        # Python comment
        def foo():
            # TODO: implement authentication logic
            x = 10  # FIXME(alice): check boundary condition
            /* HACK: ignore null check */
            // BUG: crash on empty list
            -- NOTE: database migration needed
            <!-- XXX: update markup template -->
        """
        items = ext.scan_content(content, file_path="sample.py")
        tags = [it.tag for it in items]
        assert "TODO" in tags
        assert "FIXME" in tags
        assert "HACK" in tags
        assert "BUG" in tags
        assert "NOTE" in tags
        assert "XXX" in tags

        todo_item = next(it for it in items if it.tag == "TODO")
        assert todo_item.message == "implement authentication logic"
        assert todo_item.line_number == 4

        fixme_item = next(it for it in items if it.tag == "FIXME")
        assert fixme_item.message == "check boundary condition"

    def test_filter_by_tag_and_grouping(self, mock_api) -> None:
        ext = TodoTracker(mock_api)
        ext.items = [
            TodoItem(file_path="a.py", line_number=5, tag="TODO", message="m1"),
            TodoItem(file_path="a.py", line_number=12, tag="FIXME", message="m2"),
            TodoItem(file_path="b.py", line_number=20, tag="TODO", message="m3"),
            TodoItem(file_path="b.py", line_number=30, tag="HACK", message="m4"),
        ]
        todos = ext.filter_by_tag("TODO")
        assert len(todos) == 2
        assert all(it.tag == "TODO" for it in todos)

        fixmes = ext.filter_by_tag("FIXME")
        assert len(fixmes) == 1
        assert fixmes[0].message == "m2"

        by_file = ext.group_by_file()
        assert len(by_file["a.py"]) == 2
        assert len(by_file["b.py"]) == 2

        by_tag = ext.group_by_tag()
        assert len(by_tag["TODO"]) == 2
        assert len(by_tag["FIXME"]) == 1
        assert len(by_tag["HACK"]) == 1

    def test_navigation_next_and_prev(self, mock_api, tmp_path) -> None:
        ext = TodoTracker(mock_api)
        f1 = str(tmp_path / "module1.py")
        f2 = str(tmp_path / "module2.py")

        ext.items = [
            TodoItem(file_path=f1, line_number=10, tag="TODO", message="Task 1"),
            TodoItem(file_path=f1, line_number=25, tag="FIXME", message="Task 2"),
            TodoItem(file_path=f2, line_number=5, tag="NOTE", message="Task 3"),
        ]

        # Next in same file
        next_it = ext.next_todo(f1, 10)
        assert next_it is not None
        assert next_it.line_number == 25
        assert next_it.file_path == f1

        # Next wrapping to f2
        next_f2 = ext.next_todo(f1, 30)
        assert next_f2 is not None
        assert next_f2.file_path == f2
        assert next_f2.line_number == 5

        # Prev in same file
        prev_it = ext.prev_todo(f1, 25)
        assert prev_it is not None
        assert prev_it.line_number == 10

        # Prev wrapping to f2
        prev_wrap = ext.prev_todo(f1, 5)
        assert prev_wrap is not None
        assert prev_wrap.file_path == f2

    def test_scan_workspace_with_ignore_dirs(self, mock_api, tmp_path) -> None:
        ext = TodoTracker(mock_api)

        # Create valid source file
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        src_file = src_dir / "app.py"
        src_file.write_text("# TODO: valid workspace task\nprint('hello')", encoding="utf-8")

        # Create ignored git directory file
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        git_file = git_dir / "hooks.txt"
        git_file.write_text("# TODO: should be ignored", encoding="utf-8")

        # Create ignored node_modules
        nm_dir = tmp_path / "node_modules"
        nm_dir.mkdir()
        nm_file = nm_dir / "lib.js"
        nm_file.write_text("// TODO: ignore in node_modules", encoding="utf-8")

        items = ext.scan_workspace(root_dir=tmp_path)
        assert len(items) == 1
        assert items[0].message == "valid workspace task"
        assert items[0].file_path == str(src_file.resolve())

    def test_statusbar_and_commands(self, mock_api) -> None:
        ext = TodoTracker(mock_api)
        ext.install()
        ext.items = [
            TodoItem(file_path="f.py", line_number=1, tag="TODO", message="m1"),
            TodoItem(file_path="f.py", line_number=2, tag="FIXME", message="m2"),
        ]
        ext.update_statusbar()
        assert ext.statusbar_button is not None
        assert ext.statusbar_button.text == "TODOs: 2"

        fixmes = ext.find_all_fixmes()
        assert len(fixmes) == 1
        assert fixmes[0].tag == "FIXME"

    def test_app_instance_compatibility(self, app_instance) -> None:
        setup(app_instance.api)
        assert True