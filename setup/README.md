# <!--name-->Setup Test Environment<!--/name-->

[![usages](https://img.shields.io/badge/usages-white?logo=githubactions&logoColor=blue)](https://github.com/search?q=logstash-plugins%2F.ci%2Fsetup+%28path%3A.github%2Fworkflows+OR+path%3A**%2Faction.yml+OR+path%3A**%2Faction.yaml%29&type=code)
[![test-setup](https://github.com/logstash-plugins/.ci/actions/workflows/test-setup.yml/badge.svg?branch=main)](https://github.com/logstash-plugins/.ci/workflows/test-setup.yml)

<!--description-->
Common setup steps for unit, integration and secure integration tests
<!--/description-->

## Inputs

<!--inputs-->
| Name                         | Description                                     | Required | Default |
|------------------------------|-------------------------------------------------|----------|---------|
| `elastic_stack_version`      | Elasticsearch stack version to test against     | `true`   | ` `     |
| `snapshot`                   | Whether to use snapshot version                 | `false`  | `false` |
| `docker_env`                 | Docker environment file (e.g., dockerjdk21.env) | `false`  | ` `     |
| `integration`                | Enable integration testing                      | `false`  | `false` |
| `secure_integration`         | Enable secure integration testing               | `false`  | `false` |
| `es_ssl_key_invalid`         | Use invalid SSL key for testing                 | `false`  | `false` |
| `es_ssl_supported_protocols` | SSL/TLS protocols to test                       | `false`  | ` `     |
<!--/inputs-->

## Outputs
<!--outputs-->
| Name   | Description                        |
|--------|------------------------------------|
| `skip` | Whether the test should be skipped |
<!--/outputs-->

## Usage

<!--usage action="logstash-plugins/.ci/**" version="env:VERSION"-->
```yaml
jobs:
  federation:
    permissions:
      contents: 'read'
    steps:
      - uses: actions/checkout@v6

      - uses: logstash-plugins/.ci/setup@v1
```
<!--/usage-->
