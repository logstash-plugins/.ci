#!/bin/bash

# This is intended to be run inside the docker container as the command of the docker-compose.
set -ex

CURRENT_DIR=$(dirname "${BASH_SOURCE[0]}")

cd .ci

export BUILDKIT_PROGRESS=plain
# docker will look for: "./docker-compose.yml" (and "./docker-compose.override.yml")
docker-compose up --exit-code-from logstash
