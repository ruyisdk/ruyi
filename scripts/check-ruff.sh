#!/bin/bash

set -e

poetry install --with=dev

poetry run ruff check
