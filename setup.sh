#!/usr/bin/env bash
set -eo pipefail

export SHARED_CI_DIR=.ci
export PLUGIN_DIR="$$(pwd)"
export TARGET_BRANCH="${GITHUB_PR_TARGET_BRANCH:-main}"

docker-setup.sh
exit_code=$?

case $exit_code in
  0)
    echo "Install succeeded."
    ;;
  2)
    echo "Failed to pull logstash-${ELASTIC_STACK_VERSION}. The image should exist. Aborting build."
    exit $exit_code
    ;;
  99)
    echo "Failed to pull logstash-${ELASTIC_STACK_VERSION}. Likely due to missing DRA build."
    export SKIP_SCRIPT=true
    ;;
  *)
    echo "Install failed with an unexpected code: $exit_code. Stopping build."
    exit $exit_code
    ;;
esac

if [ "$SKIP_SCRIPT" = "true" ]; then
  exit 0
else
  docker-run.sh
fi
