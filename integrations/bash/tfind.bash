_tfind_default_repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ -n "${XDG_CONFIG_HOME:-}" ]]; then
  _tfind_config_file_default="${XDG_CONFIG_HOME}/tfind/config.sh"
else
  _tfind_config_file_default="${HOME}/.config/tfind/config.sh"
fi

_tfind_env_python_set="${TFIND_PYTHON+1}"
_tfind_env_python="${TFIND_PYTHON-}"
_tfind_env_repo_root_set="${TFIND_REPO_ROOT+1}"
_tfind_env_repo_root="${TFIND_REPO_ROOT-}"

if [[ -r "${TFIND_CONFIG_FILE:-${_tfind_config_file_default}}" ]]; then
  # shellcheck disable=SC1090
  source "${TFIND_CONFIG_FILE:-${_tfind_config_file_default}}"
fi

if [[ -n "${_tfind_env_python_set:-}" ]]; then
  export TFIND_PYTHON="${_tfind_env_python}"
fi

if [[ -n "${_tfind_env_repo_root_set:-}" ]]; then
  export TFIND_REPO_ROOT="${_tfind_env_repo_root}"
fi

_tfind_repo_root="${TFIND_REPO_ROOT:-${_tfind_default_repo_root}}"
_tfind_source_root="${_tfind_repo_root}/src"
if [[ -n "${TFIND_STATE_ROOT:-}" ]]; then
  _tfind_state_root="${TFIND_STATE_ROOT}"
else
  _tfind_state_root="${XDG_STATE_HOME:-$HOME/.local/state}/tfind"
fi
_tfind_sessions_dir="${_tfind_state_root}/sessions"
_tfind_interactive_begin_marker="__TFIND_INTERACTIVE_BEGIN__"
_tfind_interactive_end_marker="__TFIND_INTERACTIVE_END__"

_tfind_python_path() {
  if [[ ":${PYTHONPATH:-}:" != *":${_tfind_source_root}:"* ]] && [[ -n "${PYTHONPATH:-}" ]]; then
    export PYTHONPATH="${_tfind_source_root}:${PYTHONPATH}"
  elif [[ -z "${PYTHONPATH:-}" ]]; then
    export PYTHONPATH="${_tfind_source_root}"
  fi
}

_tfind_script_capture_available() {
  command -v script >/dev/null 2>&1
}

_tfind_shell_is_interactive() {
  [[ $- == *i* ]]
}

_tfind_has_real_terminal_outputs() {
  [[ -n "${TFIND_REAL_STDOUT_FD:-}" ]] || return 1
  [[ -n "${TFIND_REAL_STDERR_FD:-}" ]] || return 1
  [[ "${TFIND_REAL_STDOUT_FD}" =~ ^[0-9]+$ ]] || return 1
  [[ "${TFIND_REAL_STDERR_FD}" =~ ^[0-9]+$ ]] || return 1
  [[ -t "${TFIND_REAL_STDOUT_FD}" ]] || return 1
  [[ -t "${TFIND_REAL_STDERR_FD}" ]] || return 1
}

_tfind_spawn_script_capture() {
  if [[ "${TFIND_SCRIPT_SPAWNED:-0}" == "1" ]]; then
    return 0
  fi

  local shell_path="${BASH:-}"
  if [[ -z "$shell_path" ]]; then
    shell_path="$(command -v bash 2>/dev/null || true)"
  fi

  if [[ -z "$shell_path" || ! -x "$shell_path" ]]; then
    printf '%s\n' "Unable to locate an interactive bash executable for tfind capture." >&2
    return 1
  fi

  local script_command
  printf -v script_command 'exec %q -i' "$shell_path"

  if ! _tfind_has_real_terminal_outputs; then
    exec {TFIND_REAL_STDOUT_FD}>&1
    exec {TFIND_REAL_STDERR_FD}>&2
    export TFIND_REAL_STDOUT_FD TFIND_REAL_STDERR_FD
  fi

  export TFIND_CAPTURE_ENABLED=1
  export TFIND_CAPTURE_LOG="${TFIND_CURRENT_LOG}"
  export TFIND_CAPTURE_BACKEND="script"
  export TFIND_SCRIPT_SPAWNED=1

  exec script -qef -a --log-out "$TFIND_CURRENT_LOG" --command "$script_command"
}

_tfind_resolve_python() {
  if [[ -n "${TFIND_PYTHON:-}" ]]; then
    if [[ ! -x "${TFIND_PYTHON}" ]]; then
      printf 'Configured TFIND_PYTHON is not executable: %s\n' "${TFIND_PYTHON}" >&2
      return 1
    fi
    printf '%s\n' "${TFIND_PYTHON}"
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi

  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi

  printf '%s\n' "tfind is not configured. Run: python3.11 -m tfind bootstrap bash --install --python /absolute/path/to/python" >&2
  return 1
}

_tfind_is_text_mode() {
  if [[ "$#" -eq 0 ]]; then
    return 0
  fi

  local first_arg="$1"
  if [[ "$first_arg" == "doctor" || "$first_arg" == "bootstrap" ]]; then
    return 0
  fi

  local arg
  for arg in "$@"; do
    case "$arg" in
      -h|--help|--version|--plain|-s|--savepath)
        return 0
        ;;
    esac
  done

  return 1
}

_tfind_update_pointer() {
  mkdir -p "$_tfind_state_root"
  printf '%s\n' "$TFIND_CURRENT_LOG" > "${_tfind_state_root}/current-session.txt"
}

_tfind_ensure_session_identity() {
  mkdir -p "$_tfind_sessions_dir"

  if [[ "${TFIND_CAPTURE_ENABLED:-0}" == "1" && -n "${TFIND_CAPTURE_LOG:-}" ]]; then
    export TFIND_CURRENT_LOG="${TFIND_CAPTURE_LOG}"
    _tfind_update_pointer
    return
  fi

  local current_pid_suffix="-$$"
  if [[ -z "${TFIND_SESSION_ID:-}" || "${TFIND_SESSION_ID}" != *"${current_pid_suffix}" ]]; then
    export TFIND_SESSION_ID="$(date +%Y%m%d-%H%M%S)-$$"
  fi

  local expected_log="${_tfind_sessions_dir}/bash-${TFIND_SESSION_ID}.log"
  if [[ -z "${TFIND_CURRENT_LOG:-}" || "${TFIND_CURRENT_LOG}" != "${expected_log}" ]]; then
    export TFIND_CURRENT_LOG="${expected_log}"
  fi

  _tfind_update_pointer
}

_tfind_record_history() {
  if [[ -z "${TFIND_CURRENT_LOG:-}" ]]; then
    return
  fi

  local history_id="${HISTCMD:-}"
  if [[ -z "$history_id" || "$history_id" == "${TFIND_LAST_HISTORY_ID:-}" ]]; then
    return
  fi

  local command_text
  command_text="$(builtin fc -ln -0 -0)"
  command_text="${command_text%$'\n'}"
  command_text="${command_text#"${command_text%%[![:space:]]*}"}"
  export TFIND_LAST_HISTORY_ID="$history_id"

  if [[ -z "$command_text" ]]; then
    return
  fi

  case "$command_text" in
    _tfind_*|history*|builtin\ history*|builtin\ fc*)
      return
      ;;
  esac

  printf '\n$ %s\n' "$command_text" >> "$TFIND_CURRENT_LOG"
}

_tfind_remove_history_hook() {
  if [[ -z "${PROMPT_COMMAND:-}" ]]; then
    return
  fi

  local updated="${PROMPT_COMMAND//_tfind_record_history;/}"
  updated="${updated//;_tfind_record_history/}"
  updated="${updated//_tfind_record_history/}"
  updated="${updated#;}"
  updated="${updated%;}"
  PROMPT_COMMAND="${updated}"
}

tfind() {
  _tfind_ensure_session_identity
  _tfind_python_path
  local tfind_python
  if ! tfind_python="$(_tfind_resolve_python)"; then
    return 1
  fi
  if _tfind_is_text_mode "$@"; then
    "${tfind_python}" -m tfind "$@"
  else
    if [[ -n "${TFIND_CURRENT_LOG:-}" ]]; then
      printf '%s\n' "${_tfind_interactive_begin_marker}" >> "$TFIND_CURRENT_LOG"
    fi
    if _tfind_has_real_terminal_outputs; then
      "${tfind_python}" -m tfind "$@" < /dev/tty >&"${TFIND_REAL_STDOUT_FD}" 2>&"${TFIND_REAL_STDERR_FD}"
    else
      "${tfind_python}" -m tfind "$@" < /dev/tty > /dev/tty 2> /dev/tty
    fi
    local exit_code=$?
    if [[ -n "${TFIND_CURRENT_LOG:-}" ]]; then
      printf '%s\n' "${_tfind_interactive_end_marker}" >> "$TFIND_CURRENT_LOG"
    fi
    return $exit_code
  fi
}

tfind_enable_capture() {
  _tfind_ensure_session_identity
  _tfind_python_path

  if [[ "${TFIND_CAPTURE_ENABLED:-0}" != "1" ]]; then
    if _tfind_shell_is_interactive && _tfind_script_capture_available; then
      _tfind_spawn_script_capture
    else
      export TFIND_CAPTURE_ENABLED=1
      export TFIND_CAPTURE_LOG="${TFIND_CURRENT_LOG}"
    fi
  fi

  if [[ -n "${BASH_VERSION:-}" ]]; then
    if [[ "${TFIND_CAPTURE_BACKEND:-}" == "script" ]]; then
      _tfind_remove_history_hook
    elif [[ "${PROMPT_COMMAND:-}" != *"_tfind_record_history"* ]] && [[ -n "${PROMPT_COMMAND:-}" ]]; then
      PROMPT_COMMAND="_tfind_record_history;${PROMPT_COMMAND}"
    elif [[ "${PROMPT_COMMAND:-}" != *"_tfind_record_history"* ]]; then
      PROMPT_COMMAND="_tfind_record_history"
    fi
  fi
}

tfind_enable_capture
