#!/usr/bin/env python3
"""
Outline Queue Helper
Simple helper functions for automation_engine to use with outline queue
"""

import sys
import json
import os

# Hardcoded import path
IMPORT_PATH = os.path.expanduser("~/Orchestrate Github/orchestrate-jarvis/")


def read_file(params):
    """
    Reads a file from outline_docs_queue

    Required params:
    - filepath: Just the filename (no full path)

    Returns:
    - output: File content as string
    """
    filepath = params.get("filepath")

    if not filepath:
        return {"status": "error", "message": "Missing required param: filepath"}

    # Build full path
    full_path = os.path.join(IMPORT_PATH, filepath)

    if not os.path.exists(full_path):
        return {"status": "error", "message": f"File not found: {full_path}"}

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return {
            "status": "success",
            "output": content,
            "filepath": full_path
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to read file: {str(e)}"
        }


def resolve_collection(params):
    """
    Resolves collection name to ID

    Required params:
    - collection: Collection name (with or without # prefix)

    Returns:
    - collection_id: The resolved collection ID
    """
    collection_name = params.get("collection")

    if not collection_name:
        return {"status": "error", "message": "Missing required param: collection"}

    # Collection name to ID mapping
    COLLECTION_MAP = {
        "Inbox": "02b65969-7c17-40f3-9f82-2e4b0f93ba33",
        "Technical Documents": "d5e76f6d-a87f-44f4-8897-ca15f98fa01a",
        "Projects": "8e4d3be9-9d74-4c7f-a1c9-5e8c0f6a2b41",
        "Areas": "7c3a2fd8-8e63-4b0e-9c38-4d7b1e5a3c29",
        "Resources": "6b2c1ed7-7d52-4a0d-8b27-3c6a0d4b2c18",
        "Content": "9f8e7dc6-6c41-49fe-7a16-2b5f9e3d1c07",
        "Logs": "d9dc0bb5-fadb-4515-b864-f99f3132df52",
    }

    # Strip # prefix if present
    if collection_name.startswith("#"):
        collection_name = collection_name[1:]

    # Return ID or default to Inbox
    collection_id = COLLECTION_MAP.get(collection_name, COLLECTION_MAP["Inbox"])

    return {
        "status": "success",
        "collection_id": collection_id,
        "collection_name": collection_name
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"status": "error", "message": "Usage: outline_queue_helper.py <action> --params '{...}'"}))
        sys.exit(1)

    action = sys.argv[1]
    params_str = sys.argv[3] if len(sys.argv) > 3 else "{}"

    try:
        params = json.loads(params_str)
    except json.JSONDecodeError:
        print(json.dumps({"status": "error", "message": "Invalid JSON params"}))
        sys.exit(1)

    if action == "read_file":
        result = read_file(params)
    elif action == "resolve_collection":
        result = resolve_collection(params)
    else:
        result = {"status": "error", "message": f"Unknown action: {action}"}

    print(json.dumps(result, indent=2))
