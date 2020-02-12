#!/bin/bash

set -e

NEW_VERSION=$(cat new_version)
echo "Let's try to publish \"$NEW_VERSION\"."

jgem build *.gemspec

# since GEM_HOST_API_KEY is only supported in rubygems +3.0.5,
# let's write the token to the credentials file
mkdir -p ~/.gem
echo "---" > ~/.gem/credentials
echo ":rubygems_api_key: ${GEM_HOST_API_KEY}" >> ~/.gem/credentials
chmod 0600 ~/.gem/credentials

# push the ruby gem to rubygems.org
jgem push *.gem

# time to create and push a new tag
curl -H "Authorization: token ${GITHUB_TOKEN}" -X POST -d "{ \"ref\": \"refs/tags/$(cat GEMSPEC_VERSION)\", \"sha\": \"$(git rev-parse HEAD)\" }" --header "Content-Type:application/json" "https://api.github.com/repos/$(git config --get travis.slug)/git/refs"
