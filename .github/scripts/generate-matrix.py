#!/usr/bin/env python3
import json
import yaml

with open("logstash-versions.yml") as f:
    data = yaml.safe_load(f)

versions = []
for track, version in data.get("releases", {}).items():
    versions.append({"logstash-release-track": track, "version": version, "type": "release"})
for track, version in data.get("snapshots", {}).items():
    versions.append({"logstash-release-track": track, "version": version, "type": "snapshot"})

print(json.dumps({"include": versions}))
