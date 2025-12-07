#!/usr/bin/env python3
"""
Schema Injection Validator

Tests that inject_schemas.py can load schemas for all tools by directly
importing and executing the hook logic.
"""

import json
import sys
from pathlib import Path

# Get repo root
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / '.claude' / 'hooks'))

from inject_schemas import extract_tools, load_tool_schemas


def test_tool_schema(tool_name: str) -> dict:
    """Test if schema can be loaded for a tool"""
    try:
        # Simulate message mentioning the tool
        message = f"Use {tool_name} to do something"

        # Extract tools from message
        tools = extract_tools(message)

        if tool_name not in tools:
            return {
                'tool': tool_name,
                'status': 'FAIL',
                'error': 'Tool not detected in message'
            }

        # Load schema
        schemas = load_tool_schemas(tools, str(repo_root))

        if tool_name in schemas:
            action_count = len(schemas[tool_name].get('actions', {}))
            return {
                'tool': tool_name,
                'status': 'PASS',
                'actions_found': action_count
            }
        else:
            return {
                'tool': tool_name,
                'status': 'FAIL',
                'error': 'Schema not loaded'
            }

    except Exception as e:
        return {
            'tool': tool_name,
            'status': 'FAIL',
            'error': str(e)
        }


def main():
    print("Schema Injection Validator\n")

    # Load system_settings to get all tools
    system_settings = repo_root / "system_settings.ndjson"

    tools = set()
    try:
        with open(system_settings, 'r') as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    if entry.get('action') == '__tool__':
                        tools.add(entry['tool'])
    except Exception as e:
        print(f"Failed to load system_settings.ndjson: {e}")
        sys.exit(1)

    print(f"Found {len(tools)} tools in system_settings.ndjson\n")

    results = []
    for tool in sorted(tools):
        print(f"Testing {tool}...", end=" ")
        result = test_tool_schema(tool)
        results.append(result)

        if result['status'] == 'PASS':
            print(f"✓ PASS ({result['actions_found']} actions)")
        else:
            print(f"✗ FAIL - {result['error']}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}\n")

    passed = sum(1 for r in results if r['status'] == 'PASS')
    failed = sum(1 for r in results if r['status'] == 'FAIL')

    print(f"Total Tools:  {len(results)}")
    print(f"Passed:       {passed}")
    print(f"Failed:       {failed}")

    if failed > 0:
        print(f"\nFailed tools:")
        for r in results:
            if r['status'] == 'FAIL':
                print(f"  ✗ {r['tool']}: {r['error']}")
        sys.exit(1)
    else:
        print(f"\n✅ ALL TOOLS HAVE WORKING SCHEMA INJECTION")
        sys.exit(0)


if __name__ == '__main__':
    main()
