import os
import json
import subprocess
import re

API_ACTIONS_DIR = "api_actions"
os.makedirs(API_ACTIONS_DIR, exist_ok=True)

def load_actions_file(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_actions_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def create_api_file(params):
    path = os.path.join(API_ACTIONS_DIR, params["filename"])
    if os.path.exists(path):
        return {"status": "error", "message": "File already exists"}
    save_actions_file(path, {})
    return {"status": "success", "created": path}

def add_api_command(params):
    path = os.path.join(API_ACTIONS_DIR, params["filename"])
    key = params["key"]
    command = params["command"]
    data = load_actions_file(path)
    if key in data:
        return {"status": "error", "message": f"Key '{key}' already exists."}
    data[key] = command
    save_actions_file(path, data)
    return {"status": "success", "message": f"Command '{key}' added."}

def update_api_command(params):
    path = os.path.join(API_ACTIONS_DIR, params["filename"])
    key = params["key"]
    command = params["command"]
    data = load_actions_file(path)
    if key not in data:
        return {"status": "error", "message": f"Key '{key}' not found."}
    data[key] = command
    save_actions_file(path, data)
    return {"status": "success", "message": f"Command '{key}' updated."}

def delete_api_command(params):
    path = os.path.join(API_ACTIONS_DIR, params["filename"])
    key = params["key"]
    data = load_actions_file(path)
    if key in data:
        del data[key]
        save_actions_file(path, data)
        return {"status": "success", "message": f"Command '{key}' deleted."}
    return {"status": "error", "message": f"Key '{key}' not found."}

def rename_api_key(params):
    path = os.path.join(API_ACTIONS_DIR, params["filename"])
    old_key = params["old_key"]
    new_key = params["new_key"]
    data = load_actions_file(path)
    if old_key not in data:
        return {"status": "error", "message": f"Key '{old_key}' not found."}
    if new_key in data:
        return {"status": "error", "message": f"Key '{new_key}' already exists."}
    data[new_key] = data.pop(old_key)
    save_actions_file(path, data)
    return {"status": "success", "message": f"Renamed '{old_key}' to '{new_key}'"}

def list_api_commands(params):
    path = os.path.join(API_ACTIONS_DIR, params["filename"])
    data = load_actions_file(path)
    return {"status": "success", "keys": list(data.keys())}

def get_api_command(params):
    path = os.path.join(API_ACTIONS_DIR, params["filename"])
    key = params["key"]
    data = load_actions_file(path)
    return {"status": "success", "command": data.get(key)}

def execute_api_action(params):
    import re, json
    path = os.path.join(API_ACTIONS_DIR, params["filename"])
    key = params["key"]
    data = load_actions_file(path)
    command = data.get(key)
    if not command:
        return {"status": "error", "message": f"Command '{key}' not found."}

    # Merge variables with api_keys.json
    try:
        with open("api_actions/api_keys.json", "r") as f:
            stored_keys = json.load(f)
    except Exception:
        stored_keys = {}

    passed_vars = params.get("variables", {})
    variables = {**stored_keys, **passed_vars}  # passed_vars overrides keys

    for var, val in variables.items():
        command = re.sub(r"{{\s*" + re.escape(var) + r"\s*}}", val, command)

    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        return {
            "status": "success" if result.returncode == 0 else "error",
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def create_tool_api_file(params):
    tool = params.get("tool")
    if not tool:
        return {"status": "error", "message": "Missing 'tool' param"}

    filename = f"{tool}.txt"
    path = os.path.join(API_ACTIONS_DIR, filename)

    if os.path.exists(path):
        return {"status": "exists", "message": f"File already exists: {filename}"}

    with open(path, "w", encoding="utf-8") as f:
        json.dump({}, f, indent=2)

    return {"status": "success", "filename": filename, "path": path}

def main():
    import argparse, json
    parser = argparse.ArgumentParser()
    parser.add_argument("action")
    parser.add_argument("--params")
    args = parser.parse_args()
    params = json.loads(args.params or "{}")

    if args.action == "create_api_file":
        result = create_api_file(params)
    elif args.action == "add_api_command":
        result = add_api_command(params)
    elif args.action == "update_api_command":
        result = update_api_command(params)
    elif args.action == "delete_api_command":
        result = delete_api_command(params)
    elif args.action == "rename_api_key":
        result = rename_api_key(params)
    elif args.action == "list_api_commands":
        result = list_api_commands(params)
    elif args.action == "get_api_command":
        result = get_api_command(params)
    elif args.action == "execute_api_action":
        result = execute_api_action(params)
    elif args.action == "create_tool_api_file":
        result = create_tool_api_file(params)
    else:
        result = {"status": "error", "message": f"Unknown action: {args.action}"}

    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()