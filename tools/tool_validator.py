import os
import ast
import json
import argparse

def is_flat(params):
    return all(not isinstance(v, dict) for v in params.values())

def validate_tool_script(filename):
    with open(filename, 'r') as f:
        source = f.read()

    tree = ast.parse(source)
    imports = [n for n in tree.body if isinstance(n, ast.Import) or isinstance(n, ast.ImportFrom)]
    has_dispatch_router = any(
        isinstance(n, ast.FunctionDef) and n.name == 'dispatch_router' for n in tree.body
    )

    results = {
        "file": filename,
        "has_imports": bool(imports),
        "has_dispatch_router": has_dispatch_router,
        "param_contract_violations": []
    }

    tool_name = os.path.basename(filename).replace(".py", "")
    contract_path = os.path.join("contracts", f"{tool_name}.json")

    if os.path.exists(contract_path):
        with open(contract_path, 'r') as f:
            try:
                actions = json.load(f)
            except json.JSONDecodeError:
                results["contract_error"] = "Invalid JSON"
                return results

        for a in actions:
            action_name = a.get("action")
            params = a.get("params", {})
            if not is_flat(params):
                results["param_contract_violations"].append(action_name)
    else:
        results["contract_warning"] = "No contract file found"

    return results

def scan_all_tools():
    tool_dir = os.path.join(os.path.dirname(__file__), "tools")
    results = []
    if not os.path.exists(tool_dir):
        return [{"error": f"Tool directory not found: {tool_dir}"}]
    for file in os.listdir(tool_dir):
        if file.endswith(".py") and file != "tool_validator.py":
            full_path = os.path.join(tool_dir, file)
            result = validate_tool_script(full_path)
            results.append(result)
    return results

def run_validation(_):
    return {"status": "complete", "report": scan_all_tools()}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action')
    parser.add_argument('--params')
    args = parser.parse_args()
    params = json.loads(args.params) if args.params else {}

    try:
        if args.action == 'run_validation':
            result = run_validation(params)
        elif args.action == 'validate_tool_script':
            result = validate_tool_script(filename=params.get("file_path") or params.get("filename"))
        elif args.action == 'scan_all_tools':
            result = scan_all_tools()
        elif args.action == 'is_flat':
            result = is_flat(params.get("params", {}))
        else:
            result = {'status': 'error', 'message': f'Unknown action {args.action}'}
    except Exception as e:
        result = {'status': 'error', 'message': str(e)}

    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()