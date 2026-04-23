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

If `tfind` still resolves to another command, check:

```powershell
Get-Command tfind
```

In PowerShell, the correct integrated setup should resolve `tfind` as a `Function`.
If it resolves to another script such as an npm-installed `tfind.ps1`, keep the profile hook above
and reopen PowerShell so the function takes precedence.

### Ubuntu Bash

1. Choose the Python interpreter you want `tfind` to use permanently. For example:

```bash
which python
# or:
which python3
```

2. Install the Bash integration once. If you are using the repo checkout directly, run:

```bash
/path/to/Terminal-find/bin/tfind bootstrap bash --install --python "$(which python)"
source ~/.bashrc
```

If you prefer a specific interpreter, pass it explicitly instead:

```bash
/path/to/Terminal-find/bin/tfind bootstrap bash --install --python /usr/bin/python3.11
source ~/.bashrc
```

This writes `~/.config/tfind/config.sh` with `TFIND_PYTHON` and `TFIND_REPO_ROOT`,
and appends a small `source .../integrations/bash/tfind.bash` block to `~/.bashrc`.

3. Open a new shell and search:

```bash
tfind "windowsContent"
```

4. Verify the shell integration:

```bash
type -a tfind
tfind doctor
```

In Bash, the correct integrated setup should resolve `tfind` as a shell `function`.
`tfind doctor` should also show the Bash config path and the pinned `TFIND_PYTHON`.

Once installed, `tfind` keeps using the pinned Python interpreter even if you later run
`conda activate <other-env>`.

If you want to confirm which transcript file the current shell is writing to, run:

```bash
tfind --savepath
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
- mouse wheel: move between matches; if there are no matches, scroll the view
- mouse left drag: use the terminal's normal text selection/copy behavior
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
tfind bootstrap bash --install --python /absolute/path/to/python
```

## Custom Storage Path

You can move all `tfind` state files, including transcripts, snapshots, and `current-session.txt`,
by setting `TFIND_STATE_ROOT`.

### PowerShell

```powershell
$env:TFIND_STATE_ROOT = "D:\TerminalLogs\tfind"
. "D:\Terminal-find\integrations\powershell\tfind-profile.ps1"
```

If you want a custom path every time you open PowerShell, put the same two lines in `$PROFILE`.

### Bash

```bash
export TFIND_STATE_ROOT="$HOME/terminal-logs/tfind"
/path/to/Terminal-find/bin/tfind bootstrap bash --install --python "$(which python)"
source ~/.bashrc
```

If you only want to override the current session transcript file, set `TFIND_CURRENT_LOG`
before capture starts.

To change the pinned interpreter later, rerun:

```bash
/path/to/Terminal-find/bin/tfind bootstrap bash --install --python /new/absolute/path/to/python
source ~/.bashrc
```

## Notes

- PowerShell capture uses `Start-Transcript`.
- Bash capture uses a `tee`-based live log plus a `PROMPT_COMMAND` history hook.
- The Bash installer writes `~/.config/tfind/config.sh` and updates `~/.bashrc`.
- Bash prefers `TFIND_PYTHON`, then `~/.config/tfind/config.sh`, and only then falls back to the current `python3` or `python`.
- If you move the repo checkout after installing Bash integration, rerun `tfind bootstrap bash --install ...` so `TFIND_REPO_ROOT` is updated.
- Windows can fall back to a one-time console-buffer snapshot when no transcript exists.
- In PowerShell fallback mode, `tfind` can also include the current session's command history.
- Existing scrollback from a terminal session that was not already being captured cannot be recovered generically.
- ANSI color codes are stripped before searching so matches stay readable.
