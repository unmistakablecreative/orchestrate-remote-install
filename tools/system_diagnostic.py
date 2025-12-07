#!/usr/bin/env python3
"""
OrchestrateOS System Diagnostic

One command that replaces 70 exploratory commands.
Shows complete system health instantly.

Usage: python3 tools/system_diagnostic.py
"""

import os
import sys
import json
import subprocess
import importlib.util
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# Color codes
RED = '\033[91m'
YELLOW = '\033[93m'
GREEN = '\033[92m'
RESET = '\033[0m'
BOLD = '\033[1m'

class SystemDiagnostic:
    def __init__(self):
        self.issues_critical = []
        self.issues_warning = []
        self.base_path = Path('$HOME/Orchestrate Github/orchestrate-jarvis')

    def check_processes(self):
        """Check all running processes and system resources"""
        print(f"\n{BOLD}PROCESSES:{RESET}")
        issues = []

        # Check required engines from engine_registry.json
        try:
            with open(self.base_path / 'data/engine_registry.json') as f:
                registry = json.load(f)
                required_engines = registry.get('engines', [])
        except:
            required_engines = ['automation_engine.py', 'claude_execution_engine.py',
                              'buffer_engine.py', 'podcast_publisher.py']

        # Check each engine
        for engine in required_engines:
            result = subprocess.run(['pgrep', '-f', engine], capture_output=True, text=True)
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                pid = pids[0]
                # Get uptime
                ps_result = subprocess.run(['ps', '-p', pid, '-o', 'etime='],
                                         capture_output=True, text=True)
                uptime = ps_result.stdout.strip() if ps_result.returncode == 0 else 'unknown'
                print(f"   ✅ {engine}: PID {pid}, uptime {uptime}")
            else:
                print(f"   {RED}❌ {engine}: NOT RUNNING{RESET}")
                issues.append(f"{engine} not running")

        # Check for zombie Claude sessions
        claude_result = subprocess.run(['pgrep', '-f', 'claude'], capture_output=True, text=True)
        if claude_result.returncode == 0:
            claude_pids = [p for p in claude_result.stdout.strip().split('\n') if p]
            if len(claude_pids) > 2:  # More than expected
                print(f"   {YELLOW}⚠️  {len(claude_pids)} Claude processes detected (possible zombies){RESET}")
                print(f"       PIDs: {', '.join(claude_pids)}")
                issues.append(f"Multiple Claude sessions: {', '.join(claude_pids)}")

        # Check memory usage
        vm_result = subprocess.run(['vm_stat'], capture_output=True, text=True)
        if vm_result.returncode == 0:
            lines = vm_result.stdout.split('\n')
            # Parse memory stats (this is macOS specific)
            free_pages = int([l for l in lines if 'Pages free' in l][0].split(':')[1].strip().rstrip('.'))
            page_size = 4096  # 4KB pages on macOS
            free_gb = (free_pages * page_size) / (1024**3)

            # Get total memory
            total_result = subprocess.run(['sysctl', 'hw.memsize'], capture_output=True, text=True)
            total_mem = int(total_result.stdout.split(':')[1].strip())
            total_gb = total_mem / (1024**3)
            used_percent = ((total_gb - free_gb) / total_gb) * 100

            if used_percent > 85:
                print(f"   {YELLOW}⚠️  Memory usage: {used_percent:.1f}% ({total_gb - free_gb:.1f}GB/{total_gb:.1f}GB){RESET}")
                issues.append(f"High memory usage: {used_percent:.1f}%")
            else:
                print(f"   ✅ Memory usage: {used_percent:.1f}% ({total_gb - free_gb:.1f}GB/{total_gb:.1f}GB)")

        # Check disk space
        df_result = subprocess.run(['df', '-h', str(self.base_path)], capture_output=True, text=True)
        if df_result.returncode == 0:
            lines = df_result.stdout.strip().split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                capacity = parts[4].rstrip('%')
                available = parts[3]
                if int(capacity) > 85:
                    print(f"   {RED}❌ Disk space: {capacity}% used, {available} remaining{RESET}")
                    issues.append(f"Low disk space: {capacity}% used")
                else:
                    print(f"   ✅ Disk space: {capacity}% used, {available} remaining")

        # Check CPU usage
        top_result = subprocess.run(['top', '-l', '1', '-n', '0'], capture_output=True, text=True)
        if top_result.returncode == 0:
            cpu_line = [l for l in top_result.stdout.split('\n') if 'CPU usage' in l]
            if cpu_line:
                print(f"   ✅ {cpu_line[0].strip()}")

        # Check for port conflicts
        ports_to_check = [5001, 8000, 8080]
        for port in ports_to_check:
            lsof_result = subprocess.run(['lsof', '-i', f':{port}'], capture_output=True, text=True)
            if lsof_result.returncode == 0 and lsof_result.stdout:
                lines = lsof_result.stdout.strip().split('\n')[1:]  # Skip header
                if lines:
                    process = lines[0].split()[0]
                    print(f"   ℹ️  Port {port}: in use by {process}")

        return issues

    def check_filesystem(self):
        """Check all required files and their validity"""
        print(f"\n{BOLD}FILESYSTEM:{RESET}")
        issues = []

        # Required JSON files
        required_files = {
            'data/claude_task_queue.json': 'Claude task queue',
            'data/claude_task_results.json': 'Claude task results',
            'data/execution_context.json': 'Execution context',
            'data/outline_queue.json': 'Outline queue',
            'data/outline_reference.json': 'Outline reference',
            'data/outline_aliases.json': 'Outline aliases',
            'data/youtube_published.json': 'YouTube published',
            'data/youtube_publish_queue.json': 'YouTube queue',
            'data/engine_registry.json': 'Engine registry',
            'data/working_memory.json': 'Working memory'
        }

        json_valid_count = 0
        json_total = len(required_files)

        for file_path, description in required_files.items():
            full_path = self.base_path / file_path
            if not full_path.exists():
                print(f"   {RED}❌ {description}: FILE MISSING{RESET}")
                issues.append(f"Missing file: {file_path}")
                continue

            # Validate JSON syntax
            try:
                with open(full_path) as f:
                    json.load(f)
                json_valid_count += 1
            except json.JSONDecodeError as e:
                print(f"   {RED}❌ {description}: CORRUPT at line {e.lineno}{RESET}")
                issues.append(f"Corrupted JSON: {file_path} line {e.lineno}")
                continue
            except Exception as e:
                print(f"   {RED}❌ {description}: ERROR - {str(e)}{RESET}")
                issues.append(f"Error reading {file_path}: {str(e)}")
                continue

        if json_valid_count == json_total:
            print(f"   ✅ All {json_total} JSON files valid")
        else:
            print(f"   {YELLOW}⚠️  {json_valid_count}/{json_total} JSON files valid{RESET}")

        # Check for stale lock files
        lock_files = list(self.base_path.glob('data/*.lock'))
        if lock_files:
            print(f"   {YELLOW}⚠️  {len(lock_files)} lock file(s) found:{RESET}")
            for lock_file in lock_files:
                # Check age
                age_seconds = (datetime.now().timestamp() - lock_file.stat().st_mtime)
                age_minutes = age_seconds / 60
                print(f"       {lock_file.name} (age: {age_minutes:.1f} min)")
                if age_minutes > 10:
                    issues.append(f"Stale lock file: {lock_file.name} ({age_minutes:.1f} min old)")

        # Check log file sizes
        log_files = list(self.base_path.glob('data/*.log'))
        large_logs = []
        for log_file in log_files:
            size_mb = log_file.stat().st_size / (1024 * 1024)
            if size_mb > 100:
                large_logs.append((log_file.name, size_mb))

        if large_logs:
            print(f"   {YELLOW}⚠️  Large log files:{RESET}")
            for name, size in large_logs:
                print(f"       {name}: {size:.1f}MB")
                issues.append(f"Large log: {name} ({size:.1f}MB)")

        # Check write permissions
        try:
            test_file = self.base_path / 'data/.write_test'
            test_file.write_text('test')
            test_file.unlink()
            print(f"   ✅ Write permissions OK")
        except Exception as e:
            print(f"   {RED}❌ Cannot write to data/ directory{RESET}")
            issues.append(f"No write permission: {str(e)}")

        return issues

    def check_configuration(self):
        """Check configuration and environment"""
        print(f"\n{BOLD}CONFIGURATION:{RESET}")
        issues = []

        # Check environment variables
        required_env_vars = {
            'OUTLINE_API_KEY': 'Outline API',
            'NYLAS_API_KEY': 'Nylas API',
            'BRAVE_API_KEY': 'Brave Search API'
        }

        env_ok = True
        for var, description in required_env_vars.items():
            if os.environ.get(var):
                # Don't print the actual value
                pass
            else:
                print(f"   {RED}❌ Missing: {var} ({description}){RESET}")
                issues.append(f"Missing env var: {var}")
                env_ok = False

        if env_ok:
            print(f"   ✅ All environment variables set")

        # Validate execution_context.json schema
        try:
            with open(self.base_path / 'data/execution_context.json') as f:
                ctx = json.load(f)

            required_keys = ['outline_config', 'execution_rules', 'tool_policies',
                           'critical_file_paths', 'api_endpoints']
            missing_keys = [k for k in required_keys if k not in ctx]

            if missing_keys:
                print(f"   {RED}❌ execution_context.json missing keys: {', '.join(missing_keys)}{RESET}")
                issues.append(f"Invalid execution_context: missing {', '.join(missing_keys)}")
            else:
                print(f"   ✅ execution_context.json schema valid")
        except Exception as e:
            print(f"   {RED}❌ execution_context.json: {str(e)}{RESET}")
            issues.append(f"execution_context error: {str(e)}")

        # Check tool imports
        tools_to_check = [
            'tools/outline_editor.py',
            'tools/claude_assistant.py',
            'tools/automation_engine.py',
            'tools/claude_execution_engine.py'
        ]

        tools_ok = True
        for tool_path in tools_to_check:
            full_path = self.base_path / tool_path
            if not full_path.exists():
                print(f"   {RED}❌ Tool missing: {tool_path}{RESET}")
                issues.append(f"Missing tool: {tool_path}")
                tools_ok = False

        if tools_ok:
            print(f"   ✅ All critical tools present")

        # Test API connectivity
        api_endpoints = {
            'Outline': 'https://app.getoutline.com/api/collections.list',
            'Execution Hub': 'http://localhost:5001/get_supported_actions'
        }

        for api_name, endpoint in api_endpoints.items():
            try:
                if 'localhost' in endpoint:
                    # Just check if port is open
                    result = subprocess.run(['lsof', '-i', ':5001'], capture_output=True)
                    if result.returncode == 0:
                        print(f"   ✅ {api_name}: reachable")
                    else:
                        print(f"   {YELLOW}⚠️  {api_name}: port not open{RESET}")
                        issues.append(f"{api_name} not running")
                else:
                    # For external APIs, we'd need to actually make a request
                    # but we don't want to spam APIs in diagnostics
                    pass
            except Exception as e:
                print(f"   {RED}❌ {api_name}: {str(e)}{RESET}")
                issues.append(f"{api_name} unreachable: {str(e)}")

        return issues

    def check_operations(self):
        """Check recent task execution and performance"""
        print(f"\n{BOLD}OPERATIONS:{RESET}")
        issues = []

        try:
            with open(self.base_path / 'data/claude_task_results.json') as f:
                results_data = json.load(f)
                results = results_data.get('results', {})
        except Exception as e:
            print(f"   {RED}❌ Cannot read task results: {str(e)}{RESET}")
            return [f"Cannot read task results: {str(e)}"]

        # Get last 20 tasks
        recent_tasks = sorted(results.items(),
                             key=lambda x: x[1].get('completed_at', ''),
                             reverse=True)[:20]

        if not recent_tasks:
            print(f"   {YELLOW}⚠️  No recent task results{RESET}")
            return issues

        # Calculate success rate
        successes = sum(1 for _, t in recent_tasks if t.get('status') == 'completed')
        total = len(recent_tasks)
        success_rate = (successes / total) * 100 if total > 0 else 0

        if success_rate >= 90:
            print(f"   ✅ Success rate: {successes}/{total} ({success_rate:.0f}%)")
        elif success_rate >= 70:
            print(f"   {YELLOW}⚠️  Success rate: {successes}/{total} ({success_rate:.0f}%){RESET}")
            issues.append(f"Success rate below 90%: {success_rate:.0f}%")
        else:
            print(f"   {RED}❌ Success rate: {successes}/{total} ({success_rate:.0f}%){RESET}")
            issues.append(f"Low success rate: {success_rate:.0f}%")

        # Calculate average execution time
        execution_times = []
        for task_id, task_data in recent_tasks:
            if task_data.get('started_at') and task_data.get('completed_at'):
                try:
                    start = datetime.fromisoformat(task_data['started_at'].replace('Z', '+00:00'))
                    end = datetime.fromisoformat(task_data['completed_at'].replace('Z', '+00:00'))
                    duration = (end - start).total_seconds()
                    execution_times.append(duration)
                except:
                    pass

        if execution_times:
            avg_time = sum(execution_times) / len(execution_times)
            print(f"   ✅ Average execution time: {avg_time:.1f}s")

        # Analyze error patterns
        error_messages = defaultdict(int)
        for task_id, task_data in recent_tasks:
            if task_data.get('status') == 'failed':
                error = task_data.get('error', 'Unknown error')
                # Extract key part of error
                error_key = error.split('\n')[0][:100]  # First line, max 100 chars
                error_messages[error_key] += 1

        if error_messages:
            print(f"   {YELLOW}⚠️  Error patterns in last {total} tasks:{RESET}")
            for error, count in sorted(error_messages.items(), key=lambda x: x[1], reverse=True)[:3]:
                print(f"       {count}x: {error}")
                if count >= 3:
                    issues.append(f"Recurring error ({count}x): {error[:50]}...")

        # Check token usage
        token_totals = []
        for task_id, task_data in recent_tasks:
            tokens = task_data.get('tokens', {})
            if tokens and isinstance(tokens, dict):
                total_tokens = tokens.get('total')
                if total_tokens:
                    token_totals.append(total_tokens)

        if token_totals:
            avg_tokens = sum(token_totals) / len(token_totals)
            max_tokens = max(token_totals)
            print(f"   ✅ Token usage: avg {avg_tokens:.0f}, max {max_tokens}")

            if max_tokens > 100000:
                print(f"   {YELLOW}⚠️  High token usage detected: {max_tokens} tokens{RESET}")
                issues.append(f"Token spike: {max_tokens} tokens")

        # Check queue backlog
        try:
            with open(self.base_path / 'data/claude_task_queue.json') as f:
                queue_data = json.load(f)
                tasks = queue_data.get('tasks', {})

            queued_count = sum(1 for t in tasks.values() if t.get('status') == 'queued')
            in_progress_count = sum(1 for t in tasks.values() if t.get('status') == 'in_progress')

            print(f"   ℹ️  Queue: {queued_count} queued, {in_progress_count} in progress")

            if queued_count > 10:
                print(f"   {YELLOW}⚠️  Large queue backlog: {queued_count} tasks{RESET}")
                issues.append(f"Queue backlog: {queued_count} tasks")
        except Exception as e:
            issues.append(f"Cannot check queue: {str(e)}")

        return issues

    def check_dependencies(self):
        """Check Python packages and external dependencies"""
        print(f"\n{BOLD}DEPENDENCIES:{RESET}")
        issues = []

        # Check Python packages
        required_packages = ['requests', 'anthropic']

        packages_ok = True
        for package in required_packages:
            try:
                spec = importlib.util.find_spec(package)
                if spec is None:
                    print(f"   {RED}❌ Python package missing: {package}{RESET}")
                    issues.append(f"Missing package: {package}")
                    packages_ok = False
            except Exception as e:
                print(f"   {RED}❌ Error checking {package}: {str(e)}{RESET}")
                issues.append(f"Package check error: {package}")
                packages_ok = False

        if packages_ok:
            print(f"   ✅ All required Python packages installed")

        # Check network connectivity
        try:
            result = subprocess.run(['ping', '-c', '1', '8.8.8.8'],
                                  capture_output=True, timeout=5)
            if result.returncode == 0:
                print(f"   ✅ Network connectivity OK")
            else:
                print(f"   {RED}❌ No network connectivity{RESET}")
                issues.append("No network connectivity")
        except subprocess.TimeoutExpired:
            print(f"   {YELLOW}⚠️  Network check timeout{RESET}")
            issues.append("Network check timeout")
        except Exception as e:
            print(f"   {YELLOW}⚠️  Network check error: {str(e)}{RESET}")

        return issues

    def run(self):
        """Run all diagnostic checks"""
        print(f"\n{BOLD}🔍 ORCHESTRATE SYSTEM DIAGNOSTIC{RESET}")
        print("=" * 50)

        # Run all checks
        process_issues = self.check_processes()
        filesystem_issues = self.check_filesystem()
        config_issues = self.check_configuration()
        operations_issues = self.check_operations()
        dependency_issues = self.check_dependencies()

        # Categorize issues
        all_issues = (process_issues + filesystem_issues + config_issues +
                     operations_issues + dependency_issues)

        # Classify as critical or warning
        critical_keywords = ['missing', 'corrupt', 'not running', 'failed', 'error']
        for issue in all_issues:
            is_critical = any(keyword in issue.lower() for keyword in critical_keywords)
            if is_critical:
                self.issues_critical.append(issue)
            else:
                self.issues_warning.append(issue)

        # Print summary
        print("\n" + "=" * 50)

        if self.issues_critical:
            print(f"\n{RED}{BOLD}CRITICAL FIXES REQUIRED:{RESET}")
            for i, issue in enumerate(self.issues_critical, 1):
                print(f"{i}. {issue}")

        if self.issues_warning:
            print(f"\n{YELLOW}{BOLD}WARNINGS TO ADDRESS:{RESET}")
            for i, issue in enumerate(self.issues_warning, 1):
                print(f"{i}. {issue}")

        if not self.issues_critical and not self.issues_warning:
            print(f"\n{GREEN}{BOLD}✅ ALL SYSTEMS HEALTHY{RESET}")

        print()

        # Return exit code
        return 1 if self.issues_critical else 0

def main():
    diagnostic = SystemDiagnostic()
    exit_code = diagnostic.run()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
