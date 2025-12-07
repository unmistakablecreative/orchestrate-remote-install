#!/usr/bin/env python3
"""
System Health Check - Quick diagnostics for OrchestrateOS

Usage: python3 tools/system_health_check.py
"""

import os
import json
import subprocess
from datetime import datetime

def check(name, condition, fix=None):
    """Print check result"""
    status = "✅" if condition else "❌"
    print(f"{status} {name}")
    if not condition and fix:
        print(f"   Fix: {fix}")
    return condition

def main():
    print("=== OrchestrateOS Health Check ===\n")

    # Engine checks
    print("ENGINES:")
    claude_engine = subprocess.run(['pgrep', '-f', 'claude_execution_engine'], capture_output=True).returncode == 0
    check("claude_execution_engine running", claude_engine, "python3 tools/claude_execution_engine.py run_engine > /tmp/engine.log 2>&1 &")

    auto_engine = subprocess.run(['pgrep', '-f', 'automation_engine'], capture_output=True).returncode == 0
    check("automation_engine running", auto_engine, "python3 tools/automation_engine.py run_engine > /tmp/automation.log 2>&1 &")

    # Queue checks
    print("\nQUEUE:")
    lockfile_exists = os.path.exists('data/execute_queue.lock')
    check("execute_queue.lock exists", lockfile_exists)

    with open('data/claude_task_queue.json', 'r') as f:
        queue = json.load(f)

    tasks = queue.get('tasks', {})
    queued = [tid for tid, t in tasks.items() if t.get('status') == 'queued']
    in_progress = [tid for tid, t in tasks.items() if t.get('status') == 'in_progress']

    print(f"   Queued: {len(queued)}")
    print(f"   In progress: {len(in_progress)}")

    if in_progress and not lockfile_exists:
        print(f"   ⚠️  Tasks stuck in_progress without lockfile: {in_progress}")
        print(f"   Fix: Manually clear or wait for timeout")

    # Recent results
    print("\nRECENT RESULTS:")
    with open('data/claude_task_results.json', 'r') as f:
        results = json.load(f)

    recent = sorted(results.get('results', {}).items(),
                   key=lambda x: x[1].get('completed_at', ''),
                   reverse=True)[:3]

    for task_id, data in recent:
        tokens = data.get('tokens', {})
        batch = data.get('batch_id', 'none')[:20]
        print(f"   {task_id[:30]}: {data.get('status')} | batch:{batch} | tokens:{tokens.get('total', 'N/A')}")

    # Token check
    print("\nTOKEN CAPTURE:")
    has_tokens = any(r[1].get('tokens') for r in recent)
    check("Recent tasks have token data", has_tokens, "Check if telemetry instruction in prompt")

    # Batch check
    has_batch = any(r[1].get('batch_id') for r in recent)
    check("Recent tasks have batch_id", has_batch, "Check batch_id read before task deletion")

    print("\n=== End Health Check ===")

if __name__ == "__main__":
    main()
