#!python3
"""
claude_settings.py - Manage Claude Code settings programmatically

Handles:
- .claude/settings.json (version controlled, deny rules)
- .claude/settings.local.json (personal, tool schemas)
"""

import os
import json
import argparse
import sys

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(TOOLS_DIR, ".."))

SETTINGS_FILE = os.path.join(ROOT_DIR, ".claude/settings.json")
SETTINGS_LOCAL_FILE = os.path.join(ROOT_DIR, ".claude/settings.local.json")

def output(data):
    print(json.dumps(data, indent=2))
    sys.exit(0)

def error(message):
    print(json.dumps({"status": "error", "message": message}, indent=2))
    sys.exit(1)


def read_setting(params):
    """
    Read a setting from settings.json or settings.local.json

    Params:
    - key: Setting key to read (e.g., "tool_schemas")
    - source: "local" or "main" (default: "local")

    Returns:
    - Setting value or error if not found
    """
    key = params.get('key')
    source = params.get('source', 'local')

    if not key:
        return {'status': 'error', 'message': '❌ Missing required param: key'}

    file_path = SETTINGS_LOCAL_FILE if source == 'local' else SETTINGS_FILE

    if not os.path.exists(file_path):
        return {
            'status': 'error',
            'message': f'❌ Settings file not found: {file_path}'
        }

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)

        if key not in settings:
            return {
                'status': 'error',
                'message': f'❌ Key "{key}" not found in {source} settings',
                'available_keys': list(settings.keys())
            }

        return {
            'status': 'success',
            'key': key,
            'value': settings[key],
            'source': source
        }
    except Exception as e:
        return {'status': 'error', 'message': f'❌ Error reading settings: {str(e)}'}


def update_local_setting(params):
    """
    Update a setting in settings.local.json

    Params:
    - key: Setting key
    - value: New value (any JSON type)

    Returns:
    - Success status
    """
    key = params.get('key')

    if not key:
        return {'status': 'error', 'message': '❌ Missing required param: key'}

    if 'value' not in params:
        return {'status': 'error', 'message': '❌ Missing required param: value'}

    value = params['value']

    # Load existing settings.local.json or create new
    settings = {}
    if os.path.exists(SETTINGS_LOCAL_FILE):
        try:
            with open(SETTINGS_LOCAL_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        except Exception as e:
            return {'status': 'error', 'message': f'❌ Error reading settings.local.json: {str(e)}'}

    # Update key
    settings[key] = value

    # Write back
    try:
        with open(SETTINGS_LOCAL_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)

        return {
            'status': 'success',
            'message': f'✅ Updated {key} in settings.local.json',
            'key': key,
            'file': SETTINGS_LOCAL_FILE
        }
    except Exception as e:
        return {'status': 'error', 'message': f'❌ Error writing settings: {str(e)}'}


def add_deny_rule(params):
    """
    Add a deny rule to settings.json

    Params:
    - rule: Bash command pattern to deny (e.g., "Bash(python3 tools/foo.py:*)")

    Returns:
    - Success status
    """
    rule = params.get('rule')

    if not rule:
        return {'status': 'error', 'message': '❌ Missing required param: rule'}

    if not os.path.exists(SETTINGS_FILE):
        return {'status': 'error', 'message': f'❌ settings.json not found: {SETTINGS_FILE}'}

    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)

        # Initialize denyRules if missing
        if 'denyRules' not in settings:
            settings['denyRules'] = []

        # Check if rule already exists
        if rule in settings['denyRules']:
            return {
                'status': 'success',
                'message': f'✅ Rule already exists',
                'rule': rule
            }

        # Add rule
        settings['denyRules'].append(rule)

        # Write back
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)

        return {
            'status': 'success',
            'message': f'✅ Added deny rule to settings.json',
            'rule': rule,
            'total_rules': len(settings['denyRules'])
        }
    except Exception as e:
        return {'status': 'error', 'message': f'❌ Error updating settings: {str(e)}'}


def get_tool_schemas(params):
    """
    Get tool schemas from settings.local.json

    Params:
    - tool_name: Optional - filter by tool name
    - action: Optional - filter by action

    Returns:
    - List of matching schemas
    """
    tool_name = params.get('tool_name')
    action = params.get('action')

    if not os.path.exists(SETTINGS_LOCAL_FILE):
        return {
            'status': 'error',
            'message': f'❌ settings.local.json not found. Run update_local_setting to create it.'
        }

    try:
        with open(SETTINGS_LOCAL_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)

        if 'tool_schemas' not in settings:
            return {
                'status': 'error',
                'message': '❌ No tool_schemas found in settings.local.json'
            }

        schemas = settings['tool_schemas']

        # Filter by tool_name
        if tool_name:
            schemas = [s for s in schemas if s.get('tool') == tool_name]

        # Filter by action
        if action:
            schemas = [s for s in schemas if s.get('action') == action]

        return {
            'status': 'success',
            'count': len(schemas),
            'schemas': schemas
        }
    except Exception as e:
        return {'status': 'error', 'message': f'❌ Error reading schemas: {str(e)}'}


def validate_settings(params):
    """
    Validate that settings files are properly formatted

    Returns:
    - Status and any issues found
    """
    issues = []

    # Check settings.json
    if not os.path.exists(SETTINGS_FILE):
        issues.append('❌ settings.json not found')
    else:
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                json.load(f)
        except Exception as e:
            issues.append(f'❌ settings.json invalid JSON: {str(e)}')

    # Check settings.local.json
    if os.path.exists(SETTINGS_LOCAL_FILE):
        try:
            with open(SETTINGS_LOCAL_FILE, 'r', encoding='utf-8') as f:
                local = json.load(f)

            # Validate tool_schemas structure if present
            if 'tool_schemas' in local:
                schemas = local['tool_schemas']
                if not isinstance(schemas, list):
                    issues.append('❌ tool_schemas must be an array')
                else:
                    for i, schema in enumerate(schemas):
                        if not isinstance(schema, dict):
                            issues.append(f'❌ Schema {i} is not an object')
                        elif 'tool' not in schema:
                            issues.append(f'❌ Schema {i} missing "tool" field')
        except Exception as e:
            issues.append(f'❌ settings.local.json invalid JSON: {str(e)}')

    if issues:
        return {
            'status': 'error',
            'message': 'Settings validation failed',
            'issues': issues
        }

    return {
        'status': 'success',
        'message': '✅ All settings files valid'
    }


def list_deny_rules(params):
    """
    List all deny rules from settings.json

    Returns:
    - List of deny rules
    """
    if not os.path.exists(SETTINGS_FILE):
        return {'status': 'error', 'message': f'❌ settings.json not found'}

    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)

        rules = settings.get('denyRules', [])

        return {
            'status': 'success',
            'count': len(rules),
            'rules': rules
        }
    except Exception as e:
        return {'status': 'error', 'message': f'❌ Error reading settings: {str(e)}'}


def main():
    parser = argparse.ArgumentParser(description='Manage Claude Code settings')
    parser.add_argument('action', help='Action to perform')
    parser.add_argument('--params', help='JSON params')
    args = parser.parse_args()

    params = json.loads(args.params) if args.params else {}

    actions = {
        'read_setting': read_setting,
        'update_local_setting': update_local_setting,
        'add_deny_rule': add_deny_rule,
        'get_tool_schemas': get_tool_schemas,
        'validate_settings': validate_settings,
        'list_deny_rules': list_deny_rules,
    }

    if args.action not in actions:
        error(f'Unknown action: {args.action}. Available: {", ".join(actions.keys())}')

    result = actions[args.action](params)
    output(result)


if __name__ == '__main__':
    main()
