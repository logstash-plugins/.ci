# CI

Shared helpers to dry out common CI scripts used by plugins.

LogStash plugins by convention store configuration under `ci/` folder,
`.ci` is meant to be an optional replacement for most `ci/*` files.

There's also assumptions about using `rspec` to write tests currently.

## Setup

```
git submodule add https://github.com/logstash-plugins/.ci.git
git add .ci .gitmodules && git commit -m "CI: setup .ci sub-module"
mkdir -p ci
```

Optional step is to also possibly remove all existing ci scripts:
```
rm -r ci/*
```
Obviously depends on how specific a plugin's tests are and isn't necessary.

### Unit Tests

If the plugin follows conventions and (unit) tests all run using `rspec`, simply
link the whole directory and setup a CI provider configuration file (.travis.yml):

```
rm -rf ci/unit

ln -r -s .ci/unit ci/unit

cp .ci/.travis.yml.example .travis.yml

git add ci/unit .travis.yml && git commit -m "CI: setup unit test from .ci"
```

### Performance (Functional) Tests

Here we assume to have functional spec examples marked with a *performance* tag.
We are going to re-use most of the setup from the unit test parts to run on CI:

```
mkdir -p ci/performance
rm -rf ci/performance/*

ln -r -s .ci/Dockerfile ci/performance/
ln -r -s .ci/docker-setup.sh ci/performance/
ln -r -s .ci/docker-run.sh ci/performance/

cp .ci/unit/docker.env ci/performance/
cp .ci/unit/docker-compose.yml ci/performance/
cp .ci/unit/run.sh ci/performance/
nano ci/performance/run.sh
# EDIT: change rspec to run tagged examples e.g. *rspec -fd --tag performance*
nano ci/performance/docker-compose.yml
# EDIT: change *dockerfile:* to point to *ci/performance/Dockerfile*
# EDIT: adjust *command: configuration to *ci/performance/run.sh*
# HINT: there might be other parts you might want to change e.g. env_file

nano .travis.yml
# EDIT: include a section for the performance target e.g.
# - name: Performance Test ELASTIC_STACK_VERSION=7.x
#   env: ELASTIC_STACK_VERSION=7.x
#   install: ci/performance/docker-setup.sh
#   script: ci/performance/docker-run.sh

git add ci/performance/* .travis.yml && git commit -m "CI: setup performance test using .ci"
```

Check-out an existing plugin e.g. https://github.com/logstash-plugins/logstash-filter-grok/
