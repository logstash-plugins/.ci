#!/usr/bin/env bash
set -eo pipefail

export SHARED_CI_DIR=.ci
export PLUGIN_DIR="$$(pwd)"
export TARGET_BRANCH="${GITHUB_PR_TARGET_BRANCH:-main}"

.ci/docker-setup.sh
exit_code=$?

case $exit_code in
  0)
    echo "Install succeeded."
    ;;
  2)
    echo "Failed to pull logstash-${ELASTIC_STACK_VERSION}. The image should exist. Aborting build."
    exit $exit_code
    ;;
  *)
    echo "Install failed with an unexpected code: $exit_code. Stopping build."
    exit $exit_code
    ;;
esac

.ci/docker-run.sh
