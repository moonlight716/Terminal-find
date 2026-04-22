_tfind_repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
_tfind_source_root="${_tfind_repo_root}/src"
_tfind_state_root="${XDG_STATE_HOME:-$HOME/.local/state}/tfind"
_tfind_sessions_dir="${_tfind_state_root}/sessions"

_tfind_python_path() {
  if [[ ":${PYTHONPATH:-}:" != *":${_tfind_source_root}:"* ]] && [[ -n "${PYTHONPATH:-}" ]]; then
    export PYTHONPATH="${_tfind_source_root}:${PYTHONPATH}"
  elif [[ -z "${PYTHONPATH:-}" ]]; then
    export PYTHONPATH="${_tfind_source_root}"
  fi
}

tfind() {
  _tfind_python_path
  python -m tfind "$@"
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
  mkdir -p "$_tfind_sessions_dir"
  if [[ -z "${TFIND_SESSION_ID:-}" ]]; then
    export TFIND_SESSION_ID="$(date +%Y%m%d-%H%M%S)-$$"
  fi

  if [[ -z "${TFIND_CURRENT_LOG:-}" ]]; then
    export TFIND_CURRENT_LOG="${_tfind_sessions_dir}/bash-${TFIND_SESSION_ID}.log"
  fi

  printf '%s\n' "$TFIND_CURRENT_LOG" > "${_tfind_state_root}/current-session.txt"
  _tfind_python_path

  if [[ "${TFIND_CAPTURE_ENABLED:-0}" != "1" ]]; then
    export TFIND_CAPTURE_ENABLED=1
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
