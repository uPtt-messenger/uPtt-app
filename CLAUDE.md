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
- **Worker thread (`PTTWorker`):** message I/O — login, polling mail, polling waterball, sending messages
- **Query thread (`QueryWorker`):** user-status queries — `get_user_info`, periodic online check, active-chat polling
- **Two PyPtt sessions:** main and query run on their own `UPttService` instances. Same PTT account, two concurrent logins.
  - Main session logs in with `kick_other_session=True`
  - Query session logs in ~10s after main success with `kick_other_session=False`; `kick_on_reconnect=False` so reconnect never kicks the main session
  - Rationale: `get_user_info` can block for seconds; splitting onto a second session stops queries from blocking sends
- **Reconnect throttle:** `UPttService._reconnect_lock` serializes reconnects across both sessions with a 5s minimum interval, preventing `LoginTooOften` when both drop at once
- **Communication:** Qt Signals/Slots bridge all three threads

### Signal Flow
```
UI → send_requested            → PTTWorker (main thread)
UI → user_info_requested       → QueryWorker (query thread)
UI → priority_online_requested → QueryWorker
UI → set_active_chat_requested → QueryWorker
UI → query_login_requested     → QueryWorker.do_login (triggered 10s after main login)

PTTWorker  → new_message_received / send_result / login_result / connection_lost → UI
QueryWorker → user_info_result / online_status_updated / session_archived        → UI
QueryWorker → query_session_degraded / query_session_restored                    → UI
```

### Failure Modes
- **Main session down:** `connection_lost` fires; message send/receive halts; reconnect runs on main thread
- **Query session down:** `query_session_degraded` fires; contact online dots render gray "unknown"; message send/receive unaffected; `query_session_restored` fires after next successful query
- **Both down:** both signals fire; reconnect throttle serializes recovery

### Key Modules
| Module | Role |
|--------|------|
| `app.py` | Entry point, creates both `UPttService` instances, window management, single-instance via QLocalServer |
| `worker.py` | `PTTWorker` (message I/O) + `QueryWorker` (user status) — two separate background QObjects |
| `ptt.py` | `UPttService` — thin wrapper around PyPtt with reconnect logic, shared reconnect throttle, `kick_on_reconnect` flag |
| `db.py` | SQLite database with multi-account isolation |
| `ui/screens.py` | LoginWindow and MainWindow (chat interface), owns both worker threads |
| `ui/widgets.py` | ChatBubble, WaterballBubble, MailCard, ContactItem (with `set_online_unknown` for degraded mode) |
| `ui/styles.py` | QSS dark theme stylesheets |
| `config.py` | Constants: poll intervals (mail 5s, waterball 5s, online 60s), max messages (256) |
| `contant.py` | Message format templates, commands, URLs (filename typo is legacy, do not rename) |
| `utils.py` | App data directory, version checking, message formatting |

### Message Types and Flow
Three message types with different handling:
- **`uptt`** — uPtt-format messages: parsed, saved to DB, then **auto-deleted from PTT**
- **`mail`** — Regular PTT station mail: displayed as mail cards, **never deleted** from PTT
- **`waterball`** — PTT waterball (instant pop-up) messages: captured and displayed inline

**Sending:** UI → worker wraps with uPtt header/footer + embedded timestamp → PyPtt `mail()` API → saved to local DB

**Receiving:** Worker polls PTT mail → filters by format → extracts content → processes per type → saves to DB → emits `new_message_received` signal to UI

### Polling Optimization
- **First poll after login:** scans up to 200 messages to recover offline history
- **Subsequent polls:** scans max 50 messages, stops early if hitting timestamp cutoff (`last_poll_time - 10s buffer`)
- uPtt messages are always fully processed regardless of age (must be deleted from PTT)
- Index tracking prevents rescanning: compares newest index and adjusts for deleted messages
- `last_poll_time` is persisted in SQLite settings table to survive restarts

### Timestamp Synchronization
uPtt embeds the sender's timestamp in message content as `[uPtt-ts:ISO-FORMAT]` after the division line. This embedded timestamp takes precedence over PTT's mail timestamp for message ordering, ensuring consistency across sender and receiver. Fallback chain: embedded timestamp → mail date → current time.

### Reply Format
Quoted replies are encoded as `[re:@SENDER_ID|TRUNCATED_PREVIEW]\nMESSAGE_TEXT`. Use `encode_reply()` / `decode_reply()` in `utils.py`.

### Connection Resilience
`ptt.py` handles reconnection on `PyPtt.ConnectionClosed`:
- Creates fresh PyPtt.Service instance on disconnect
- Max 5 retries: 3s delay between attempts, 60s for `LoginTooOften`
- `WrongIDorPassword` gives up immediately
- PTTWorker emits `connection_lost` / `connection_restored`; QueryWorker emits `query_session_degraded` / `query_session_restored`
- **Shared throttle:** `UPttService._reconnect_lock` serializes reconnects across both sessions with a 5s minimum interval (class attribute). Without this, A and B dropping simultaneously would race into `LoginTooOften`.
- **Kick semantics:** only main session escalates to `kick_other_session=True` on retry; query session's `kick_on_reconnect=False` ensures it can never evict the main session.

### Waterball Deduplication
Waterball polling generates a batch fingerprint (hash of all content in current poll). If identical to the previous batch, the entire batch is skipped — this handles cases where PTT's CLEAR API fails.

### Database
SQLite at platform-specific app data directory (`~/.local/share/uPtt/`, `~/Library/Application Support/uPtt/`, `%APPDATA%\uPtt/`). Multi-account isolation via `account_id` foreign key on all tables.

Key patterns:
- **Composite primary keys:** sessions use `(account_id, id)`, ensuring account isolation
- **Message deduplication:** UNIQUE constraint on `(account_id, session_id, sender_id, content, timestamp)`
- **Soft delete:** sessions use `is_visible` flag instead of hard delete
- **Pin ordering:** `is_pinned` + `pin_order` columns, pinned/unpinned sections sort independently
- **Config storage:** JSON-serialized values in settings table (dates as ISO strings)

## Testing

### Security Fixture
`conftest.py` has an **autouse** fixture that wraps `PyPtt.Service.call` and monitors for the canary password (`SECRET_CANARY_PW_12345`). Any non-login API call containing this canary raises `PasswordLeakError`. This ensures credentials never leak through PyPtt calls during tests.

### Key Fixtures (in test files)
- `ptt_service_mock` — `MagicMock(spec=UPttService)` with `ptt_id="TestUser"`
- `db_mock` — `MagicMock()` with `get_config` returning `None`
- `worker` — actual `PTTWorker` with mocked dependencies
- `db_manager` — real `DatabaseManager` using `tmp_path`

### Qt Testing Pattern
Uses `pytest-qt`'s `qtbot` for signal assertions:
```python
with qtbot.waitSignal(worker.login_result) as blocker:
    worker.do_login("user", "pass")
assert blocker.args == [True, "success"]
```

## CI Pipeline

Multi-stage workflow (`.github/workflows/build.yml`):
1. **Secret Scan** — TruffleHog with `--only-verified` on all branches/PRs
2. **Change Detection** — skips test/build for doc-only changes
3. **Testing** — `QT_QPA_PLATFORM=offscreen pytest` on Ubuntu with Qt6 system deps
4. **Security Analysis** — Bandit (static analysis) + pip-audit (dependency vulnerabilities)
5. **Build macOS** — Nuitka standalone app bundle, SVG→ICNS icon pipeline via librsvg
6. **Build Windows** — Nuitka onefile EXE, SVG→ICO via ImageMagick

Beta builds append `beta{COMMIT_SHA[0:4]}` to version and set prerelease flag.

## Development Rules

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
