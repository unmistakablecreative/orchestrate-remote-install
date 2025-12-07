#!/usr/bin/env python3
"""
JSON File Protection - Validates that critical JSON files are only modified via json_manager

This script acts as a gate-keeper. Add it to Claude's prompt to prevent direct Write/Edit on JSON files.
"""

PROTECTED_FILES = [
    "data/outline_queue.json",
    "data/claude_task_queue.json",
    "data/claude_task_results.json",
    "data/automation_state.json",
    "data/execution_log.json",
    "data/outline_reference.json",
    "data/youtube_published.json",
    "data/youtube_publish_queue.json",
    "data/podcast_index.json",
    "data/working_memory.json"
]

def is_protected(file_path):
    """Check if a file path is a protected JSON file"""
    # Normalize path
    normalized = file_path.replace(os.path.expanduser("~/Orchestrate Github/orchestrate-jarvis/"), '')

    return normalized in PROTECTED_FILES

def validate_operation(tool_name, file_path):
    """
    Validate that Write/Edit operations don't target protected JSON files

    Returns: (allowed: bool, error_message: str)
    """
    if tool_name not in ['Write', 'Edit']:
        return True, None

    if not file_path:
        return True, None

    if not file_path.endswith('.json'):
        return True, None

    if is_protected(file_path):
        return False, f"""
❌ BLOCKED: Cannot use {tool_name} tool on protected JSON file: {file_path}

CRITICAL JSON files MUST be modified using json_manager tool, NOT Write/Edit.

Protected files:
{chr(10).join(f'  - {f}' for f in PROTECTED_FILES)}

Use json_manager instead:
  - add_json_entry (add new entry)
  - update_json_entry (update existing entry)
  - delete_json_entry (remove entry)
  - read_json_file (read entire file)

This protection prevents JSON structure corruption and race conditions.
"""

    return True, None

if __name__ == "__main__":
    # Test the protection
    test_cases = [
        ("Write", "data/outline_queue.json"),
        ("Edit", "data/claude_task_queue.json"),
        ("Write", "some_other_file.txt"),
        ("Read", "data/outline_queue.json")
    ]

    for tool, path in test_cases:
        allowed, msg = validate_operation(tool, path)
        status = "✅ ALLOWED" if allowed else "❌ BLOCKED"
        print(f"{status}: {tool} on {path}")
        if msg:
            print(msg)
