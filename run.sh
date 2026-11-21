#!/bin/sh
set -eu
python3 app/piefi_portal.py --bind 0.0.0.0 --port 8090
