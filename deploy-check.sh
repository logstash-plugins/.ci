#!/bin/bash

VERSION=$(ruby -rrubygems -e 'gemspec_path = Dir.glob("*.gemspec").first; puts "v" + Gem::Specification.load(gemspec_path).version.to_s')
ruby -e "versions = IO.popen(\"git tag -l\").read.split(\"\n\"); exit(1) if versions.include?(\"${VERSION}\")"

status=$?

[ $status -eq 0 ] && echo "Ready to publish!" || echo "Tag for version ${VERSION} already exists, skipping publish."

exit $status
