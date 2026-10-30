#!/usr/bin/env bash
# Build dist/logrotate-lite-<version>.tar.gz
set -eu
cd "$(dirname "$0")/.."

version="$(cat VERSION)"
name="logrotate-lite-$version"
tar czf "dist/$name.tar.gz" --transform "s,^,$name/," bin lib README.md VERSION test
echo "built dist/$name.tar.gz"
