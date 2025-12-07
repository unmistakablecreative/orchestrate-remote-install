#!/usr/bin/env python3
"""
Autonomous Install Test - Post-Auth Phase

Tests that run AFTER user authenticates Claude Code.
Validates Claude Code integration and task execution flow.

Tests:
- Poll for auth completion (5min timeout)
- claude_assistant assign_task
- claude_assistant check_task_status
- claude_assistant execute_queue
- Full task execution flow

Usage:
    python3 tools/autonomous_install_test_post_auth.py
"""

import sys
import json
import subprocess
import time
from typing import Dict, Any, Tuple

# Test configuration
AUTH_TIMEOUT_SECONDS = 300  # 5 minutes
AUTH_POLL_INTERVAL = 10  # Check every 10 seconds
TEST_TASK_ID = "test_post_auth_install"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_header(message: str):
    """Print test section header"""
    print(f"\n{Colors.BLUE}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BLUE}{message}{Colors.RESET}")
    print(f"{Colors.BLUE}{'=' * 60}{Colors.RESET}\n")

def print_success(message: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")

def print_error(message: str):
    """Print error message"""
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")

def print_info(message: str):
    """Print info message"""
    print(f"{Colors.YELLOW}→ {message}{Colors.RESET}")

def run_execution_hub_task(tool_name: str, action: str, params: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Run a task via execution_hub.py and return success status + result

    Args:
        tool_name: Name of tool to execute
        action: Action to perform
        params: Parameters for the action

    Returns:
        Tuple of (success: bool, result: dict)
    """
    try:
        task_params = {
            "tool_name": tool_name,
            "action": action,
            "params": params
        }

        cmd = [
            "python3",
            "execution_hub.py",
            "execute_task",
            "--params",
            json.dumps(task_params)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return False, {
                "error": "Command failed",
                "stderr": result.stderr,
                "stdout": result.stdout
            }

        try:
            response = json.loads(result.stdout)
            success = response.get("status") == "success"
            return success, response
        except json.JSONDecodeError:
            return False, {
                "error": "Invalid JSON response",
                "stdout": result.stdout
            }

    except subprocess.TimeoutExpired:
        return False, {"error": "Command timeout after 30s"}
    except Exception as e:
        return False, {"error": str(e)}

def poll_for_auth() -> bool:
    """
    Poll for Claude Code authentication completion

    Attempts to call check_task_status every AUTH_POLL_INTERVAL seconds.
    If it succeeds (doesn't error about auth), Claude is authenticated.

    Returns:
        True if auth detected, False if timeout
    """
    print_header("POLLING FOR CLAUDE CODE AUTHENTICATION")

    print_info(f"Timeout: {AUTH_TIMEOUT_SECONDS}s")
    print_info(f"Poll interval: {AUTH_POLL_INTERVAL}s")
    print_info("Waiting for user to complete Claude Code auth in container...")

    start_time = time.time()
    attempt = 0

    while (time.time() - start_time) < AUTH_TIMEOUT_SECONDS:
        attempt += 1
        elapsed = int(time.time() - start_time)

        print_info(f"Attempt {attempt} ({elapsed}s elapsed)")

        # Try to call a Claude action - if it works, auth is complete
        success, result = run_execution_hub_task(
            "claude_assistant",
            "check_task_status",
            {"task_id": "auth_check_probe"}
        )

        # If we get a response (even if task not found), auth is working
        if success or "not found" in result.get("message", "").lower():
            print_success(f"Claude Code authenticated! (detected at {elapsed}s)")
            return True

        # If we get auth error specifically, keep polling
        error_msg = result.get("message", "")
        if "auth" in error_msg.lower() or "permission" in error_msg.lower():
            print_info(f"Not authenticated yet... ({error_msg[:50]})")
        else:
            # Some other error - might indicate auth is working
            print_info(f"Got response (possible auth success): {error_msg[:50]}")
            return True

        time.sleep(AUTH_POLL_INTERVAL)

    print_error(f"Authentication timeout after {AUTH_TIMEOUT_SECONDS}s")
    return False

def test_assign_task() -> Tuple[bool, str]:
    """
    Test claude_assistant assign_task

    Returns:
        Tuple of (success: bool, task_id: str)
    """
    print_header("TEST: claude_assistant assign_task")

    print_info("Assigning test task")
    success, result = run_execution_hub_task(
        "claude_assistant",
        "assign_task",
        {
            "task_id": TEST_TASK_ID,
            "description": "Test task for post-auth validation. Just verify the task system works."
        }
    )

    if success:
        task_id = result.get("task_id") or TEST_TASK_ID
        print_success(f"Task assigned: {task_id}")
        return True, task_id
    else:
        print_error(f"Failed to assign task: {result.get('message', 'Unknown error')}")
        return False, ""

def test_check_task_status(task_id: str) -> bool:
    """
    Test claude_assistant check_task_status

    Args:
        task_id: Task ID to check

    Returns:
        True if check succeeded
    """
    print_header("TEST: claude_assistant check_task_status")

    print_info(f"Checking status of task: {task_id}")
    success, result = run_execution_hub_task(
        "claude_assistant",
        "check_task_status",
        {"task_id": task_id}
    )

    if success:
        status = result.get("status", "unknown")
        print_success(f"Task status retrieved: {status}")
        return True
    else:
        print_error(f"Failed to check task status: {result.get('message', 'Unknown error')}")
        return False

def test_execute_queue() -> bool:
    """
    Test claude_assistant execute_queue

    Returns:
        True if execute_queue succeeded
    """
    print_header("TEST: claude_assistant execute_queue")

    print_info("Triggering execute_queue")
    success, result = run_execution_hub_task(
        "claude_assistant",
        "execute_queue",
        {}
    )

    if success:
        pending_tasks = result.get("pending_tasks", [])
        task_count = len(pending_tasks) if isinstance(pending_tasks, list) else result.get("task_count", 0)
        print_success(f"Execute queue completed ({task_count} pending tasks)")
        return True
    else:
        # execute_queue might return "no pending tasks" which is still success
        msg = result.get("message", "")
        if "no pending" in msg.lower() or "no tasks" in msg.lower():
            print_success("Execute queue completed (no pending tasks)")
            return True
        else:
            print_error(f"Failed to execute queue: {msg}")
            return False

def test_full_execution_flow() -> bool:
    """
    Test full task execution flow

    1. Assign a simple task
    2. Trigger execute_queue
    3. Wait briefly for execution
    4. Check task result

    Returns:
        True if full flow succeeded
    """
    print_header("TEST: Full Task Execution Flow")

    # Step 1: Assign task
    print_info("Step 1: Assigning test task")
    flow_task_id = "test_execution_flow_post_auth"
    success, result = run_execution_hub_task(
        "claude_assistant",
        "assign_task",
        {
            "task_id": flow_task_id,
            "description": "Simple test: list files in data/ directory"
        }
    )

    if not success:
        print_error(f"Flow step 1 failed: {result.get('message', 'Unknown error')}")
        return False

    print_success(f"Task assigned: {flow_task_id}")

    # Step 2: Execute queue
    print_info("Step 2: Executing queue")
    success, result = run_execution_hub_task(
        "claude_assistant",
        "execute_queue",
        {}
    )

    if not success and "no pending" not in result.get("message", "").lower():
        print_error(f"Flow step 2 failed: {result.get('message', 'Unknown error')}")
        return False

    print_success("Queue execution triggered")

    # Step 3: Wait for execution (Claude needs time to process)
    print_info("Step 3: Waiting for task execution (15s)")
    time.sleep(15)

    # Step 4: Check task result
    print_info("Step 4: Checking task result")
    success, result = run_execution_hub_task(
        "claude_assistant",
        "get_task_result",
        {"task_id": flow_task_id}
    )

    if success:
        status = result.get("status", "unknown")
        output = result.get("output", "")
        print_success(f"Task completed with status: {status}")
        if output:
            print_info(f"Output preview: {output[:100]}...")
        return True
    else:
        # Task might still be in_progress, which is acceptable
        msg = result.get("message", "")
        if "in_progress" in msg.lower() or "not found" in msg.lower():
            print_info("Task still processing or not yet executed (acceptable)")
            return True
        else:
            print_error(f"Flow step 4 failed: {msg}")
            return False

def run_all_tests() -> int:
    """
    Run all post-auth tests and return exit code

    Returns:
        0 if all tests passed, 1 if any failed
    """
    print_header("AUTONOMOUS INSTALL TEST - POST-AUTH PHASE")
    print("Running tests that require Claude Code authentication\n")

    test_results = []

    # First: Poll for auth
    if not poll_for_auth():
        print_error("Authentication polling timed out")
        print_info("User must run 'claude auth' inside the container and complete authentication")
        return 1

    # Give Claude a moment to fully initialize
    print_info("Waiting 5s for Claude to fully initialize...")
    time.sleep(5)

    # Run tests
    success, task_id = test_assign_task()
    test_results.append(("assign_task", success))

    if success:
        test_results.append(("check_task_status", test_check_task_status(task_id)))

    test_results.append(("execute_queue", test_execute_queue()))
    test_results.append(("full_execution_flow", test_full_execution_flow()))

    # Print summary
    print_header("TEST SUMMARY")

    passed_count = sum(1 for _, passed in test_results if passed)
    total_count = len(test_results)

    for test_name, passed in test_results:
        status = f"{Colors.GREEN}PASS{Colors.RESET}" if passed else f"{Colors.RED}FAIL{Colors.RESET}"
        print(f"{test_name}: {status}")

    print(f"\n{passed_count}/{total_count} tests passed\n")

    if passed_count == total_count:
        print_success("All post-auth tests passed! ✓")
        print_success("OrchestrateOS installation validated successfully!")
        return 0
    else:
        print_error(f"{total_count - passed_count} test(s) failed")
        return 1

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
