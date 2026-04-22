#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cat <<EOF
Terminal-find is ready in this workspace.

1. Put this directory on PATH:
   ${REPO_ROOT}/bin

2. Source this file from ~/.bashrc:
   source ${REPO_ROOT}/integrations/bash/tfind.bash

3. Open a new shell and run:
   tfind "windowsContent"
EOF
