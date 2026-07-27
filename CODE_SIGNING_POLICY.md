# Code signing policy

uPtt is signed using certificates issued by [SignPath.io](https://signpath.io), and verified by the [SignPath Foundation](https://signpath.org).

## Team and roles

| Role | GitHub | Name |
|------|--------|------|
| Author | [PttCodingMan](https://github.com/PttCodingMan) | CodingMan |
| Reviewer | [white1033](https://github.com/white1033) | Yen-Ying Lee |
| Approver | [yehshao0925](https://github.com/yehshao0925) | YShao |

### Role definitions

- **Author** -- Trusted team member who develops and maintains the source code.
- **Reviewer** -- Reviews all external contributions (pull requests from non-committers) before they are merged.
- **Approver** -- Approves code signing requests for each release build.

## Build verification

All release artifacts are built through automated CI/CD pipelines (GitHub Actions). SignPath verifies that each signed binary is a reproducible, automated build originating from the source code in this repository.

## Privacy policy

This program does not collect, transmit, or store any personal information to external servers. All user data (message history, contact list, account settings) is stored locally on the user's device in a SQLite database.

Network communication is limited to:
- Connecting to PTT (ptt.cc) servers for mail-based messaging, initiated by the user
- Checking for new releases via the GitHub API (https://api.github.com)

No telemetry, analytics, or tracking of any kind is included.

## License

uPtt is licensed under the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.html).
