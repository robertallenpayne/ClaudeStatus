#!/usr/bin/env bash
# Launch the Claude Status widget using the project venv.
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
    /opt/homebrew/bin/python3.12 -m venv .venv
    .venv/bin/pip install -q customtkinter
fi
.venv/bin/python3 widget.py
