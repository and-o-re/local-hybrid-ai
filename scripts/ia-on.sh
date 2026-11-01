#!/usr/bin/env bash
# Script portável de inicialização da IA Local Híbrida (`./scripts/ia-on.sh`)
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export HYBRID_AI_HOME="$(cd "$SCRIPT_DIR/.." && pwd)"
exec "$HOME/.local/bin/ia-on" "$@"
