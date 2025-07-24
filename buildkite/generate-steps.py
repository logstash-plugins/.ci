import os
import requests
import sys
import typing
from requests.adapters import HTTPAdapter, Retry

from ruamel.yaml import YAML

RELEASES_URL = "https://raw.githubusercontent.com/elastic/logstash/main/ci/logstash_releases.json"
TEST_COMMAND: typing.final = ".buildkite/scripts/pull-request-pipeline/run.sh"

def call_url_with_retry(url: str, max_retries: int = 5, delay: int = 1) -> requests.Response:
    schema = "https://" if "https://" in url else "http://"
    session = requests.Session()
    # retry on most common failures such as connection timeout(408), etc...
    retries = Retry(total=max_retries, backoff_factor=delay, status_forcelist=[408, 502, 503, 504])
    session.mount(schema, HTTPAdapter(max_retries=retries))
    return session.get(url)

def load_agent_config(config_path: str = ".ci/buildkite/agent-config.yaml") -> dict[str, typing.Any]:
    """Load agent configuration from YAML file."""
    yaml = YAML(typ='safe')
    with open(config_path, 'r') as f:
        config = yaml.load(f)
    return config

def load_plugin_ci_jobs_config(config_path: str = ".ci/.buildkite/scripts/pull-request-pipeline/plugin-ci-jobs.yaml") -> dict[str, typing.Any]:
    """Load plugin CI jobs configuration including exclude rules."""
    yaml = YAML(typ='safe')
    with open(config_path, 'r') as f:
        config = yaml.load(f)
    return config

def parse_exclude_env_params(exclude_data) -> dict[str, str]:
    """Parse exclude data (string or list) like 'ELASTIC_STACK_VERSION=7.current' into dict."""
    exclude_params = {}
    
    # Handle different YAML formats - could be string or list
    if isinstance(exclude_data, list):
        # If it's a list, join all items into one string
        exclude_string = ' '.join(exclude_data) if exclude_data else ''
    elif isinstance(exclude_data, str):
        exclude_string = exclude_data
    else:
        exclude_string = ''
    
    if exclude_string:
        # Split by spaces and parse key=value pairs
        parts = exclude_string.split()
        for part in parts:
            if '=' in part:
                key, value = part.split('=', 1)
                exclude_params[key] = value
    return exclude_params

def generate_unit_test_steps(stack_version, snapshot, exclude_params: dict[str, str] = None) -> list[typing.Any]:
    test_steps = []

    label_unit_test: typing.final = f"Unit test for {stack_version}, snapshot: {snapshot}"
    
    # Build env dictionary
    env = {
        "SNAPSHOT": snapshot,
        "ELASTIC_STACK_VERSION": stack_version
    }
    
    # Add DOCKER_ENV for 7.x+ versions
    if not stack_version.startswith("7."):
        env["DOCKER_ENV"] = "dockerjdk21.env"
    
    # Check if ALL exclude parameters match the current env
    if exclude_params:
        exclude_match = True
        for exclude_key, exclude_value in exclude_params.items():
            if env.get(exclude_key) != exclude_value:
                exclude_match = False
                break
        
        if exclude_match:
            # Return empty list if this env matches all exclude parameters
            return test_steps
    
    test_steps.append({
        "label": label_unit_test,
        "command": TEST_COMMAND,
        "env": env
    })
    return test_steps


if __name__ == "__main__":
    # TODO: if plugin uses its own agent (e.g. multi-jdk etc..), 
    #   we need to load it from plugin's own agent-config.yaml
    agent_config = load_agent_config()
    
    # Load plugin CI jobs config once to get exclude parameters
    plugin_config = {}
    exclude_params = {}
    try:
        plugin_config = load_plugin_ci_jobs_config()
    except FileNotFoundError:
        # If plugin-ci-jobs.yaml doesn't exist, continue without exclusions
        pass

    exclude_string = plugin_config.get("exclude", "")
    exclude_params = parse_exclude_env_params(exclude_string)

    structure = {
        "agents": agent_config,
        "steps": []}

    unit_test_steps = []
    response = call_url_with_retry(RELEASES_URL)
    versions_json = response.json()

    release_versions = versions_json.get("releases", [])
    snapshot_versions = versions_json.get("snapshots", [])

    for release_version in release_versions:
        steps = generate_unit_test_steps(release_version, "false", exclude_params)
        unit_test_steps += steps if steps else []

    for snapshot_version in snapshot_versions:
        steps = generate_unit_test_steps(snapshot_version, "true", exclude_params)
        unit_test_steps += steps if steps else []

    # TODO: group unit and integration tests by Logstash version for better visibility
    structure["steps"].append({
        "group": "pr-unit-tests",
        "key": "pr-unit-tests",
        "steps": unit_test_steps
    })

    jobs = plugin_config.get("jobs", [])
    for job in jobs:
        structure["steps"].append({
            "group": "plugins-tests",
            "key": "pr-plugin-tests",
            "steps": [
                {
                    "label": f"Integration test for {job}",
                    "command": TEST_COMMAND,
                    "env": parse_exclude_env_params(job)
                }
            ]
        })

    print(
        '# yaml-language-server: $schema=https://raw.githubusercontent.com/buildkite/pipeline-schema/main/schema.json')
    YAML().dump(structure, sys.stdout)