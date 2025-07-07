#!/bin/bash

REGEN_SCRIPT="./ruyi/resource_bundle/__main__.py"

cd "$(dirname "${BASH_SOURCE[0]}")"/.. || exit
if ! "$REGEN_SCRIPT"; then
    echo "error: syncing of resource bundle failed" >&2
    exit 1
fi

if ! git diff --exit-code ruyi/resource_bundle > /dev/null; then
    echo "error: resource bundle modified but not synced to Python package" >&2
    echo "info: re-run $REGEN_SCRIPT to do so" >&2
    exit 1
fi

echo "info: ✅ resource bundle is properly synced" >&2
exit 0
