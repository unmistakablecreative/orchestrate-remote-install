#!/usr/bin/env python3
"""
Path configuration for OrchestrateOS remote installations.
All tools should import paths from here instead of hardcoding them.
"""
import os
from pathlib import Path

# ORCHESTRATE_HOME can be set as env var, defaults to ~/Orchestrate Github/orchestrate-jarvis
ORCHESTRATE_HOME = Path(os.environ.get(
    'ORCHESTRATE_HOME',
    os.path.expanduser('~/Orchestrate Github/orchestrate-jarvis')
))

# Common paths derived from ORCHESTRATE_HOME
DATA_DIR = ORCHESTRATE_HOME / 'data'
TOOLS_DIR = ORCHESTRATE_HOME / 'tools'
QUEUE_DIR = ORCHESTRATE_HOME / 'outline_docs_queue'
SEMANTIC_MEMORY_DIR = ORCHESTRATE_HOME / 'semantic_memory'
BLOG_DRAFTS_DIR = ORCHESTRATE_HOME / 'blog_drafts'
PUBLISH_READY_DIR = ORCHESTRATE_HOME / 'publish_ready'

# Key data files
TASK_QUEUE_FILE = DATA_DIR / 'claude_task_queue.json'
TASK_RESULTS_FILE = DATA_DIR / 'claude_task_results.json'
OUTLINE_QUEUE_FILE = DATA_DIR / 'outline_queue.json'
SYSTEM_SETTINGS_FILE = ORCHESTRATE_HOME / 'system_settings.ndjson'
CREDENTIALS_FILE = ORCHESTRATE_HOME / 'credentials.json'

def ensure_dirs():
    """Create required directories if they don't exist."""
    for d in [DATA_DIR, TOOLS_DIR, QUEUE_DIR, SEMANTIC_MEMORY_DIR, BLOG_DRAFTS_DIR, PUBLISH_READY_DIR]:
        d.mkdir(parents=True, exist_ok=True)
