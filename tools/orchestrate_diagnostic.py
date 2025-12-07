#!/usr/bin/env python3
"""
OrchestrateOS Full Stack Diagnostic
Traces entire architecture: Launchd → Engine Launcher → Individual Engines → Task Queue
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def section(title):
    print("\n" + "="*70)
    print(f"🔍 {title}")
    print("="*70)


def get_process_tree():
    """Get full process tree for orchestrate components"""
    section("PROCESS TREE")
    
    components = {
        'launchd': 'com.orchestrate',
        'engine_launcher': 'engine_launcher.py',
        'jarvis': 'jarvis.py',
        'automation': 'automation_engine.py',
        'claude_exec': 'claude_execution_engine.py',
        'buffer': 'buffer_engine.py',
        'podcast': 'podcast_publisher.py',
        'claude_sessions': 'claude.*execute'
    }
    
    processes = {}
    for name, pattern in components.items():
        try:
            result = subprocess.run(
                ['pgrep', '-fl', pattern],
                capture_output=True,
                text=True
            )
            if result.stdout.strip():
                pids = []
                for line in result.stdout.strip().split('\n'):
                    pid = line.split()[0]
                    pids.append(pid)
                processes[name] = pids
                
                # Check parent PID
                for pid in pids:
                    try:
                        ps_result = subprocess.run(
                            ['ps', '-o', 'ppid=', '-p', pid],
                            capture_output=True,
                            text=True
                        )
                        ppid = ps_result.stdout.strip()
                        print(f"  {name}: PID {pid} (parent: {ppid})")
                    except:
                        print(f"  {name}: PID {pid}")
            else:
                processes[name] = []
                print(f"  {name}: NOT RUNNING")
        except Exception as e:
            print(f"  {name}: Error checking ({e})")
            processes[name] = []
    
    return processes


def check_launchd():
    """Check if launchd is managing orchestrate"""
    section("LAUNCHD CONFIGURATION")
    
    try:
        result = subprocess.run(
            ['launchctl', 'list'],
            capture_output=True,
            text=True
        )
        
        orchestrate_services = [
            line for line in result.stdout.split('\n')
            if 'orchestrate' in line.lower()
        ]
        
        if orchestrate_services:
            print("  Launchd is managing:")
            for service in orchestrate_services:
                print(f"    {service}")
                
            # Check plist location
            plist_path = Path.home() / "Library/LaunchAgents"
            plists = list(plist_path.glob("*orchestrate*.plist"))
            if plists:
                print(f"\n  Plist files:")
                for plist in plists:
                    print(f"    {plist}")
        else:
            print("  ✅ Launchd NOT managing orchestrate")
    except Exception as e:
        print(f"  Error checking launchd: {e}")


def check_engine_registry():
    """Check what engines are configured"""
    section("ENGINE REGISTRY")
    
    registry_path = "data/engine_registry.json"
    if os.path.exists(registry_path):
        with open(registry_path, 'r') as f:
            registry = json.load(f)
        
        engines = registry.get('engines', [])
        print(f"  Configured engines: {len(engines)}")
        for engine in engines:
            print(f"    - {engine}")
    else:
        print("  ❌ engine_registry.json not found")


def check_task_queue_state():
    """Check current task queue and recent activity"""
    section("TASK QUEUE STATE")
    
    queue_file = "data/claude_task_queue.json"
    results_file = "data/claude_task_results.json"
    locks_dir = "data/task_locks"
    
    # Queue
    if os.path.exists(queue_file):
        with open(queue_file, 'r') as f:
            queue = json.load(f)
        tasks = queue.get('tasks', {})
        
        if tasks:
            print(f"  Queue: {len(tasks)} task(s)")
            by_status = {}
            for task in tasks.values():
                status = task.get('status', 'unknown')
                by_status[status] = by_status.get(status, 0) + 1
            
            for status, count in by_status.items():
                print(f"    {status}: {count}")
        else:
            print("  Queue: EMPTY")
    else:
        print("  Queue: File not found")
    
    # Results
    if os.path.exists(results_file):
        with open(results_file, 'r') as f:
            results = json.load(f)
        
        all_results = results.get('results', {})
        if all_results:
            print(f"\n  Results: {len(all_results)} completed")
            
            # Check recent activity (last 10 minutes)
            now = datetime.now()
            recent = []
            for tid, result in all_results.items():
                completed = result.get('completed_at', '')
                if completed:
                    try:
                        completed_time = datetime.fromisoformat(completed.replace('Z', ''))
                        age_minutes = (now - completed_time).total_seconds() / 60
                        if age_minutes < 10:
                            recent.append((tid, age_minutes))
                    except:
                        pass
            
            if recent:
                print(f"  Recent completions (last 10 min): {len(recent)}")
                for tid, age in recent[:5]:
                    print(f"    {tid}: {age:.1f} min ago")
        else:
            print("\n  Results: EMPTY")
    else:
        print("\n  Results: File not found")
    
    # Locks
    if os.path.exists(locks_dir):
        locks = list(Path(locks_dir).glob("*.lock"))
        if locks:
            print(f"\n  Task locks: {len(locks)} active")
            for lock in locks[:5]:
                age = (datetime.now().timestamp() - lock.stat().st_mtime) / 60
                print(f"    {lock.name}: {age:.1f} min old")
        else:
            print("\n  Task locks: NONE")
    else:
        print("\n  Task locks: Directory not found")


def check_file_integrity():
    """Check critical JSON files for corruption"""
    section("FILE INTEGRITY")
    
    critical_files = [
        "data/claude_task_queue.json",
        "data/claude_task_results.json",
        "data/execution_log.json",
        "data/working_memory.json",
        "system_settings.ndjson"
    ]
    
    for filepath in critical_files:
        if not os.path.exists(filepath):
            print(f"  ❌ {filepath}: NOT FOUND")
            continue
        
        try:
            with open(filepath, 'r') as f:
                if filepath.endswith('.ndjson'):
                    # Validate each line
                    for i, line in enumerate(f, 1):
                        if line.strip():
                            json.loads(line)
                else:
                    json.load(f)
            print(f"  ✅ {filepath}: OK")
        except json.JSONDecodeError as e:
            print(f"  ❌ {filepath}: CORRUPTED ({e})")
        except Exception as e:
            print(f"  ⚠️  {filepath}: ERROR ({e})")


def analyze_root_cause(processes):
    """Analyze what's causing issues"""
    section("ROOT CAUSE ANALYSIS")
    
    issues = []
    
    # Check for duplicate engines
    if len(processes.get('claude_exec', [])) > 1:
        issues.append({
            'severity': 'CRITICAL',
            'issue': 'Multiple claude_execution_engine processes',
            'pids': processes['claude_exec'],
            'cause': 'Engine spawned multiple times (launchd + manual?)',
            'fix': 'Kill all, restart via launchd OR engine_launcher (not both)'
        })
    
    # Check if both launchd AND engine_launcher are running
    if processes.get('launchd') and processes.get('engine_launcher'):
        issues.append({
            'severity': 'HIGH',
            'issue': 'Launchd AND engine_launcher both active',
            'cause': 'Conflicting management - both trying to keep engines alive',
            'fix': 'Choose ONE: launchd OR engine_launcher, disable the other'
        })
    
    # Check for active Claude sessions with no queue
    queue_file = "data/claude_task_queue.json"
    if processes.get('claude_sessions') and os.path.exists(queue_file):
        with open(queue_file, 'r') as f:
            queue = json.load(f)
        if not queue.get('tasks'):
            issues.append({
                'severity': 'MEDIUM',
                'issue': 'Claude session running with empty queue',
                'cause': 'Session may be completing final tasks',
                'fix': 'Wait 5 minutes or pkill claude if truly stuck'
            })
    
    if issues:
        print(f"  Found {len(issues)} issue(s):\n")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. [{issue['severity']}] {issue['issue']}")
            if 'pids' in issue:
                print(f"     PIDs: {', '.join(issue['pids'])}")
            print(f"     Cause: {issue['cause']}")
            print(f"     Fix: {issue['fix']}\n")
    else:
        print("  ✅ No critical issues detected")


def generate_fix_commands(processes):
    """Generate exact commands to fix issues"""
    section("RECOMMENDED FIX")
    
    if len(processes.get('claude_exec', [])) > 1:
        print("  DUPLICATE ENGINES DETECTED\n")
        print("  Step 1: Kill ALL engines")
        print("    pkill -f claude_execution_engine.py")
        print("    pkill -f automation_engine.py")
        print("    pkill -f buffer_engine.py")
        print("    pkill -f podcast_publisher.py")
        print("\n  Step 2: Check if launchd will restart them")
        print("    launchctl list | grep orchestrate")
        print("\n  Step 3a: If launchd manages them (RECOMMENDED)")
        print("    launchctl unload ~/Library/LaunchAgents/com.orchestrate.*.plist")
        print("    launchctl load ~/Library/LaunchAgents/com.orchestrate.*.plist")
        print("\n  Step 3b: If manual management")
        print("    python3 engine_launcher.py start")
    else:
        print("  ✅ System appears healthy")
        print("\n  To restart engines:")
        print("    launchctl unload ~/Library/LaunchAgents/com.orchestrate.*.plist")
        print("    launchctl load ~/Library/LaunchAgents/com.orchestrate.*.plist")


def main():
    print("\n╔" + "="*68 + "╗")
    print("║" + " "*15 + "ORCHESTRATEOS FULL DIAGNOSTIC" + " "*24 + "║")
    print("╚" + "="*68 + "╝")
    
    processes = get_process_tree()
    check_launchd()
    check_engine_registry()
    check_task_queue_state()
    check_file_integrity()
    analyze_root_cause(processes)
    generate_fix_commands(processes)
    
    print("\n" + "="*70)
    print("Diagnostic complete")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()