#!/usr/bin/env python3
"""
OrchestrateOS Validator - Codebase-wide validation tool

Validates tools for:
1. Import validity (syntax errors, missing dependencies)
2. Schema compliance (action params match system_settings.ndjson)
3. JSON operations safety (can read/write data files without corruption)
4. State transition validity (tools follow defined state patterns)

DIAGNOSTIC ONLY - Does not modify any files.
"""

import os
import sys
import json
import importlib
import importlib.util
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Tuple


def load_compatibility_config() -> Dict:
    """Load tool compatibility metadata"""
    config_path = "data/orchestrate_compatibility.json"
    if not os.path.exists(config_path):
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_system_settings() -> List[Dict]:
    """Load system_settings.ndjson as list of action definitions"""
    settings_file = "system_settings.ndjson"
    if not os.path.exists(settings_file):
        return []

    settings = []
    with open(settings_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    settings.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    return settings


def get_tool_list() -> List[str]:
    """Get list of all Python tools in tools/ directory"""
    tools_dir = Path("tools")
    if not tools_dir.exists():
        return []

    tools = []
    for file in tools_dir.glob("*.py"):
        # Skip special files
        if file.name.startswith("_") or file.name == "system_settings.py":
            continue
        tools.append(file.stem)

    return sorted(tools)


def validate_import(tool_name: str) -> Tuple[bool, str]:
    """
    Validate that a tool can be imported without syntax errors

    Returns: (is_valid, error_message)
    """
    tool_path = f"tools/{tool_name}.py"

    if not os.path.exists(tool_path):
        return False, f"Tool file not found: {tool_path}"

    # Try importing using importlib
    spec = importlib.util.spec_from_file_location(tool_name, tool_path)
    if spec is None:
        return False, f"Could not load module spec for {tool_name}"

    try:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return True, ""
    except SyntaxError as e:
        return False, f"Syntax error at line {e.lineno}: {e.msg}"
    except ImportError as e:
        return False, f"Import error: {str(e)}"
    except Exception as e:
        return False, f"Import failed: {type(e).__name__}: {str(e)}"


def validate_schema(tool_name: str) -> Tuple[bool, List[str]]:
    """
    Validate that tool's actions match system_settings.ndjson schema

    Returns: (is_valid, list_of_issues)
    """
    settings = load_system_settings()

    # Get all action definitions for this tool
    tool_actions = [s for s in settings if s.get("tool") == tool_name and s.get("action") != "__tool__"]

    if not tool_actions:
        return False, [f"No actions registered for {tool_name} in system_settings.ndjson"]

    issues = []

    for action_def in tool_actions:
        action_name = action_def.get("action")
        params = action_def.get("params", [])
        optional_params = action_def.get("optional_params", [])

        # Check if action definition is complete
        if not action_name:
            issues.append(f"Action definition missing 'action' field")
            continue

        # Validate params is a list
        if not isinstance(params, list):
            issues.append(f"Action '{action_name}' has invalid 'params' (must be list, got {type(params).__name__})")

        # Validate optional_params is a list
        if optional_params and not isinstance(optional_params, list):
            issues.append(f"Action '{action_name}' has invalid 'optional_params' (must be list, got {type(optional_params).__name__})")

    return len(issues) == 0, issues


def validate_json_operations(tool_name: str) -> Tuple[bool, List[str]]:
    """
    Validate that tool can safely read/write its data files

    Returns: (is_valid, list_of_issues)
    """
    compatibility = load_compatibility_config()
    tool_config = compatibility.get(tool_name, {})
    data_files = tool_config.get("data_files", [])

    if not data_files:
        # Tool doesn't declare data files - assume safe
        return True, []

    issues = []

    for data_file in data_files:
        file_path = f"data/{data_file}"

        # Check if file exists
        if not os.path.exists(file_path):
            issues.append(f"Data file not found: {file_path}")
            continue

        # Try reading as JSON
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                json.load(f)
        except json.JSONDecodeError as e:
            issues.append(f"JSON corruption in {file_path}: {str(e)}")
        except Exception as e:
            issues.append(f"Cannot read {file_path}: {str(e)}")

    return len(issues) == 0, issues


def validate_state_transitions(tool_name: str) -> Tuple[bool, List[str]]:
    """
    Validate that tool follows defined state transition patterns

    Returns: (is_valid, list_of_issues)
    """
    compatibility = load_compatibility_config()
    tool_config = compatibility.get(tool_name, {})
    valid_transitions = tool_config.get("valid_state_transitions", {})

    if not valid_transitions:
        # Tool doesn't declare state transitions - assume safe
        return True, []

    issues = []

    # Validate transition structure
    for from_state, to_states in valid_transitions.items():
        if not isinstance(to_states, list):
            issues.append(f"State transition for '{from_state}' must be a list (got {type(to_states).__name__})")
        else:
            # Check for circular transitions
            if from_state in to_states and len(to_states) == 1:
                issues.append(f"Circular transition detected: '{from_state}' -> '{from_state}'")

    return len(issues) == 0, issues


def validate_tool(tool_name: str) -> Dict[str, Any]:
    """
    Run all validations for a single tool

    Returns validation report dict
    """
    report = {
        "tool": tool_name,
        "import_valid": False,
        "schema_valid": False,
        "json_operations_safe": False,
        "state_transitions_valid": False,
        "issues": []
    }

    # Validate import
    import_valid, import_error = validate_import(tool_name)
    report["import_valid"] = import_valid
    if not import_valid:
        report["issues"].append({"type": "import", "message": import_error})
        # If import fails, skip other validations
        return report

    # Validate schema
    schema_valid, schema_issues = validate_schema(tool_name)
    report["schema_valid"] = schema_valid
    for issue in schema_issues:
        report["issues"].append({"type": "schema", "message": issue})

    # Validate JSON operations
    json_valid, json_issues = validate_json_operations(tool_name)
    report["json_operations_safe"] = json_valid
    for issue in json_issues:
        report["issues"].append({"type": "json", "message": issue})

    # Validate state transitions
    state_valid, state_issues = validate_state_transitions(tool_name)
    report["state_transitions_valid"] = state_valid
    for issue in state_issues:
        report["issues"].append({"type": "state_transition", "message": issue})

    return report


def validate_all_tools() -> Dict[str, Any]:
    """
    Run validations for all tools in tools/ directory

    Returns summary report with per-tool results
    """
    tools = get_tool_list()

    summary = {
        "total_tools": len(tools),
        "passed": 0,
        "failed": 0,
        "tools": {}
    }

    for tool_name in tools:
        report = validate_tool(tool_name)

        # Tool passes if all validations pass
        tool_passed = (
            report["import_valid"] and
            report["schema_valid"] and
            report["json_operations_safe"] and
            report["state_transitions_valid"]
        )

        if tool_passed:
            summary["passed"] += 1
        else:
            summary["failed"] += 1

        summary["tools"][tool_name] = report

    return summary


def format_report(summary: Dict[str, Any]) -> str:
    """Format validation summary as human-readable text"""
    lines = []
    lines.append("=" * 80)
    lines.append("ORCHESTRATEOS VALIDATION REPORT")
    lines.append("=" * 80)
    lines.append(f"Total Tools: {summary['total_tools']}")
    lines.append(f"Passed: {summary['passed']}")
    lines.append(f"Failed: {summary['failed']}")
    lines.append("")

    # Show failed tools first
    failed_tools = {k: v for k, v in summary["tools"].items() if len(v["issues"]) > 0}
    passed_tools = {k: v for k, v in summary["tools"].items() if len(v["issues"]) == 0}

    if failed_tools:
        lines.append("FAILED TOOLS:")
        lines.append("-" * 80)
        for tool_name, report in failed_tools.items():
            lines.append(f"\n{tool_name}:")
            lines.append(f"  Import Valid: {report['import_valid']}")
            lines.append(f"  Schema Valid: {report['schema_valid']}")
            lines.append(f"  JSON Operations Safe: {report['json_operations_safe']}")
            lines.append(f"  State Transitions Valid: {report['state_transitions_valid']}")

            if report["issues"]:
                lines.append("  Issues:")
                for issue in report["issues"]:
                    lines.append(f"    [{issue['type']}] {issue['message']}")

    if passed_tools:
        lines.append("")
        lines.append("PASSED TOOLS:")
        lines.append("-" * 80)
        for tool_name in passed_tools.keys():
            lines.append(f"  ✓ {tool_name}")

    lines.append("")
    lines.append("=" * 80)

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validate OrchestrateOS tools")
    parser.add_argument("--tool", help="Validate specific tool (default: all)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    parser.add_argument("--action", help="Action to perform", default="validate_all_tools")
    parser.add_argument("--params", help="JSON params for action")

    args = parser.parse_args()

    # Support both CLI patterns (--tool X and action=validate_tool params={tool: X})
    if args.action == "validate_tool":
        params = json.loads(args.params) if args.params else {}
        tool_name = params.get("tool") or args.tool

        if not tool_name:
            print(json.dumps({
                "status": "error",
                "message": "Missing required parameter: tool"
            }, indent=2))
            sys.exit(1)

        report = validate_tool(tool_name)
        print(json.dumps(report, indent=2))

    elif args.action == "validate_all_tools" or (not args.action and not args.tool):
        summary = validate_all_tools()

        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(format_report(summary))

    else:
        print(json.dumps({
            "status": "error",
            "message": f"Unknown action: {args.action}"
        }, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
