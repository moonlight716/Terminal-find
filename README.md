# Terminal-find

`Terminal-find` gives you a `Ctrl+F`-style search experience for terminal sessions.
The command is `tfind`.

It is built around a practical constraint:

- A normal CLI tool cannot universally read and control another terminal emulator's private scrollback buffer.
- To make search reliable on Windows 11 and Ubuntu, `tfind` searches a live transcript/log of the current shell session instead.

That means once capture is enabled, `tfind "windowsContent"` can:

- jump to the first match immediately
- highlight the current match or all matches
- show match counts
- toggle case sensitivity, accent matching, and whole-word matching with keys `1` to `4`
- keep refreshing while the transcript grows

On Windows, if transcript capture is not enabled yet, `tfind` also has a fallback:

- it can snapshot the current console buffer and search that immediately
- when launched from the PowerShell integration function, it also merges the current session command history
- this is useful for the terminal text you can already see right now
- live refresh still needs transcript capture

## Quick Start

### Windows PowerShell

1. Add `D:\Terminal-find\bin` to your `PATH`, or call the wrapper directly:
   `D:\Terminal-find\bin\tfind.cmd`
2. Source the integration script from your PowerShell profile:

```powershell
. "D:\Terminal-find\integrations\powershell\tfind-profile.ps1"
```

3. Open a new terminal tab, run a few commands, then search:

```powershell
tfind "windowsContent"
```

### Ubuntu Bash

1. Add the repo `bin/` directory to `PATH`.
2. Source the Bash integration from `~/.bashrc`:

```bash
source /path/to/Terminal-find/integrations/bash/tfind.bash
```

3. Open a new shell and search:

```bash
tfind "windowsContent"
```

## Keys Inside `tfind`

- `1`: toggle highlight all
- `2`: toggle case sensitive
- `3`: toggle match accents
- `4`: toggle whole word
- `n`, `j`, `Enter`, `Down`: next match
- `p`, `k`, `Shift-Tab`, `Up`: previous match
- `Home`, `End`: first or last match
- `PageUp`, `PageDown`: scroll
- `r`: reload now
- `q`, `Esc`, `Ctrl+C`: quit

## Commands

```text
tfind "query"
tfind "query" --file path/to/log.txt
tfind "query" --plain
tfind doctor
tfind bootstrap powershell
tfind bootstrap bash
```

## Notes

- PowerShell capture uses `Start-Transcript`.
- Bash capture uses a `tee`-based live log plus a command pre-exec hook.
- Windows can fall back to a one-time console-buffer snapshot when no transcript exists.
- In PowerShell fallback mode, `tfind` can also include the current session's command history.
- Existing scrollback from a terminal session that was not already being captured cannot be recovered generically.
- ANSI color codes are stripped before searching so matches stay readable.
