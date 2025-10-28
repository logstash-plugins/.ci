#!/bin/bash

set -e

# Ensure we are in the root of a Logstash plugin
if ls logstash-*.gemspec >/dev/null 2>&1; then
  echo "Detected Logstash plugin gemspec. Proceeding to add .ci scripts..."
else
  echo "Error: This does not appear to be the root of a Logstash plugin (missing logstash-*.gemspec)." >&2
  exit 1
fi

# Run .before_install[0] from travis/exec.yml using yq
if ! command -v yq >/dev/null 2>&1; then
  echo "Error: 'yq' is required but not installed. Please install yq (e.g., 'brew install yq') and retry." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXEC_YAML="$SCRIPT_DIR/travis/exec.yml"

if [ ! -f "$EXEC_YAML" ]; then
  echo "Error: Could not find $EXEC_YAML" >&2
  exit 1
fi

CMD=$(yq -r '.before_install[0]' "$EXEC_YAML")
if [ -z "$CMD" ] || [ "$CMD" = "null" ]; then
  echo "Error: No before_install[0] command found in $EXEC_YAML" >&2
  exit 1
fi

echo "Executing: $CMD"
bash -lc "$CMD"

echo "Successfully added .ci scripts to the plugin."

