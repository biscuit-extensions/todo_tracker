# Todo_tracker

Scan workspace for TODO, FIXME, and HACK annotations

## 🔧 Development

### Customizing the Extension

1. **Main Extension Logic**: Edit `src/todo_tracker/extension.py`
2. **Entry Point**: Modify `src/todo_tracker/__init__.py` if needed
3. **Tests**: Update `tests/test_todo_tracker.py` to match your changes

### Adding New Functionality

- **`src/todo_tracker/extension.py`**: Contains the main `greet()` function and extension logic
- **`tests/test_todo_tracker.py`**: Add tests for your new functionality

## Running the Development Server

To run the development server, use the following command:

```bash
biscuit ext dev
```

This will start the server and allow you to test your extension in a local environment.

### Testing

Make sure to install `pytest` before running the tests.

```bash
biscuit ext test
```

Modify tests to reflect the changes you made to the extension.

## Publishing & Updating

To publish or update your extension, use the following commands, and follow the instructions provided by the Biscuit CLI:

```bash
biscuit ext publish
biscuit ext update
```

### Project Structure

```
todo_tracker/
├── src/
│   └── todo_tracker/
│       ├── __init__.py          # Extension entry point
│       └── extension.py         # Main extension logic
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Pytest configuration
│   └── test_todo_tracker.py
├── pyproject.toml              # Project configuration
└── README.md                   # This file
```

---

**Author**: billyeatcookies  
**Version**: 0.1.0
