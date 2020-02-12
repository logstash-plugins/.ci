#!/bin/bash

# This is intended to be run inside the docker container as the command of the docker-compose.
set -ex
docker-compose -f .ci/docker-compose.yml run -e GEM_HOST_API_KEY logstash .ci/publish.sh
