# CI

Shared helpers to dry out common CI scripts used by plugins.

LogStash plugins by convention store configuration under `ci/` folder,
`.ci` is meant to be an optional replacement for most `ci/*` files.

There's also assumptions about using `rspec` to write tests currently.

## Setup

Set up your plugin's .travis.yml:

```
import:
- logstash-plugins/.ci:travis/defaults.yml@v0.1.0
- logstash-plugins/.ci:travis/matrix.yml@v0.1.0
- logstash-plugins/.ci:travis/exec.yml@v0.1.0
```

### Custom behaviour

If the plugin follows conventions and (unit) tests all run using `rspec`, simply
place your own shell scripts in the .ci folder
