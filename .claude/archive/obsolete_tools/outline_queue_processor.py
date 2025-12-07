#!/usr/bin/env python3
"""
Outline Queue Processor
Processes queue entries and calls outline_editor with proper params
"""

import sys
import json
import os
import subprocess
from datetime import datetime
from collection_resolver import resolve_collection, get_file_path, read_file_content


def process_create_doc(params):
    """
    Process a new document creation

    Required params:
    - entry_key: Queue entry key
    - file: Filename (no path)
    - collection: Collection name or ID
    """
    entry_key = params.get("entry_key")
    filename = params.get("file")
    collection = params.get("collection")

    if not all([entry_key, filename, collection]):
        return {"status": "error", "message": "Missing required params: entry_key, file, collection"}

    # Resolve collection name to ID
    collection_id = resolve_collection(collection)

    # Get full file path
    file_path = get_file_path(filename)

    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {file_path}"}

    # Call outline_editor to import the doc
    cmd = [
        "python3",
        "tools/outline_editor.py",
        "import_doc_from_file",
        "--params",
        json.dumps({
            "file_path": file_path,
            "collectionId": collection_id,
            "publish": True
        })
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        response = json.loads(result.stdout)

        if result.returncode == 0 and response.get("data"):
            doc_id = response["data"]["id"]

            # Update queue entry with doc_id and status
            update_queue_entry(entry_key, {
                "doc_id": doc_id,
                "status": "processed",
                "updated_at": datetime.now().isoformat()
            })

            return {
                "status": "success",
                "doc_id": doc_id,
                "message": f"Document created: {doc_id}"
            }
        else:
            error_msg = response.get("message", result.stderr)
            update_queue_entry(entry_key, {
                "status": "error",
                "error": error_msg,
                "updated_at": datetime.now().isoformat()
            })
            return {"status": "error", "message": error_msg}

    except Exception as e:
        error_msg = str(e)
        update_queue_entry(entry_key, {
            "status": "error",
            "error": error_msg,
            "updated_at": datetime.now().isoformat()
        })
        return {"status": "error", "message": error_msg}


def process_create_child_doc(params):
    """
    Process a child document creation

    Required params:
    - entry_key: Queue entry key
    - file: Filename (no path)
    - parent_doc_id: Parent document ID
    """
    entry_key = params.get("entry_key")
    filename = params.get("file")
    parent_doc_id = params.get("parent_doc_id")

    if not all([entry_key, filename, parent_doc_id]):
        return {"status": "error", "message": "Missing required params: entry_key, file, parent_doc_id"}

    # Get full file path
    file_path = get_file_path(filename)

    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {file_path}"}

    # Call outline_editor to import the doc as a child
    cmd = [
        "python3",
        "tools/outline_editor.py",
        "import_doc_from_file",
        "--params",
        json.dumps({
            "file_path": file_path,
            "parentDocumentId": parent_doc_id,
            "publish": True
        })
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        response = json.loads(result.stdout)

        if result.returncode == 0 and response.get("data"):
            doc_id = response["data"]["id"]

            # Update queue entry with doc_id and status
            update_queue_entry(entry_key, {
                "doc_id": doc_id,
                "status": "processed",
                "updated_at": datetime.now().isoformat()
            })

            return {
                "status": "success",
                "doc_id": doc_id,
                "message": f"Child document created: {doc_id}"
            }
        else:
            error_msg = response.get("message", result.stderr)
            update_queue_entry(entry_key, {
                "status": "error",
                "error": error_msg,
                "updated_at": datetime.now().isoformat()
            })
            return {"status": "error", "message": error_msg}

    except Exception as e:
        error_msg = str(e)
        update_queue_entry(entry_key, {
            "status": "error",
            "error": error_msg,
            "updated_at": datetime.now().isoformat()
        })
        return {"status": "error", "message": error_msg}


def process_update_doc(params):
    """
    Process a document update

    Required params:
    - entry_key: Queue entry key
    - file: Filename (no path)
    - doc_id: Document ID to update
    """
    entry_key = params.get("entry_key")
    filename = params.get("file")
    doc_id = params.get("doc_id")

    if not all([entry_key, filename, doc_id]):
        return {"status": "error", "message": "Missing required params: entry_key, file, doc_id"}

    # Get full file path
    file_path = get_file_path(filename)

    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {file_path}"}

    # Read file content
    try:
        content = read_file_content(filename)
    except Exception as e:
        return {"status": "error", "message": f"Failed to read file: {str(e)}"}

    # Call outline_editor to update the doc
    cmd = [
        "python3",
        "tools/outline_editor.py",
        "update_doc",
        "--params",
        json.dumps({
            "doc_id": doc_id,
            "text": content,
            "append": False,
            "publish": True
        })
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        response = json.loads(result.stdout)

        if result.returncode == 0:
            # Update queue entry - reset status to processed
            update_queue_entry(entry_key, {
                "status": "processed",
                "updated_at": datetime.now().isoformat()
            })

            return {
                "status": "success",
                "doc_id": doc_id,
                "message": f"Document updated: {doc_id}"
            }
        else:
            error_msg = response.get("message", result.stderr)
            update_queue_entry(entry_key, {
                "status": "error",
                "error": error_msg,
                "updated_at": datetime.now().isoformat()
            })
            return {"status": "error", "message": error_msg}

    except Exception as e:
        error_msg = str(e)
        update_queue_entry(entry_key, {
            "status": "error",
            "error": error_msg,
            "updated_at": datetime.now().isoformat()
        })
        return {"status": "error", "message": error_msg}


def update_queue_entry(entry_key, updates):
    """Update queue entry with new fields"""
    queue_file = "data/outline_queue.json"

    try:
        with open(queue_file, 'r') as f:
            queue = json.load(f)
    except Exception:
        queue = {"entries": {}}

    if entry_key not in queue.get("entries", {}):
        print(f"Warning: entry_key {entry_key} not found in queue", file=sys.stderr)
        return

    queue["entries"][entry_key].update(updates)

    with open(queue_file, 'w') as f:
        json.dump(queue, f, indent=2)


def main(params):
    """Main entry point for outline_queue_processor"""
    action = params.get("action")

    if action == "process_create_doc":
        return process_create_doc(params)
    elif action == "process_create_child_doc":
        return process_create_child_doc(params)
    elif action == "process_update_doc":
        return process_update_doc(params)
    else:
        return {"status": "error", "message": f"Unknown action: {action}"}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"status": "error", "message": "Usage: outline_queue_processor.py <action> --params '{...}'"}))
        sys.exit(1)

    action = sys.argv[1]
    params_str = sys.argv[3] if len(sys.argv) > 3 else "{}"
    params = json.loads(params_str)
    params["action"] = action

    result = main(params)
    print(json.dumps(result, indent=2))
