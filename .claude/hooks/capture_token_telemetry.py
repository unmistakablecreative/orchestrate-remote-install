#!/usr/bin/env python3
"""
Token Telemetry Capture Hook
Captures token usage from Claude Code transcript when log_task_completion is called.
Writes to data/last_execution_telemetry.json for merge into task results.
"""

import json
import os
import sys

def get_token_usage_from_transcript(transcript_path):
    """Extract total token usage from transcript JSONL file."""
    if not os.path.exists(transcript_path):
        return None

    total_input = 0
    total_output = 0
    total_cache_read = 0
    total_cache_creation = 0

    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    message = entry.get("message", {})
                    usage = message.get("usage", {})

                    if usage:
                        total_input += usage.get("input_tokens", 0)
                        total_output += usage.get("output_tokens", 0)
                        total_cache_read += usage.get("cache_read_input_tokens", 0)
                        total_cache_creation += usage.get("cache_creation_input_tokens", 0)
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Error reading transcript: {e}", file=sys.stderr)
        return None

    return {
        "tokens_input": total_input + total_cache_read + total_cache_creation,
        "tokens_output": total_output,
        "tokens_cache_read": total_cache_read,
        "tokens_cache_creation": total_cache_creation,
        "tokens_raw_input": total_input
    }

def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    # Only trigger on Bash tool calls
    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    # Check if this is a log_task_completion call
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    if "log_task_completion" not in command:
        sys.exit(0)

    # Get transcript path
    transcript_path = input_data.get("transcript_path", "")
    if not transcript_path:
        sys.exit(0)

    # Extract token usage
    usage = get_token_usage_from_transcript(transcript_path)
    if not usage:
        sys.exit(0)

    # Get project directory
    cwd = input_data.get("cwd", os.getcwd())
    telemetry_file = os.path.join(cwd, "data", "last_execution_telemetry.json")

    # Write telemetry file
    try:
        os.makedirs(os.path.dirname(telemetry_file), exist_ok=True)
        with open(telemetry_file, 'w', encoding='utf-8') as f:
            json.dump(usage, f, indent=2)
        print(f"Token telemetry captured: {usage['tokens_input']} input, {usage['tokens_output']} output", file=sys.stderr)
    except Exception as e:
        print(f"Error writing telemetry: {e}", file=sys.stderr)

    sys.exit(0)

if __name__ == "__main__":
    main()
