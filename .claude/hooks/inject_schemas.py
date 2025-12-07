#!/usr/bin/env python3
"""
Auto-inject relevant tool schemas from system_settings.ndjson based on user prompt.
Also injects utility script schemas from utility_scripts.ndjson.
Reduces token bloat by only loading schemas for tools mentioned in the message.
"""
import json
import sys
import re
from pathlib import Path

def extract_tool_names(user_message):
    """Extract potential tool names from user message."""
    # Read system_settings to get all valid tool names
    settings_path = Path(__file__).parent.parent.parent / "system_settings.ndjson"
    if not settings_path.exists():
        return []

    valid_tools = set()
    with open(settings_path) as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if "tool" in entry:
                    valid_tools.add(entry["tool"])
            except:
                continue

    # Find tool names mentioned in message
    mentioned_tools = set()
    message_lower = user_message.lower()

    for tool in valid_tools:
        # Check for exact tool name or common variations
        if tool in message_lower or tool.replace("_", " ") in message_lower:
            mentioned_tools.add(tool)

    return mentioned_tools

def extract_utility_scripts(user_message):
    """Extract mentioned utility scripts from user message."""
    scripts_path = Path(__file__).parent.parent.parent / "utility_scripts.ndjson"
    if not scripts_path.exists():
        return []

    valid_scripts = {}
    with open(scripts_path) as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                script_name = entry.get("script")
                if script_name:
                    valid_scripts[script_name] = entry
            except:
                continue

    # Find scripts mentioned in message
    mentioned_scripts = []
    message_lower = user_message.lower()

    for script_name, script_data in valid_scripts.items():
        # Check for script name or path mentions
        if script_name in message_lower or script_data.get("path", "") in message_lower:
            mentioned_scripts.append(script_data)

    return mentioned_scripts

def get_tool_schemas(tool_names):
    """Get schemas for specific tools from system_settings.ndjson."""
    if not tool_names:
        return ""

    settings_path = Path(__file__).parent.parent.parent / "system_settings.ndjson"
    if not settings_path.exists():
        return ""

    schemas = []
    with open(settings_path) as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if entry.get("tool") in tool_names:
                    # Skip the __tool__ meta entry
                    if entry.get("action") != "__tool__":
                        schemas.append(entry)
            except:
                continue

    return schemas

def get_critical_rules(user_message):
    """Return critical workflow rules when relevant keywords are detected."""
    message_lower = user_message.lower()

    # Keywords that trigger inbox rule injection
    inbox_keywords = ['inbox', 'claude inbox', 'reply', 'respond', 'update_doc', 'append']

    if any(kw in message_lower for kw in inbox_keywords):
        return """
🚨 CLAUDE INBOX RULE 🚨
Inbox replies = update_doc ONLY. NEVER queue_doc. NEVER write files.

COMMAND:
python3 execution_hub.py execute_task --params '{
  "tool_name": "outline_editor",
  "action": "update_doc",
  "params": {"doc_id": "<inbox doc id>", "text": "Your reply...", "append": true}
}'

queue_doc REJECTS inbox reply filenames automatically.
"""
    return ""


def format_schema_output(schemas, utility_scripts, critical_rules=""):
    """Format schemas and utility scripts into readable injection text."""
    if not schemas and not utility_scripts and not critical_rules:
        return ""

    output = ["<system-reminder>"]

    # Critical rules first (highest priority)
    if critical_rules:
        output.append(critical_rules)

    # UTILITY SCRIPTS FIRST (higher priority for Claude)
    if utility_scripts:
        output.append("")
        output.append("━" * 60)
        output.append("UTILITY SCRIPTS")
        output.append("━" * 60)
        output.append("")
        for script in utility_scripts:
            script_name = script.get("script", "")
            path = script.get("path", "")
            desc = script.get("description", "")
            output.append(f"{script_name}")
            output.append(f"  PATH: {path}")
            if desc:
                output.append(f"  → {desc}")
            output.append("")

    # TOOL SCHEMAS
    if schemas:
        # Group schemas by tool
        tools = {}
        for schema in schemas:
            tool = schema["tool"]
            if tool not in tools:
                tools[tool] = []
            tools[tool].append(schema)

        for tool, tool_schemas in tools.items():
            output.append("")
            output.append("━" * 60)
            output.append(f"TOOL: {tool}")
            output.append("━" * 60)
            output.append("")

            # List all actions first
            action_names = [s["action"] for s in tool_schemas]
            output.append("ACTIONS:")
            output.append(" | ".join(action_names))
            output.append("")
            output.append("━" * 60)

            # Then detail each action
            for schema in tool_schemas:
                action = schema["action"]
                params = schema.get("params", [])
                desc = schema.get("description", "")

                output.append(f"{action}")
                if params:
                    # Try to determine required vs optional from description
                    req_params = []
                    opt_params = []

                    # Expanded heuristic: common required params
                    common_required = {
                        "doc_id", "title", "query", "file_path", "collection_id", "content",
                        "parent_doc_id", "filename", "prompt", "prompts", "text", "url",
                        "tool_name", "action", "message", "task_id", "entry_key"
                    }

                    # Params that are usually optional
                    common_optional = {
                        "append", "publish", "limit", "offset", "campaign_name", "blog_post",
                        "auto_generate", "save_dir", "direction", "sort", "color", "icon",
                        "description", "permission", "sharing"
                    }

                    for p in params:
                        if p in common_optional:
                            opt_params.append(p)
                        elif p in common_required:
                            req_params.append(p)
                        else:
                            # If unsure, treat as required (safer than missing it)
                            req_params.append(p)

                    if req_params:
                        output.append(f"  REQUIRED: {', '.join(req_params)}")
                    if opt_params:
                        output.append(f"  OPTIONAL: {', '.join(opt_params)}")

                if desc:
                    # Truncate long descriptions
                    short_desc = desc[:100] + "..." if len(desc) > 100 else desc
                    output.append(f"  → {short_desc}")
                output.append("")

    output.append("━" * 60)
    output.append("</system-reminder>")
    return "\n".join(output)

# Main execution
try:
    input_data = json.load(sys.stdin)

    # Debug log
    log_path = Path(__file__).parent.parent.parent / "data" / "hook_debug.log"
    with open(log_path, "a") as log:
        log.write(f"\n--- Hook called ---\n")
        log.write(f"Input: {json.dumps(input_data)}\n")

    # Claude Code passes "prompt", manual tests pass "user_message"
    user_message = input_data.get("prompt") or input_data.get("user_message", "")

    if not user_message:
        sys.exit(0)  # No message to process

    # Extract tool schemas
    tool_names = extract_tool_names(user_message)
    schemas = get_tool_schemas(tool_names)

    # Extract utility scripts
    utility_scripts = extract_utility_scripts(user_message)

    # Get critical workflow rules
    critical_rules = get_critical_rules(user_message)

    # Only proceed if we found something
    if not tool_names and not utility_scripts and not critical_rules:
        sys.exit(0)

    output = format_schema_output(schemas, utility_scripts, critical_rules)

    # Debug log results
    with open(log_path, "a") as log:
        log.write(f"Tools found: {list(tool_names)}\n")
        log.write(f"Utility scripts found: {[s.get('script') for s in utility_scripts]}\n")
        log.write(f"Schemas count: {len(schemas)}\n")
        log.write(f"Output length: {len(output) if output else 0}\n")

    if output:
        print(output)

except Exception as e:
    # Log errors but don't break workflow
    try:
        log_path = Path(__file__).parent.parent.parent / "data" / "hook_debug.log"
        with open(log_path, "a") as log:
            log.write(f"ERROR: {str(e)}\n")
    except:
        pass
    sys.exit(0)
