#!/usr/bin/env python3
"""
Central Buildkite step generator for Logstash plugins.
Lives in logstash-plugins/.ci — fetched by each plugin at pipeline time.

Flow:
  1. Read base-pr-test-matrix.yml (shared unit + integration versions per stream)
  2. Read logstash-versions.yml   (version alias -> concrete version, already in .ci root)
  3. Read plugin-test-config.yml  (plugin overrides + extended stages)
  4. Determine branch -> stream   (main -> 9.x, 11.x -> 8.x)
  5. Expand versions into steps, skipping unavailable versions
  6. Emit Buildkite pipeline YAML to stdout

Usage:
    SHARED_CI_DIR=/tmp/ci  PLUGIN_DIR=$(pwd) \
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
    """Load logstash-versions.yml from the .ci repo root."""
    return load_yaml(os.path.join(SHARED_CI_DIR, "logstash-versions.yml"))


def load_plugin_config():
    path = os.path.join(PLUGIN_DIR, ".buildkite", "plugin-test-config.yml")
    if not os.path.exists(path):
        return {}
    return load_yaml(path)


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------

def version_available(logstash_versions, alias, snapshot):
    """Check whether a concrete version exists for this alias."""
    category = "snapshots" if snapshot else "releases"
    val = logstash_versions.get(category, {}).get(str(alias))
    return val is not None


def expand_versions(version_list, logstash_versions):
    """Expand a list of version aliases into (alias, snapshot) pairs,
    skipping aliases that have no concrete version in logstash-versions.yml."""
    pairs = []
    for alias in version_list:
        alias = str(alias)
        if version_available(logstash_versions, alias, snapshot=False):
            pairs.append((alias, False))
        if version_available(logstash_versions, alias, snapshot=True):
            pairs.append((alias, True))
    return pairs


# ---------------------------------------------------------------------------
# Label / key helpers
# ---------------------------------------------------------------------------

def step_label(prefix, env):
    version = env["ELASTIC_STACK_VERSION"]
    is_snapshot = env.get("SNAPSHOT") == "true"
    parts = [prefix, version]
    if is_snapshot:
        parts.append("SNAPSHOT")
    extras = []
    if env.get("ES_SSL_KEY_INVALID") == "true":
        extras.append("invalid key")
    if env.get("ES_SSL_SUPPORTED_PROTOCOLS"):
        extras.append(env["ES_SSL_SUPPORTED_PROTOCOLS"])
    if extras:
        parts.append(f"({', '.join(extras)})")
    return " - ".join(parts)


def step_key(prefix, env):
    parts = [prefix, env["ELASTIC_STACK_VERSION"].replace(".", "-")]
    if env.get("SNAPSHOT") == "true":
        parts.append("snapshot")
    if env.get("ES_SSL_KEY_INVALID") == "true":
        parts.append("invalid-key")
    if env.get("ES_SSL_SUPPORTED_PROTOCOLS"):
        parts.append(env["ES_SSL_SUPPORTED_PROTOCOLS"].lower().replace(".", ""))
    return "-".join(parts)


# ---------------------------------------------------------------------------
# Step builder
# ---------------------------------------------------------------------------

def make_step(label, key, env, timeout_in_minutes=60):
    return {
        "label": label,
        "key": key,
        "command": ".buildkite/scripts/run-tests.sh",
        "env": env,
        "timeout_in_minutes": timeout_in_minutes,
        "retry": {
            "automatic": {"limit": 2},
        },
    }


# ---------------------------------------------------------------------------
# Group builders
# ---------------------------------------------------------------------------

def build_base_group(group_name, emoji, key_prefix, version_list,
                     logstash_versions, default_env,
                     extra_env=None, timeout=60):
    """Build a step group from a list of version aliases."""
    steps = []
    for alias, snapshot in expand_versions(version_list, logstash_versions):
        env = dict(default_env)
        env["ELASTIC_STACK_VERSION"] = alias
        if snapshot:
            env["SNAPSHOT"] = "true"
        if extra_env:
            env.update(extra_env)
        label = step_label(f"{emoji} {group_name}", env)
        key = step_key(key_prefix, env)
        steps.append(make_step(label, key, env, timeout))
    return {
        "group": f"{emoji} {group_name}",
        "key": key_prefix,
        "steps": steps,
    }


def build_plugin_stage_group(stage_cfg):
    """Build a group from an explicit plugin-defined stage."""
    name = stage_cfg["name"]
    emoji = stage_cfg.get("emoji", ":gear:")
    group_key = stage_cfg.get("group_key", name.lower().replace(" ", "-"))
    timeout = stage_cfg.get("timeout_in_minutes", 60)

    steps = []
    for entry in stage_cfg.get("matrix", []):
        env = dict(entry)
        label = step_label(f"{emoji} {name}", env)
        key = step_key(group_key, env)
        steps.append(make_step(label, key, env, timeout))
    return {
        "group": f"{emoji} {name}",
        "key": group_key,
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

def main():
    base_matrix = load_base_matrix()
    logstash_versions = load_logstash_versions()
    plugin_config = load_plugin_config()

    target_branch = os.environ.get(
        "TARGET_BRANCH",
        os.environ.get("BUILDKITE_BRANCH", "main"),
    )

    stream = select_stream(target_branch)
    stream_cfg = base_matrix.get(stream, {})
    default_env = base_matrix.get("default_env", {})
    agent_cfg = base_matrix.get("agent", {})
    overrides = plugin_config.get("overrides", {}).get(stream, {})

    groups = []

    # --- Unit tests (from base matrix) ---
    if overrides.get("unit", True):
        unit_versions = stream_cfg.get("unit", [])
        if unit_versions:
            groups.append(build_base_group(
                "Unit Tests", ":rspec:", "unit-tests",
                unit_versions, logstash_versions, default_env,
                timeout=30,
            ))

    # --- Integration tests (from base matrix, unless plugin disables) ---
    if overrides.get("integration", True):
        integ_versions = stream_cfg.get("integration", [])
        if integ_versions:
            groups.append(build_base_group(
                "Integration Tests", ":elasticsearch:", "base-integration-tests",
                integ_versions, logstash_versions, default_env,
                extra_env={"INTEGRATION": "true"},
                timeout=60,
            ))

    # --- Plugin-specific extended stages ---
    for stage in plugin_config.get("stages", []):
        groups.append(build_plugin_stage_group(stage))

    pipeline = {
        "agents": agent_cfg,
        "steps": groups,
    }
    yaml.dump(pipeline, sys.stdout, default_flow_style=False, sort_keys=False)


if __name__ == "__main__":
    main()
