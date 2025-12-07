#!/bin/bash
cd "$HOME/Orchestrate Github/orchestrate-jarvis"
exec python3 tools/outline_editor.py watch --debounce 0.1
