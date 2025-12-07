#!/usr/bin/env python3
"""
claude_diagnostic.py - Figure out WTF is causing task re-execution

Run this to see the full picture of what's happening.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


def check_running_processes():
    """Check for Claude Code processes still running"""
    print("\n" + "="*60)
    print("🔍 RUNNING CLAUDE PROCESSES")
    print("="*60)
    
    try:
        result = subprocess.run(['pgrep', '-fl', 'claude'], 
                              capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
            return True
        else:
            print("✅ No Claude processes running")
            return False
    except:
        print("⚠️  Could not check processes")
        return False


def check_queue_state():
    """Check current queue state"""
    print("\n" + "="*60)
    print("📋 TASK QUEUE STATE")
    print("="*60)
    
    queue_file = "data/claude_task_queue.json"
    if not os.path.exists(queue_file):
        print("✅ No queue file")
        return {}
    
    with open(queue_file, 'r') as f:
        queue = json.load(f)
    
    tasks = queue.get("tasks", {})
    print(f"Total tasks in queue: {len(tasks)}")
    
    by_status = {}
    for tid, task in tasks.items():
        status = task.get("status", "unknown")
        by_status[status] = by_status.get(status, 0) + 1
    
    for status, count in by_status.items():
        print(f"  {status}: {count}")
    
    return tasks


def check_task_locks():
    """Check for lingering task locks"""
    print("\n" + "="*60)
    print("🔒 TASK LOCKS")
    print("="*60)
    
    locks_dir = "data/task_locks"
    if not os.path.exists(locks_dir):
        print("✅ No locks directory")
        return []
    
    locks = list(Path(locks_dir).glob("*.lock"))
    print(f"Active locks: {len(locks)}")
    
    for lock in locks:
        try:
            with open(lock, 'r') as f:
                lock_data = json.load(f)
            created = lock_data.get("created_at", "unknown")
            print(f"  {lock.name}: created {created}")
        except:
            print(f"  {lock.name}: (corrupted)")
    
    return locks


def check_results_timeline():
    """Check when results were written"""
    print("\n" + "="*60)
    print("📊 RESULTS TIMELINE")
    print("="*60)
    
    results_file = "data/claude_task_results.json"
    if not os.path.exists(results_file):
        print("✅ No results file")
        return {}
    
    with open(results_file, 'r') as f:
        results = json.load(f)
    
    all_results = results.get("results", {})
    print(f"Total completed tasks: {len(all_results)}")
    
    # Group by time
    now = datetime.now()
    recent = []
    
    for tid, result in all_results.items():
        completed = result.get("completed_at", "")
        if completed:
            try:
                completed_time = datetime.fromisoformat(completed.replace('Z', ''))
                age_minutes = (now - completed_time).total_seconds() / 60
                
                if age_minutes < 5:
                    recent.append((tid, age_minutes, result.get("description", "")[:50]))
            except:
                pass
    
    if recent:
        print(f"\n⚠️  {len(recent)} tasks completed in last 5 minutes:")
        for tid, age, desc in sorted(recent, key=lambda x: x[1]):
            print(f"  {age:.1f}min ago: {tid}")
            print(f"    → {desc}")
    else:
        print("✅ No tasks completed in last 5 minutes")
    
    return all_results


def check_execution_log():
    """Check recent execution_log activity"""
    print("\n" + "="*60)
    print("📝 RECENT EXECUTION LOG")
    print("="*60)
    
    log_file = "data/execution_log.json"
    if not os.path.exists(log_file):
        print("✅ No execution log")
        return []
    
    with open(log_file, 'r') as f:
        log = json.load(f)
    
    executions = log.get("executions", [])
    
    # Get last 10 executions
    recent = executions[-10:]
    
    print(f"Total executions: {len(executions)}")
    print(f"\nLast 10 executions:")
    
    for entry in recent:
        timestamp = entry.get("timestamp", "unknown")
        tool = entry.get("tool", "unknown")
        action = entry.get("action", "unknown")
        status = entry.get("result_status", "unknown")
        print(f"  {timestamp}: {tool}.{action} → {status}")
    
    return recent


def check_engines():
    """Check if automation engines are running"""
    print("\n" + "="*60)
    print("⚙️  AUTOMATION ENGINES")
    print("="*60)
    
    engines = [
        'automation_engine.py',
        'claude_execution_engine.py',
        'buffer_engine.py'
    ]
    
    for engine in engines:
        try:
            result = subprocess.run(['pgrep', '-f', engine], 
                                  capture_output=True, text=True)
            if result.stdout:
                pid = result.stdout.strip()
                print(f"✅ {engine}: running (PID {pid})")
            else:
                print(f"❌ {engine}: not running")
        except:
            print(f"⚠️  Could not check {engine}")


def check_for_duplicate_pattern():
    """Look for duplicate task pattern"""
    print("\n" + "="*60)
    print("🔍 DUPLICATE DETECTION")
    print("="*60)
    
    results_file = "data/claude_task_results.json"
    if not os.path.exists(results_file):
        print("✅ No results to analyze")
        return
    
    with open(results_file, 'r') as f:
        results = json.load(f)
    
    all_results = results.get("results", {})
    
    # Group by description
    by_desc = {}
    for tid, result in all_results.items():
        desc = result.get("description", "")[:100]  # First 100 chars
        if desc not in by_desc:
            by_desc[desc] = []
        by_desc[desc].append((tid, result.get("completed_at", "")))
    
    # Find duplicates
    duplicates = {desc: tasks for desc, tasks in by_desc.items() if len(tasks) > 1}
    
    if duplicates:
        print(f"⚠️  Found {len(duplicates)} tasks executed multiple times:")
        for desc, tasks in list(duplicates.items())[:5]:  # Show first 5
            print(f"\n  \"{desc}...\"")
            print(f"  Executed {len(tasks)} times:")
            for tid, completed in tasks:
                print(f"    - {tid} at {completed}")
    else:
        print("✅ No duplicate executions detected")


def check_self_assignment_task():
    """Check if self-assignment meta-task is still active"""
    print("\n" + "="*60)
    print("🎯 SELF-ASSIGNMENT META-TASK")
    print("="*60)
    
    queue_file = "data/claude_task_queue.json"
    if not os.path.exists(queue_file):
        print("✅ No queue file")
        return
    
    with open(queue_file, 'r') as f:
        queue = json.load(f)
    
    tasks = queue.get("tasks", {})
    
    meta_tasks = {}
    for tid, task in tasks.items():
        desc = task.get("description", "").lower()
        if "self" in desc and "assign" in desc:
            meta_tasks[tid] = task
    
    if meta_tasks:
        print(f"⚠️  Found {len(meta_tasks)} self-assignment meta-task(s):")
        for tid, task in meta_tasks.items():
            status = task.get("status", "unknown")
            created = task.get("created_at", "unknown")
            print(f"\n  {tid}")
            print(f"  Status: {status}")
            print(f"  Created: {created}")
            print(f"  Desc: {task.get('description', '')[:100]}")
    else:
        print("✅ No self-assignment meta-tasks in queue")


def main():
    print("╔" + "="*58 + "╗")
    print("║" + " "*15 + "CLAUDE DIAGNOSTIC TOOL" + " "*21 + "║")
    print("╚" + "="*58 + "╝")
    
    has_processes = check_running_processes()
    queue_tasks = check_queue_state()
    locks = check_task_locks()
    results = check_results_timeline()
    recent_exec = check_execution_log()
    check_engines()
    check_for_duplicate_pattern()
    check_self_assignment_task()
    
    # Summary
    print("\n" + "="*60)
    print("🎯 DIAGNOSTIC SUMMARY")
    print("="*60)
    
    issues = []
    
    if has_processes:
        issues.append("⚠️  Claude processes still running")
    
    if len(queue_tasks) > 0:
        issues.append(f"⚠️  {len(queue_tasks)} tasks still in queue")
    
    if len(locks) > 0:
        issues.append(f"⚠️  {len(locks)} task locks still active")
    
    if issues:
        print("\n".join(issues))
        print("\n💡 LIKELY CAUSE:")
        if has_processes:
            print("  Claude Code session still executing tasks")
            print("  → Run: pkill claude")
        if len(locks) > 0:
            print("  Stale locks preventing cleanup")
            print("  → Run: rm data/task_locks/*.lock")
    else:
        print("✅ System appears idle")
        print("🤔 If tasks are still being added, check:")
        print("   - claude_execution_engine.py polling")
        print("   - Orphan detection resetting tasks")
        print("   - External triggers (cron, launchd)")


if __name__ == '__main__':
    main()