#!/usr/bin/env bash
set -euo pipefail

repository_root="$(git rev-parse --show-toplevel)"
output_path="${1:-$repository_root/dist/tulite-release.tar.gz}"

case "$output_path" in
  /*) ;;
  *) output_path="$PWD/$output_path" ;;
esac

mkdir -p "$(dirname "$output_path")"

# git archive packages committed application sources only. Runtime data,
# local environment files and agent scratch directories cannot enter the bundle.
git -C "$repository_root" archive \
  --format=tar.gz \
  --prefix=tulite/ \
  --output="$output_path" \
  HEAD

printf 'Release package: %s\n' "$output_path"
