#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../backend"

mapfile -t test_files < <(find tests -maxdepth 1 -type f -name 'test_*.py' | sort)
if [[ ${#test_files[@]} -eq 0 ]]; then
  echo "No backend tests found." >&2
  exit 1
fi

echo "Running ${#test_files[@]} backend test files in isolated pytest processes..."
for test_file in "${test_files[@]}"; do
  echo "==> pytest ${test_file}"
  timeout 120s pytest -q "$test_file"
done

echo "All backend test files passed."
