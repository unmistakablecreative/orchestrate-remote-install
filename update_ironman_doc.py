#!/usr/bin/env python3
import json
import sys
import os

# Change to the project directory
os.chdir('$HOME/Orchestrate Github/orchestrate-jarvis')
sys.path.insert(0, '$HOME/Orchestrate Github/orchestrate-jarvis')
sys.path.insert(0, '$HOME/Orchestrate Github/orchestrate-jarvis/tools')

from tools.outline_editor import update_doc

# Read the updated content
with open('data/ironman_update.md', 'r') as f:
    content = f.read()

# Update the document
try:
    result = update_doc({
        'doc_id': 'e0daf702-84c9-4f7b-9728-6a0a2c794fae',
        'text': content,
        'append': False,
        'publish': True
    })
    print(json.dumps(result, indent=2))
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
