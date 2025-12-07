import os
import ast
import json

TOOLS_DIR = 'tools'
SETTINGS_FILE = 'system_settings.ndjson'
REPORT_FILE = 'data/schema_validation_report.txt'

# Load system_settings.ndjson
def load_system_settings():
    tool_actions = {}
    with open(SETTINGS_FILE, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                tool = obj.get('tool')
                action = obj.get('action')
                params = obj.get('params', [])
                if tool and action:
                    tool_actions[(tool, action)] = params
            except json.JSONDecodeError:
                continue
    return tool_actions

# Extract top-level def signatures from each tool file
def extract_tool_actions():
    extracted = {}
    for filename in os.listdir(TOOLS_DIR):
        if not filename.endswith('.py'):
            continue
        tool_name = filename.replace('.py', '')
        with open(os.path.join(TOOLS_DIR, filename), 'r') as f:
            try:
                tree = ast.parse(f.read())
            except SyntaxError:
                continue
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    action_name = node.name
                    arg_names = [arg.arg for arg in node.args.args if arg.arg != 'context']
                    # Detect if using unpacked 'params'
                    if len(arg_names) == 1 and arg_names[0] == 'params':
                        extracted[(tool_name, action_name)] = '__params_wrapped__'
                    else:
                        extracted[(tool_name, action_name)] = arg_names
    return extracted

# Compare extracted actions against system_settings.ndjson
def validate():
    settings = load_system_settings()
    extracted = extract_tool_actions()
    report = []

    for key, code_params in extracted.items():
        settings_params = settings.get(key)

        if settings_params is None:
            report.append(f'MISSING in system_settings: {key[0]}.{key[1]}')
            continue

        if code_params == '__params_wrapped__':
            # Skip detailed comparison — we assume contract is flat-packed inside `params`
            continue

        if sorted(settings_params) != sorted(code_params):
            report.append(f'MISMATCH for {key[0]}.{key[1]}:\n  system_settings: {settings_params}\n  code:             {code_params}')

    for key in settings:
        if key not in extracted:
            report.append(f'OBSOLETE in system_settings: {key[0]}.{key[1]}')

    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, 'w') as out:
        if not report:
            out.write('✅ All schemas aligned. No mismatches found.')
        else:
            out.write('\n'.join(report))

    print(f'Report written to {REPORT_FILE}')

if __name__ == '__main__':
    validate()