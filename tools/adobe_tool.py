"""
Adobe Tool - Unified Adobe Creative Cloud automation using JSON operation sequences and core primitives.

Architecture:
    Claude (generates JSON operation sequences)
            ↓
    adobe_tool.py (Python orchestration layer)
    - Validates operations against primitives
    - Writes config to standard location
    - Invokes JSX via osascript
    - Returns result/error
            ↓
    JSX Core Files (one per app, exposes primitives)
"""

import json
import os
import subprocess
from pathlib import Path

ACTIONS = {
    "execute": {
        "required": ["config"],
        "optional": [],
        "description": "Execute operation sequence from JSON config"
    },
    "execute_from_file": {
        "required": ["config_file"],
        "optional": [],
        "description": "Execute operation sequence from JSON file path"
    },
    "list_primitives": {
        "required": ["app"],
        "optional": [],
        "description": "List available primitives for an Adobe app"
    },
    "validate_config": {
        "required": ["config"],
        "optional": [],
        "description": "Validate config without executing"
    }
}

SUPPORTED_APPS = ["photoshop", "aftereffects", "indesign", "premiere"]

APP_NAMES = {
    "photoshop": "Adobe Photoshop 2025",
    "aftereffects": "Adobe After Effects 2025",
    "indesign": "Adobe InDesign 2025",
    "premiere": "Adobe Premiere Pro 2025"
}

# JSX paths relative to orchestrate-jarvis
SCRIPT_DIR = Path(__file__).parent
JSX_DIR = SCRIPT_DIR / "adobe_jsx"

JSX_PATHS = {
    "photoshop": JSX_DIR / "photoshop_core.jsx",
    "aftereffects": JSX_DIR / "aftereffects_core.jsx",
    "indesign": JSX_DIR / "indesign_core.jsx",
    "premiere": JSX_DIR / "premiere_core.jsx"
}

# Primitives definitions with required params
PRIMITIVES = {
    "photoshop": {
        "createDocument": {"required": ["width", "height"], "optional": ["name", "colorMode"]},
        "openDocument": {"required": ["path"], "optional": []},
        "addTextLayer": {"required": ["text", "x", "y"], "optional": ["font", "size", "color"]},
        "addShapeLayer": {"required": ["type", "params"], "optional": []},
        "applyGradient": {"required": ["layer", "startColor", "endColor"], "optional": ["angle"]},
        "applyEffect": {"required": ["layer", "effectName", "params"], "optional": []},
        "importImage": {"required": ["path", "x", "y"], "optional": ["width", "height", "removeBackground"]},
        "setLayerOpacity": {"required": ["layer", "opacity"], "optional": []},
        "setLayerBlendMode": {"required": ["layer", "mode"], "optional": []},
        "resizeCanvas": {"required": ["width", "height"], "optional": ["anchor"]},
        "flattenLayers": {"required": [], "optional": []},
        "exportPNG": {"required": ["path"], "optional": []},
        "exportJPG": {"required": ["path"], "optional": ["quality"]},
        "saveDocument": {"required": ["path"], "optional": []},
        "closeDocument": {"required": [], "optional": ["save"]},
        "removeBackground": {"required": ["layer"], "optional": []},
        "runAction": {"required": ["actionSet", "actionName"], "optional": []}
    },
    "aftereffects": {
        "createComp": {"required": ["name", "width", "height", "duration", "framerate"], "optional": []},
        "addTextLayer": {"required": ["text", "position"], "optional": ["font", "size", "color", "inPoint", "outPoint"]},
        "addShapeLayer": {"required": ["type", "params"], "optional": ["inPoint", "outPoint"]},
        "addSolidLayer": {"required": ["name", "color", "width", "height"], "optional": ["inPoint", "outPoint"]},
        "addImageLayer": {"required": ["path"], "optional": ["inPoint", "outPoint", "position", "scale"]},
        "addAudioLayer": {"required": ["path"], "optional": ["inPoint"]},
        "addKeyframe": {"required": ["layer", "property", "time", "value"], "optional": ["easing"]},
        "applyPreset": {"required": ["layer", "presetPath"], "optional": []},
        "setLayerParent": {"required": ["childLayer", "parentLayer"], "optional": []},
        "setExpression": {"required": ["layer", "property", "expression"], "optional": []},
        "addToRenderQueue": {"required": ["comp", "outputPath", "format"], "optional": ["settings"]},
        "render": {"required": [], "optional": []}
    },
    "indesign": {},
    "premiere": {}
}

# Standard file paths
CONFIG_PATH = os.path.expanduser("~/orchestrate/data/adobe_config.json")
RESULT_PATH = os.path.expanduser("~/orchestrate/data/adobe_result.json")


def ensure_data_dir():
    """Ensure the orchestrate data directory exists"""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)


def validate_config(config: dict) -> dict:
    """
    Validate operation config without executing

    Returns: {"valid": True} or {"valid": False, "errors": [...]}
    """
    errors = []

    # Check app
    app = config.get("app")
    if not app:
        errors.append("Missing required field: app")
    elif app not in SUPPORTED_APPS:
        errors.append(f"Unsupported app: {app}. Must be one of: {SUPPORTED_APPS}")

    # Check operations
    operations = config.get("operations")
    if not operations:
        errors.append("Missing required field: operations")
    elif not isinstance(operations, list):
        errors.append("operations must be an array")
    elif app in SUPPORTED_APPS:
        app_primitives = PRIMITIVES.get(app, {})

        for i, op in enumerate(operations):
            if not isinstance(op, dict):
                errors.append(f"Operation {i} must be an object")
                continue

            fn = op.get("fn")
            if not fn:
                errors.append(f"Operation {i}: Missing required field 'fn'")
                continue

            if fn not in app_primitives:
                errors.append(f"Operation {i}: Unknown primitive '{fn}' for {app}")
                continue

            # Check required params
            required = app_primitives[fn].get("required", [])
            for param in required:
                if param not in op:
                    errors.append(f"Operation {i} ({fn}): Missing required param '{param}'")

    if errors:
        return {"valid": False, "errors": errors}
    return {"valid": True}


def execute(config: dict) -> dict:
    """
    Execute Adobe operation sequence

    1. Validate app is supported
    2. Validate each operation against known primitives
    3. Write config to ~/orchestrate/data/adobe_config.json
    4. Invoke appropriate JSX core file via osascript
    5. Read result from ~/orchestrate/data/adobe_result.json
    6. Return success/error with output path
    """
    # Validate first
    validation = validate_config(config)
    if not validation.get("valid"):
        return {"status": "error", "error": "Validation failed", "details": validation.get("errors", [])}

    app = config["app"]

    # Check JSX file exists
    jsx_path = JSX_PATHS.get(app)
    if not jsx_path or not jsx_path.exists():
        return {"status": "error", "error": f"JSX core file not found for {app}: {jsx_path}"}

    # Ensure data dir exists
    ensure_data_dir()

    # Write config
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

    # Build osascript command
    app_name = APP_NAMES[app]
    jsx_abs_path = str(jsx_path.resolve())

    # Use osascript to invoke JSX
    script = f'''
    tell application "{app_name}"
        activate
        do javascript file "{jsx_abs_path}"
    end tell
    '''

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode != 0:
            return {
                "status": "error",
                "error": "osascript execution failed",
                "stderr": result.stderr,
                "stdout": result.stdout
            }

        # Read result file
        if os.path.exists(RESULT_PATH):
            with open(RESULT_PATH) as f:
                content = f.read()
            # Remove control characters that ExtendScript may insert in error messages
            content = content.replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ')
            jsx_result = json.loads(content)
            return {"status": "success", **jsx_result}
        else:
            return {
                "status": "success",
                "message": "Execution completed but no result file found",
                "stdout": result.stdout
            }

    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "Execution timed out after 5 minutes"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def execute_from_file(config_file: str) -> dict:
    """
    Execute operation sequence from JSON file path
    """
    config_path = os.path.expanduser(config_file)

    if not os.path.exists(config_path):
        return {"status": "error", "error": f"Config file not found: {config_path}"}

    try:
        with open(config_path) as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        return {"status": "error", "error": f"Invalid JSON in config file: {e}"}

    return execute(config)


def list_primitives(app: str) -> dict:
    """
    List available primitives for an Adobe app
    """
    if app not in SUPPORTED_APPS:
        return {
            "status": "error",
            "error": f"Unsupported app: {app}. Must be one of: {SUPPORTED_APPS}"
        }

    primitives = PRIMITIVES.get(app, {})

    result = {
        "status": "success",
        "app": app,
        "primitives": {}
    }

    for fn_name, params in primitives.items():
        result["primitives"][fn_name] = {
            "required": params.get("required", []),
            "optional": params.get("optional", [])
        }

    return result


def run(action: str, params: dict) -> dict:
    """Main entry point called by execution_hub"""

    if action == "execute":
        config = params.get("config")
        if not config:
            return {"status": "error", "error": "Missing required param: config"}
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except json.JSONDecodeError as e:
                return {"status": "error", "error": f"Invalid JSON config: {e}"}
        return execute(config)

    elif action == "execute_from_file":
        config_file = params.get("config_file")
        if not config_file:
            return {"status": "error", "error": "Missing required param: config_file"}
        return execute_from_file(config_file)

    elif action == "list_primitives":
        app = params.get("app")
        if not app:
            return {"status": "error", "error": "Missing required param: app"}
        return list_primitives(app)

    elif action == "validate_config":
        config = params.get("config")
        if not config:
            return {"status": "error", "error": "Missing required param: config"}
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except json.JSONDecodeError as e:
                return {"status": "error", "error": f"Invalid JSON config: {e}"}
        validation = validate_config(config)
        return {"status": "success" if validation.get("valid") else "error", **validation}

    else:
        return {"status": "error", "error": f"Unknown action: {action}. Available: {list(ACTIONS.keys())}"}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('action')
    parser.add_argument('--params')
    args = parser.parse_args()
    params = json.loads(args.params) if args.params else {}
    result = run(args.action, params)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
