#!/bin/bash

set -e

poetry install --only=main
poetry run pip install pylic

poetry run pylic list
poetry run pylic check
