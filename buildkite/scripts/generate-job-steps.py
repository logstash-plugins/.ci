#!/usr/bin/env python3
"""
Central Buildkite step generator for Logstash plugins.
Lives in logstash-plugins/.ci — fetched by each plugin at pipeline time.

Flow:
  1. Read base-pr-test-matrix.yml   (stream-based 8.x/9.x OR jobs format)
  2. Read logstash-versions.yml     (version alias -> concrete version, in .ci root)
  3. Read plugin-tests.yml          (plugin-specific explicit test groups)
  4. Determine branch -> stream     (main -> 9.x, 11.x -> 8.x)
  5. Build base groups (stream or jobs format)
  6. Append plugin-specific groups with explicit env entries
  7. Deduplicate and emit Buildkite pipeline YAML to stdout

Base matrix supports two formats:

  A) Stream-based (8.x / 9.x with unit/integration version lists):
     9.x:
       unit: [9.previous, 9.current, main]
       integration: [9.previous, 9.current, main]

  B) Jobs format (explicit env strings per step):
     jobs:
       - group: "Integration Tests"
         steps:
           - ELASTIC_STACK_VERSION=9.current
           - SNAPSHOT=true ELASTIC_STACK_VERSION=main

Plugin-tests.yml uses jobs format with env: prefix:
  jobs:
    - group: "Integration Tests"
      steps:
        - env: INTEGRATION=true ELASTIC_STACK_VERSION=8.current

Usage:
    SHARED_CI_DIR=/tmp/ci  PLUGIN_DIR=$(pwd) \\
        python3 /tmp/ci/buildkite/scripts/generate-job-steps.py
"""

import os
import sys
import yaml


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SHARED_CI_DIR = os.environ.get("SHARED_CI_DIR", os.path.join(os.path.dirname(__file__), "..", ".."))
PLUGIN_DIR = os.environ.get("PLUGIN_DIR", os.getcwd())
BK_DIR = os.path.join(SHARED_CI_DIR, "buildkite")


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_yaml(path):
    with open(path, "r") as fh:
        return yaml.safe_load(fh) or {}


def load_base_matrix():
    return load_yaml(os.path.join(BK_DIR, "base-pr-test-matrix.yml"))


def load_logstash_versions():
    return load_yaml(os.path.join(SHARED_CI_DIR, "logstash-versions.yml"))


def load_plugin_tests():
    path = os.path.join(PLUGIN_DIR, ".buildkite", "pull-request-pipeline", "plugin-tests.yml")
    if not os.path.exists(path):
        return {}
    return load_yaml(path)


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------

def version_available(logstash_versions, alias, snapshot):
    category = "snapshots" if snapshot else "releases"
    return logstash_versions.get(category, {}).get(str(alias)) is not None


def expand_versions(version_list, logstash_versions):
    """Expand version aliases into (alias, is_snapshot) pairs,
    skipping aliases without a concrete version in logstash-versions.yml."""
    results = []
    for alias in version_list:
        alias = str(alias)
        if version_available(logstash_versions, alias, snapshot=False):
            results.append((alias, False))
        if version_available(logstash_versions, alias, snapshot=True):
            results.append((alias, True))
    return results


def parse_env_string(env_str):
    """Parse 'KEY=VALUE KEY2=VALUE2 ...' into a dict."""
    env = {}
    for token in env_str.split():
        key, _, value = token.partition("=")
        if key:
            env[key] = value
    return env


# Env keys that determine test identity (ignore LOG_LEVEL etc. for deduplication)
DEDUP_ENV_KEYS = (
    "DOCKER_ENV", "ELASTIC_STACK_VERSION", "SNAPSHOT",
    "INTEGRATION", "SECURE_INTEGRATION",
    "ES_SSL_KEY_INVALID", "ES_SSL_SUPPORTED_PROTOCOLS",
)


def env_canonical_key(env):
    """Return a deterministic key for deduplication. Two steps with the same
    key run the same tests."""
    parts = []
    for k in DEDUP_ENV_KEYS:
        v = env.get(k)
        if v is not None:
            parts.append(f"{k}={v}")
    return "|".join(sorted(parts))


# ---------------------------------------------------------------------------
# Label / key helpers
# ---------------------------------------------------------------------------

STANDARD_ENV_KEYS = {"DOCKER_ENV", "ELASTIC_STACK_VERSION", "SNAPSHOT", "INTEGRATION", "LOG_LEVEL"}


def step_label(prefix, env):
    version = env["ELASTIC_STACK_VERSION"]
    is_snapshot = env.get("SNAPSHOT") == "true"
    parts = [prefix, version]
    if is_snapshot:
        parts.append("SNAPSHOT")
    extras = sorted(f"{k}={v}" for k, v in env.items() if k not in STANDARD_ENV_KEYS and v)
    if extras:
        parts.append(f"({', '.join(extras)})")
    return " - ".join(parts)


def step_key(prefix, env, index=None):
    parts = [prefix, env["ELASTIC_STACK_VERSION"].replace(".", "-")]
    if env.get("SNAPSHOT") == "true":
        parts.append("snapshot")
    if index is not None:
        parts.append(str(index))
    return "-".join(parts)


# ---------------------------------------------------------------------------
# Step builder
# ---------------------------------------------------------------------------

def make_step(label, key, env, timeout_in_minutes=60):
    return {
        "label": label,
        "key": key,
        "command": ".buildkite/run-tests.sh",
        "env": env,
        "timeout_in_minutes": timeout_in_minutes,
        "retry": {
            "automatic": {"limit": 1},
        },
    }


# ---------------------------------------------------------------------------
# Group builders
# ---------------------------------------------------------------------------

def build_base_group(group_name, emoji, key_prefix, version_list,
                     logstash_versions, default_env, type_env=None, timeout=60):
    """Build a Buildkite step group from a list of version aliases (base matrix)."""
    steps = []
    for alias, snapshot in expand_versions(version_list, logstash_versions):
        env = dict(default_env)
        if type_env:
            env.update(type_env)
        env["ELASTIC_STACK_VERSION"] = alias
        if snapshot:
            env["SNAPSHOT"] = "true"
        label = step_label(f"{emoji} {group_name}", env)
        key = step_key(key_prefix, env)
        steps.append(make_step(label, key, env, timeout))
    return {
        "group": f"{emoji} {group_name}",
        "key": key_prefix,
        "steps": steps,
    }


def _parse_step_env(entry):
    """Parse a step entry: string or dict with env key."""
    if isinstance(entry, str):
        return entry
    return entry.get("env", "")


def _group_type_env(group_name):
    """Implicit env vars for known base matrix group types."""
    name_lower = group_name.lower()
    if "integration" in name_lower and "secure" not in name_lower:
        return {"INTEGRATION": "true"}
    if "secure" in name_lower and "integration" in name_lower:
        return {"SECURE_INTEGRATION": "true", "INTEGRATION": "true"}
    return {}


def build_base_jobs_group(group_cfg, default_env, group_index):
    """Build a Buildkite step group from base matrix jobs format (explicit env strings)."""
    group_name = group_cfg["group"]
    key_prefix = f"base-{group_index}-{group_name.lower().replace(' ', '-')}"
    timeout = group_cfg.get("timeout_in_minutes", 60)
    type_env = _group_type_env(group_name)

    steps = []
    for i, entry in enumerate(group_cfg.get("steps", [])):
        env_str = _parse_step_env(entry)
        env = dict(default_env)
        env.update(type_env)
        env.update(parse_env_string(env_str))
        label = step_label(group_name, env)
        key = step_key(key_prefix, env, index=i)
        steps.append(make_step(label, key, env, timeout))
    return {
        "group": group_name,
        "key": key_prefix,
        "steps": steps,
    }


def build_plugin_group(group_cfg, default_env, group_index):
    """Build a Buildkite step group from an explicit plugin jobs entry."""
    group_name = group_cfg["group"]
    key_prefix = f"plugin-{group_index}-{group_name.lower().replace(' ', '-')}"
    timeout = group_cfg.get("timeout_in_minutes", 60)

    steps = []
    for i, entry in enumerate(group_cfg.get("steps", [])):
        env_str = _parse_step_env(entry)
        env = dict(default_env)
        env.update(parse_env_string(env_str))
        label = step_label(group_name, env)
        key = step_key(key_prefix, env, index=i)
        steps.append(make_step(label, key, env, timeout))
    return {
        "group": group_name,
        "key": key_prefix,
        "steps": steps,
    }


# ---------------------------------------------------------------------------
# Stream selection
# ---------------------------------------------------------------------------

def select_stream(target_branch):
    """Map a branch name to the test stream.

    main   -> 9.x
    11.x   -> 8.x
    8.*    -> 8.x   (legacy branch naming)
    """
    branch = target_branch.lower()
    if branch.startswith(("8.", "11.")):
        return "8.x"
    return "9.x"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

BASE_TYPE_CONFIG = {
    "unit": {"display_name": "Unit Tests", "emoji": ":rspec:", "env": {}, "timeout": 30},
    "integration": {"display_name": "Integration Tests", "emoji": ":elasticsearch:", "env": {"INTEGRATION": "true"}, "timeout": 60},
}


def main():
    base_matrix = load_base_matrix()
    logstash_versions = load_logstash_versions()
    plugin_tests = load_plugin_tests()

    target_branch = os.environ.get(
        "TARGET_BRANCH",
        os.environ.get("BUILDKITE_BRANCH", "main"),
    )

    # --- Base matrix test groups ---
    default_env = base_matrix.get("default_env", {})
    agent_cfg = base_matrix.get("agent", {})
    overrides = plugin_tests.get("overrides", {})

    groups = []

    if "jobs" in base_matrix:
        # Jobs format: explicit env strings per step
        for i, group_cfg in enumerate(base_matrix["jobs"]):
            groups.append(build_base_jobs_group(group_cfg, default_env, i))
    else:
        # Stream format: 8.x / 9.x with unit/integration version lists
        stream = select_stream(target_branch)
        base_stream_cfg = base_matrix.get(stream, {})
        for test_type, version_list in base_stream_cfg.items():
            if not version_list:
                continue
            if not overrides.get(test_type, True):
                continue
            cfg = BASE_TYPE_CONFIG.get(test_type, {
                "display_name": test_type.replace("_", " ").title(),
                "emoji": ":gear:", "env": {}, "timeout": 60,
            })
            groups.append(build_base_group(
                cfg["display_name"], cfg["emoji"],
                test_type.replace("_", "-"),
                version_list, logstash_versions, default_env,
                type_env=cfg["env"],
                timeout=cfg["timeout"],
            ))

    # --- Plugin-specific test groups (explicit env entries) ---
    for i, group_cfg in enumerate(plugin_tests.get("jobs", [])):
        groups.append(build_plugin_group(group_cfg, default_env, i))

    # --- Remove duplicate steps (same env = same test; first occurrence wins) ---
    seen = set()
    deduped = []
    for g in groups:
        kept = []
        for s in g["steps"]:
            ck = env_canonical_key(s["env"])
            if ck in seen:
                continue
            seen.add(ck)
            kept.append(s)
        if kept:
            deduped.append({**g, "steps": kept})

    pipeline = {
        "agents": agent_cfg,
        "steps": deduped,
    }
    yaml.dump(pipeline, sys.stdout, default_flow_style=False, sort_keys=False)


if __name__ == "__main__":
    main()
