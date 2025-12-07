#!/usr/bin/env python3
"""
Execution Hub - Clean Sequential Execution
No locks, no retries, no defensive bullshit. Just execute.
"""

import os
import json
import subprocess
import argparse
import logging
import time
from datetime import datetime
from pathlib import Path

NDJSON_REGISTRY_FILE = "system_settings.ndjson"
EXECUTION_LOG = "data/execution_log.json"
THREAD_STATE_FILE = "data/thread_state.json"
MAX_TOKEN_BUDGET = 100000
DEFAULT_TIMEOUT = 200

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


# ============================================================================
# SIMPLE JSON HELPERS
# ============================================================================

def read_json(filepath, default=None):
    """Read JSON file, return default if missing/corrupt"""
    if not os.path.exists(filepath):
        return default if default is not None else {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return default if default is not None else {}


def write_json(filepath, data):
    """Write JSON file"""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


# ============================================================================
# THREAD STATE (minimal)
# ============================================================================

def read_thread_state():
    state = read_json(THREAD_STATE_FILE, default={
        "score": 100,
        "tokens_used": 0,
        "execution_count": 0,
        "thread_started_at": time.strftime("%Y-%m-%dT%H:%M:%S")
    })
    # Auto-reset if thread_started_at is >24 hours old
    try:
        started_at = state.get("thread_started_at", "")
        if started_at:
            started = datetime.fromisoformat(started_at.replace('Z', ''))
            age_hours = (datetime.now() - started).total_seconds() / 3600
            if age_hours > 24:
                logging.info(f"Thread state stale ({age_hours:.1f}h old), resetting")
                state = reset_thread_state()
    except Exception:
        pass
    return state


def update_state(score_change=0, token_cost=0):
    state = read_thread_state()
    state["score"] = max(0, min(150, state.get("score", 100) + score_change))
    state["tokens_used"] = state.get("tokens_used", 0) + token_cost
    state["execution_count"] = state.get("execution_count", 0) + 1
    write_json(THREAD_STATE_FILE, state)
    return state


def reset_thread_state():
    state = {
        "score": 100,
        "tokens_used": 0,
        "execution_count": 0,
        "thread_started_at": time.strftime("%Y-%m-%dT%H:%M:%S")
    }
    write_json(THREAD_STATE_FILE, state)
    return state


def attach_telemetry(response, state):
    if not isinstance(response, dict):
        response = {"result": response}
    response["thread_score"] = state.get("score", 100)
    response["tokens_used"] = state.get("tokens_used", 0)
    response["tokens_remaining"] = MAX_TOKEN_BUDGET - state.get("tokens_used", 0)
    response["token_budget"] = MAX_TOKEN_BUDGET
    return response


# ============================================================================
# LOG ROTATION
# ============================================================================

def rotate_logs():
    """Rotate debug logs that grow unbounded. Called periodically."""
    import shutil

    logs_to_rotate = [
        ("data/hook_debug.log", 500 * 1024),  # 500KB max
        ("data/claude_execution.log", 500 * 1024),  # 500KB max
    ]

    archive_dir = Path("data/log_archive")
    archive_dir.mkdir(parents=True, exist_ok=True)

    for log_path, max_size in logs_to_rotate:
        log_file = Path(log_path)
        if log_file.exists():
            try:
                size = log_file.stat().st_size
                if size > max_size:
                    # Archive with timestamp
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    archive_name = f"{log_file.stem}_{timestamp}{log_file.suffix}"
                    archive_path = archive_dir / archive_name
                    shutil.move(str(log_file), str(archive_path))
                    logging.info(f"Rotated {log_path} ({size/1024:.1f}KB) to {archive_path}")

                    # Keep only last 5 archives per log type
                    pattern = f"{log_file.stem}_*{log_file.suffix}"
                    archives = sorted(archive_dir.glob(pattern), reverse=True)
                    for old_archive in archives[5:]:
                        old_archive.unlink()
                        logging.info(f"Deleted old archive: {old_archive}")
            except Exception as e:
                logging.warning(f"Failed to rotate {log_path}: {e}")


# ============================================================================
# EXECUTION LOGGING
# ============================================================================

def log_execution(tool, action, params, status, result):
    try:
        os.makedirs("data", exist_ok=True)

        # Rotate logs periodically (every 10th execution)
        state = read_json(THREAD_STATE_FILE, default={})
        if state.get("execution_count", 0) % 10 == 0:
            rotate_logs()

        log = read_json(EXECUTION_LOG, default={"executions": []})
        # Fix: Ensure log has correct structure (file may contain just [])
        if isinstance(log, list):
            log = {"executions": log}
        if "executions" not in log:
            log["executions"] = []
        log["executions"].append({
            "tool": tool,
            "action": action,
            "params": params,
            "status": status,
            "output": result,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
        })
        # Keep only last 100 entries to prevent unbounded growth
        if len(log["executions"]) > 100:
            log["executions"] = log["executions"][-100:]
        write_json(EXECUTION_LOG, log)
    except Exception as e:
        logging.warning(f"Failed to log execution: {e}")


# ============================================================================
# REGISTRY
# ============================================================================

def load_registry():
    if not os.path.exists(NDJSON_REGISTRY_FILE):
        return {}

    tools = {}
    with open(NDJSON_REGISTRY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                tool = entry["tool"]
                action = entry["action"]

                if tool not in tools:
                    tools[tool] = {"path": None, "actions": {}, "locked": False}

                if action == "__tool__":
                    tools[tool]["path"] = entry["script_path"]
                    tools[tool]["locked"] = entry.get("locked", False)
                else:
                    tools[tool]["actions"][action] = {
                        "params": entry.get("params", []),
                        "timeout_seconds": entry.get("timeout_seconds", DEFAULT_TIMEOUT)
                    }
            except:
                pass
    return tools


# ============================================================================
# CORE EXECUTION
# ============================================================================

def execute_tool(tool_name, action, params):
    """Execute tool via subprocess. Simple."""
    registry = load_registry()
    state = read_thread_state()

    # Validate tool exists
    if tool_name not in registry:
        state = update_state(-10)
        result = {"status": "error", "message": f"Tool '{tool_name}' not found"}
        log_execution(tool_name, action, params, "error", result)
        return attach_telemetry(result, state)

    tool_info = registry[tool_name]
    script_path = tool_info.get("path")

    if not script_path or not os.path.isfile(script_path):
        state = update_state(-10)
        result = {"status": "error", "message": f"Script not found: {script_path}"}
        log_execution(tool_name, action, params, "error", result)
        return attach_telemetry(result, state)

    if action not in tool_info["actions"]:
        state = update_state(-10)
        result = {"status": "error", "message": f"Action '{action}' not found", "available": list(tool_info["actions"].keys())}
        log_execution(tool_name, action, params, "error", result)
        return attach_telemetry(result, state)

    # Get timeout
    timeout = tool_info["actions"][action].get("timeout_seconds", DEFAULT_TIMEOUT)

    # Special: execute_queue runs async
    if tool_name == "claude_assistant" and action == "execute_queue":
        reset_thread_state()
        try:
            process = subprocess.Popen(
                ["python3", script_path, action, "--params", json.dumps(params)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            result = {"status": "started", "message": "Queue execution started", "pid": process.pid}
            log_execution(tool_name, action, params, "started", result)
            return attach_telemetry(result, read_thread_state())
        except Exception as e:
            result = {"status": "error", "message": str(e)}
            log_execution(tool_name, action, params, "error", result)
            return attach_telemetry(result, read_thread_state())

    # Execute subprocess
    try:
        cmd = ["python3", script_path, action, "--params", json.dumps(params)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        output = proc.stdout.strip()
        try:
            parsed = json.loads(output)
        except:
            parsed = {"raw_output": output, "stderr": proc.stderr}

        state = update_state(+5)
        log_execution(tool_name, action, params, "success", parsed)
        return attach_telemetry(parsed, state)

    except subprocess.TimeoutExpired:
        state = update_state(-20)
        result = {"status": "error", "message": f"Timeout after {timeout}s"}
        log_execution(tool_name, action, params, "timeout", result)
        return attach_telemetry(result, state)

    except Exception as e:
        state = update_state(-20)
        result = {"status": "error", "message": str(e)}
        log_execution(tool_name, action, params, "error", result)
        return attach_telemetry(result, state)


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action")
    parser.add_argument("--params", type=str)
    args = parser.parse_args()

    if args.action == "load_orchestrate_os":
        state = reset_thread_state()
        result = {"status": "ready", "message": "OrchestrateOS loaded"}
        print(json.dumps(attach_telemetry(result, state), indent=4))
        return

    if args.action == "execute_task":
        try:
            p = json.loads(args.params or "{}")
            tool = p.get("tool_name")
            act = p.get("action")
            prms = p.get("params", {})

            if not tool or not act:
                raise ValueError("Missing tool_name or action")

            result = execute_tool(tool, act, prms)
            print(json.dumps(result, indent=4))

        except Exception as e:
            result = {"status": "error", "message": str(e)}
            print(json.dumps(attach_telemetry(result, read_thread_state()), indent=4))
    else:
        result = {"status": "error", "message": "Invalid action"}
        print(json.dumps(attach_telemetry(result, read_thread_state()), indent=4))


if __name__ == "__main__":
    main()
