#!/bin/sh

set -e
eval $(python3 exporter.py)
python3 app.py