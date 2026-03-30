<p align="center">
  <img src="src/uPtt/ui/assets/logo_horizontal.svg" alt="uPtt Logo" width="450">
</p>

<p align="center">
  <strong>Bringing the warmth of PTT back to life on modern desktops</strong><br>
  A modern instant messaging client built for PTT (Taiwan's largest BBS).
</p>

<p align="center">
  <a href="https://github.com/uPtt-messenger/uPttTerm/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-GPL--3.0-green.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/Platform-Windows%20|%20macOS-lightgrey" alt="Platform">
</p>

<p align="center">
  English | <a href="README.md">繁體中文</a>
</p>

---

### Project Vision

[PTT (Ptt Bulletin Board System)](https://www.ptt.cc) is Taiwan's most vibrant online community, active for over 30 years. However, its traditional Telnet interface and internal mail system feel dated in the age of modern instant messaging.

**uPtt** bridges that gap. Using Python and a modern GUI framework (PySide6/Qt6), it transforms PTT's internal mail system into a seamless chat experience -- like Telegram or LINE -- without requiring any knowledge of Telnet keyboard commands.

---

## Features

### Instant Messaging
* **Mail-to-chat conversion:** Automatically transforms PTT internal mail into intuitive chat bubbles.
* **Quote reply:** Right-click any message to quote-reply, with a preview shown above the input box.
* **Smart polling:** Background polling delivers messages in real time while keeping system load minimal.
* **Multi-account support:** Database-level isolation lets you switch between multiple PTT accounts with separate chat histories.
* **Plain mail display:** Non-uPtt mail (system notices, regular mail from other users) appears as mail cards in chat history, expandable with one click.

### Contact Management
* **Pin conversations:** Right-click a contact to pin it to the top of the list.
* **Drag-and-drop reordering:** Rearrange contacts freely; pinned and unpinned sections sort independently.
* **Close / Delete / Block:** Three levels of contact management via the right-click menu.

### Background Notifications
* **System tray:** The app continues running in the background after closing the window.
* **Desktop notifications:** Receive real-time notification previews when new messages arrive.

### Keyboard Shortcuts
| Key | Action |
|-----|--------|
| `Ctrl+N` | Focus the new conversation input |
| `Ctrl+W` | Close the current conversation |
| `Ctrl+Q` | Quit the application |
| `Enter` | Send message |

### Modern UI/UX
* **Retina-ready:** All-vector SVG icon rendering, crisp on 4K and HiDPI displays.
* **Dark theme:** Inherits PTT's signature dark aesthetic with refined typography.
* **Instant local cache:** Chat history loads instantly from the local SQLite database.

### Security & Privacy
* **Local-only storage:** All chat history and account data is stored exclusively on your device -- nothing is uploaded to third-party servers.
* **Native protocol:** Connects directly to PTT's official servers.
* **Automated leak prevention:** CI pipelines integrate TruffleHog scanning and dynamic credential detection to ensure sensitive information never leaks in development, testing, or logs.

---

## Screenshot

### Modern Login Experience
<img width="520" alt="Login Screen" src="https://i.meee.com.tw/0RXU0Vt.png" />

---

## How It Works

To deliver a smooth messaging experience, uPtt uses the following mechanisms:

1. **Automatic mail cleanup:** After a message is parsed and saved to the local database, the corresponding PTT mail is **automatically deleted** to keep your inbox clean.
2. **Plain mail preserved:** Non-uPtt mail (system announcements, regular mail) is **never deleted**, but still displayed as mail cards in the relevant chat history.
3. **Safety note:** The app only auto-deletes mail that matches the uPtt message format. If you have concerns, enable "External mailbox backup" in your PTT settings.

---

## Getting Started

### Download
Head to [GitHub Releases](https://github.com/uPtt-messenger/uPtt-app/releases) to download the latest version:

* **Windows:** Download the `.exe` file and run it.
* **macOS:** Download the `.dmg` file and drag `uPtt` to your Applications folder.

---

## Development

Built with **Python 3.12** and **PySide6**. To set up a development environment:

1. **Clone:** `git clone git@github.com:uPtt-messenger/uPtt-app.git`
2. **Install dependencies:** `pip install -r requirements.txt`
3. **Run:** `python3 src/run_app.py`
4. **Test:** `pytest --cov=src/uPtt tests/`

---

## License & Acknowledgements

* Licensed under **GPL-3.0**.
* Powered by [PyPtt](https://github.com/PyPtt/PyPtt) for PTT server communication.

## Code signing policy

Release builds are signed by [SignPath.io](https://signpath.io) and verified by the [SignPath Foundation](https://signpath.org).

See [Code Signing Policy](CODE_SIGNING_POLICY.md) for details.
