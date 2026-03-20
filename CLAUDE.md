# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

uPtt is a Python 3.12 + PySide6 (Qt6) desktop application that transforms PTT's (Taiwan's BBS) internal mail system into a modern instant messenger. It connects directly to PTT servers via the PyPtt library, using PTT mail as the message transport layer.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run the app
python src/run_app.py
python src/run_app.py --debug   # Debug mode: enables logging, bypasses single-instance check

# Run tests (with coverage)
pytest

# Run a single test file or test
pytest tests/test_db.py
pytest tests/test_db.py::TestDatabaseManager::test_add_message

# Build (handled by CI, uses Nuitka)
# See .github/workflows/build.yml for platform-specific build steps
```

Pytest is configured in `pytest.ini` with `--cov=src/uPtt --cov-fail-under=5`. Tests require `QT_QPA_PLATFORM=offscreen` for headless environments (CI sets this automatically).

## Architecture

### Threading Model
- **Main thread:** Qt event loop (UI)
- **Worker thread (`worker.py`):** All PTT I/O (login, polling mail, sending messages, user info queries)
- **Communication:** Qt Signals/Slots bridge the two threads

### Signal Flow
```
UI → Signal (e.g. login_requested) → PTTWorker (background thread)
PTTWorker → Signal (e.g. login_result) → UI handler
```

### Key Modules
| Module | Role |
|--------|------|
| `app.py` | Entry point, window management, single-instance via QLocalServer |
| `worker.py` | Background thread: polling loop, send/receive, user queries |
| `ptt.py` | Thin wrapper around PyPtt library |
| `db.py` | SQLite database with multi-account isolation |
| `ui/screens.py` | LoginWindow and MainWindow (chat interface) |
| `ui/widgets.py` | ChatBubble, ContactItem custom widgets |
| `ui/styles.py` | QSS dark theme stylesheets |
| `config.py` | Constants (poll interval, max messages, service port) |
| `contant.py` | Message format templates, commands, URLs |
| `utils.py` | App data directory, version checking, message formatting |

### Message Flow
1. **Sending:** UI → worker formats with uPtt header/footer → PyPtt `mail()` API → saved to local DB
2. **Receiving:** Worker polls PTT mail every 5s → filters uPtt-format messages → extracts content → auto-deletes from PTT → saves to DB → emits signal to UI

### Database
SQLite at platform-specific app data directory (`~/.local/share/uPtt/`, `~/Library/Application Support/uPtt/`, `%APPDATA%\uPtt/`). Multi-account isolation via `account_id` foreign key on all tables.

## Development Rules (from GEMINI.md)

### Git Workflow
- **main**: stable production. **beta**: staging. **feature/\***: branch from beta, squash merge back. **hotfix/\***: branch from main, merge to both main and beta.
- Commit messages follow **Conventional Commits** (`feat:`, `fix:`, `test:`, `chore:`).
- Run `pytest` and ensure all tests pass before any commit or merge.
- On merge conflicts: stop and ask for human intervention.

### PTT ID Handling
- **Internal keys:** always lowercase (`.lower()`) for case-insensitive matching
- **Display:** preserve original case from PTT server
- **Self-chat is forbidden:** filter out sessions where target ID matches logged-in account
- **Re-add existing contact:** even if already in list, re-adding the same ID must still trigger a `user_info` query to refresh casing and nickname

### UI Standards
- Dynamic centering with `Qt.AlignVCenter` / `addStretch()`
- All SVG assets rendered via `render_svg` helper (respects `devicePixelRatioF()` for HiDPI)
- Dark terminal aesthetic with monospace fonts ("SF Mono", "Consolas", "Courier New")
- Accent color: `#A0C4B4` (sage green)
- Contact list items: nickname label must have `setFixedHeight` so the ID label doesn't shift when nickname is absent; use `setSpacing(2)` between ID and nickname

### App Lifecycle
- **Exit:** ensure PTTWorker thread is stopped and PyPtt is logged out before the app closes
- **Single instance:** second launch notifies the first instance to raise its window to front, then exits; `--debug` bypasses this check

### Security
- CI runs TruffleHog secret scanning on all branches
- Tests include password leak detection via canary pattern
- Never log or expose credentials
