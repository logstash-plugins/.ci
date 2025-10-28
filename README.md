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


## Mac OS throubleshooting
In some circumstances on MacOS, Rosetta2 could kicks it and generate an error related to QEMU not able to run some x86 code, for example:
```
ci-logstash-1  | Failed (Expected: 10000 got: 0, execution output:
ci-logstash-1  |  qemu-x86_64: Could not open '/lib64/ld-linux-x86-64.so.2': No such file or directory
ci-logstash-1  | ). Sleeping for 2.0
```

In such cases set and export `DOCKER_DEFAULT_PLATFORM` environment variable:
```
export DOCKER_DEFAULT_PLATFORM=linux/amd64
```

and then rebuild the image:
```
.ci/docker-setup.sh && .ci/docker-run.sh
```

## add-scripts-to-current-plugin.sh

Bootstrap this repo's `.ci` assets into a Logstash plugin repository from your local checkout.

### Prerequisites

- `yq` must be installed (used to read `travis/exec.yml`). For macOS with Homebrew:
  ```
  brew install yq
  ```
- `curl` and `tar` available in your shell.

### Usage

1. Change directory to the root of your plugin (must contain a `logstash-*.gemspec`).
2. Run the script from this repo:
   ```
   /path/to/logstash-plugins/.ci/add-scripts-to-current-plugin.sh
   ```

### What it does

- 

If `yq` is not installed or `travis/exec.yml` cannot be found, the script will exit with an error message.
