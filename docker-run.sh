#!/bin/bash

# This is intended to be run inside the docker container as the command of the docker-compose.
set -ex

CURRENT_DIR=$(dirname "${BASH_SOURCE[0]}")

cd .ci

# docker will look for: "./docker-compose.yml" (and "./docker-compose.override.yml")
if [[ "$ELASTIC_STACK_RETRIEVED_VERSION" = "8.0.0"* ]]; then
  docker-compose --end-file docker_jdk_bundled.env up --exit-code-from logstash 
else
  docker-compose up --exit-code-from logstash
fi
