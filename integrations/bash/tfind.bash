_tfind_repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
_tfind_source_root="${_tfind_repo_root}/src"
if [[ -n "${TFIND_STATE_ROOT:-}" ]]; then
  _tfind_state_root="${TFIND_STATE_ROOT}"
else
  _tfind_state_root="${XDG_STATE_HOME:-$HOME/.local/state}/tfind"
fi
_tfind_sessions_dir="${_tfind_state_root}/sessions"

_tfind_python_path() {
  if [[ ":${PYTHONPATH:-}:" != *":${_tfind_source_root}:"* ]] && [[ -n "${PYTHONPATH:-}" ]]; then
    export PYTHONPATH="${_tfind_source_root}:${PYTHONPATH}"
  elif [[ -z "${PYTHONPATH:-}" ]]; then
    export PYTHONPATH="${_tfind_source_root}"
  fi
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

tfind() {
  _tfind_ensure_session_identity
  _tfind_python_path
  if _tfind_is_text_mode "$@"; then
    python -m tfind "$@"
  else
    python -m tfind "$@" < /dev/tty > /dev/tty 2> /dev/tty
  fi
}

_tfind_record_command() {
  local command_text="${BASH_COMMAND:-}"
  if [[ -z "${TFIND_CURRENT_LOG:-}" || -z "$command_text" ]]; then
    return
  fi

  case "$command_text" in
    _tfind_record_command*|_tfind_python_path*|history*|printf\ \'\\n\$\ %s\\n\'*)
      return
      ;;
  esac

  if [[ "$command_text" != "${TFIND_LAST_COMMAND:-}" ]]; then
    printf '\n$ %s\n' "$command_text" >> "$TFIND_CURRENT_LOG"
    export TFIND_LAST_COMMAND="$command_text"
  fi
}

tfind_enable_capture() {
  _tfind_ensure_session_identity
  _tfind_python_path

  if [[ "${TFIND_CAPTURE_ENABLED:-0}" != "1" ]]; then
    export TFIND_CAPTURE_ENABLED=1
    export TFIND_CAPTURE_LOG="${TFIND_CURRENT_LOG}"
    exec 3>&1 4>&2
    exec > >(tee -a "$TFIND_CURRENT_LOG" >&3) 2> >(tee -a "$TFIND_CURRENT_LOG" >&4)
  fi

  if [[ -n "${BASH_VERSION:-}" ]]; then
    if [[ "${PS0:-}" != *'$(_tfind_record_command)'* ]] && [[ -n "${PS0:-}" ]]; then
      PS0='$(_tfind_record_command)'"${PS0}"
    elif [[ "${PS0:-}" != *'$(_tfind_record_command)'* ]]; then
      PS0='$(_tfind_record_command)'
    fi
  fi
}

tfind_enable_capture
