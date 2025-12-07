#!/usr/bin/env python3
"""
Autonomous Install Test - Pre-Auth Phase

Tests that run BEFORE user authenticates Claude Code.
Validates Docker container setup and basic API functionality.

Tests:
- json_manager basic CRUD operations
- outline_editor API connectivity
- ledger_manager credit management
- Verify claude_assistant.py is unlocked in ledger

Usage:
    python3 tools/autonomous_install_test_pre_auth.py
"""

import sys
import json
import subprocess
import time
from typing import Dict, Any, List, Tuple

# Test data
TEST_LEDGER_USER = "test_pre_auth_install"
TEST_JSON_FILE = "test_pre_auth_data.json"
TEST_JSON_ENTRY = "test_entry_pre_auth"

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

def test_json_manager_operations() -> bool:
    """
    Test json_manager basic CRUD operations

    Tests:
    1. Create test JSON file
    2. Add entry to file
    3. Read entry from file
    4. Delete entry from file
    5. Clean up test file
    """
    print_header("TEST: json_manager CRUD Operations")

    all_passed = True

    # Test 1: Create JSON file
    print_info(f"Creating test file: {TEST_JSON_FILE}")
    success, result = run_execution_hub_task(
        "json_manager",
        "create_json_file",
        {"filename": TEST_JSON_FILE}
    )
    if success:
        print_success("JSON file created")
    else:
        print_error(f"Failed to create JSON file: {result.get('message', 'Unknown error')}")
        all_passed = False
        return all_passed

    # Test 2: Add entry
    print_info(f"Adding test entry: {TEST_JSON_ENTRY}")
    success, result = run_execution_hub_task(
        "json_manager",
        "add_json_entry",
        {
            "filename": TEST_JSON_FILE,
            "entry_key": TEST_JSON_ENTRY,
            "test_field": "test_value",
            "test_number": 42
        }
    )
    if success:
        print_success("Entry added successfully")
    else:
        print_error(f"Failed to add entry: {result.get('message', 'Unknown error')}")
        all_passed = False

    # Test 3: Read entry
    print_info(f"Reading entry: {TEST_JSON_ENTRY}")
    success, result = run_execution_hub_task(
        "json_manager",
        "read_json_entry",
        {
            "filename": TEST_JSON_FILE,
            "entry_key": TEST_JSON_ENTRY
        }
    )
    if success and result.get("entry"):
        entry = result["entry"]
        if entry.get("test_field") == "test_value" and entry.get("test_number") == 42:
            print_success("Entry read correctly")
        else:
            print_error(f"Entry data mismatch: {entry}")
            all_passed = False
    else:
        print_error(f"Failed to read entry: {result.get('message', 'Unknown error')}")
        all_passed = False

    # Test 4: Delete entry
    print_info(f"Deleting entry: {TEST_JSON_ENTRY}")
    success, result = run_execution_hub_task(
        "json_manager",
        "delete_json_entry",
        {
            "filename": TEST_JSON_FILE,
            "entry_key": TEST_JSON_ENTRY
        }
    )
    if success:
        print_success("Entry deleted successfully")
    else:
        print_error(f"Failed to delete entry: {result.get('message', 'Unknown error')}")
        all_passed = False

    # Clean up: Remove test file
    print_info("Cleaning up test file")
    try:
        subprocess.run(["rm", f"data/{TEST_JSON_FILE}"], check=True, capture_output=True)
        print_success("Test file cleaned up")
    except:
        print_error("Failed to clean up test file (non-critical)")

    return all_passed

def test_outline_editor_api() -> bool:
    """
    Test outline_editor API connectivity

    Tests:
    1. Search for docs (verifies API auth works)
    2. Check response structure
    """
    print_header("TEST: outline_editor API Connectivity")

    all_passed = True

    # Test: Search docs
    print_info("Searching Outline docs with query: 'test'")
    success, result = run_execution_hub_task(
        "outline_editor",
        "search_docs",
        {
            "query": "test",
            "limit": 5
        }
    )
    if success:
        # Check if we got valid response structure
        if "data" in result or "documents" in result or isinstance(result.get("results"), list):
            print_success("Outline API connected successfully")
        else:
            print_error(f"Unexpected response structure: {result}")
            all_passed = False
    else:
        print_error(f"Failed to connect to Outline API: {result.get('message', 'Unknown error')}")
        all_passed = False

    return all_passed

def test_ledger_manager_operations() -> bool:
    """
    Test ledger_manager credit management

    Tests:
    1. List ledger entries (verifies JSONBin connectivity)
    2. Check for test user entry
    """
    print_header("TEST: ledger_manager Credit Management")

    all_passed = True

    # Test: List ledger entries
    print_info("Listing ledger entries")
    success, result = run_execution_hub_task(
        "ledger_manager",
        "list_ledger_entries",
        {}
    )
    if success:
        entries = result.get("entries", [])
        total_count = result.get("total_count", 0)
        print_success(f"Ledger accessed successfully ({total_count} total entries)")
    else:
        print_error(f"Failed to access ledger: {result.get('message', 'Unknown error')}")
        all_passed = False

    return all_passed

def test_claude_assistant_unlocked() -> bool:
    """
    Verify claude_assistant.py is unlocked in ledger

    Checks that the system has claude_assistant in tools_unlocked
    """
    print_header("TEST: claude_assistant.py Unlocked Status")

    all_passed = True

    # Get system identity to find user_id
    print_info("Reading system identity")
    try:
        with open("data/system_identity.json", "r") as f:
            identity = json.load(f)
            user_id = identity.get("user_id")

        if not user_id:
            print_error("No user_id found in system_identity.json")
            return False

        print_info(f"System user_id: {user_id}")
    except Exception as e:
        print_error(f"Failed to read system_identity.json: {str(e)}")
        return False

    # Check ledger for this user
    print_info("Checking ledger for claude_assistant unlock")
    success, result = run_execution_hub_task(
        "ledger_manager",
        "list_ledger_entries",
        {"user_id": user_id}
    )

    if success:
        entries = result.get("entries", [])
        if entries:
            user_entry = entries[0]
            tools_unlocked = user_entry.get("tools_unlocked", [])

            if "claude_assistant" in tools_unlocked:
                print_success("claude_assistant.py is unlocked ✓")
            else:
                print_error(f"claude_assistant.py NOT unlocked. Tools: {tools_unlocked}")
                all_passed = False
        else:
            print_error(f"User {user_id} not found in ledger")
            all_passed = False
    else:
        print_error(f"Failed to check ledger: {result.get('message', 'Unknown error')}")
        all_passed = False

    return all_passed

def run_all_tests() -> int:
    """
    Run all pre-auth tests and return exit code

    Returns:
        0 if all tests passed, 1 if any failed
    """
    print_header("AUTONOMOUS INSTALL TEST - PRE-AUTH PHASE")
    print(f"Running tests that don't require Claude Code authentication\n")

    test_results = []

    # Run each test
    test_results.append(("json_manager CRUD", test_json_manager_operations()))
    test_results.append(("outline_editor API", test_outline_editor_api()))
    test_results.append(("ledger_manager", test_ledger_manager_operations()))
    test_results.append(("claude_assistant unlocked", test_claude_assistant_unlocked()))

    # Print summary
    print_header("TEST SUMMARY")

    passed_count = sum(1 for _, passed in test_results if passed)
    total_count = len(test_results)

    for test_name, passed in test_results:
        status = f"{Colors.GREEN}PASS{Colors.RESET}" if passed else f"{Colors.RED}FAIL{Colors.RESET}"
        print(f"{test_name}: {status}")

    print(f"\n{passed_count}/{total_count} tests passed\n")

    if passed_count == total_count:
        print_success("All pre-auth tests passed! ✓")
        print_info("Next step: User must authenticate Claude Code in container")
        print_info("After auth, run: python3 tools/autonomous_install_test_post_auth.py")
        return 0
    else:
        print_error(f"{total_count - passed_count} test(s) failed")
        return 1

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
