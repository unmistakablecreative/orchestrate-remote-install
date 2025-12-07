#!/usr/bin/env python3
"""
Collection Resolver for Outline Queue System
Maps collection names to their IDs with hardcoded import path
"""

import os

# Hardcoded import path - ALWAYS use this directory
IMPORT_PATH = os.path.expanduser("~/Orchestrate Github/orchestrate-jarvis/")

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


def resolve_collection(name: str) -> str:
    """
    Resolves collection name to ID

    Args:
        name: Collection name, optionally with # prefix

    Returns:
        Collection ID string
    """
    # Strip # prefix if present
    if name.startswith("#"):
        name = name[1:]

    # Return ID or default to Inbox
    return COLLECTION_MAP.get(name, COLLECTION_MAP["Inbox"])


def get_file_path(filename: str) -> str:
    """
    Returns full file path for a queue file

    Args:
        filename: Just the filename (e.g., "my-doc.md")

    Returns:
        Full path to file in outline_docs_queue/
    """
    return os.path.join(IMPORT_PATH, filename)


def read_file_content(filename: str) -> str:
    """
    Reads markdown file content from queue directory

    Args:
        filename: Just the filename (e.g., "my-doc.md")

    Returns:
        File content as string
    """
    filepath = get_file_path(filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()
