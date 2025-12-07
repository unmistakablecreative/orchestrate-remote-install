#!/usr/bin/env python3
"""
Archive old doc tracking entries and maintain recent 20 in CLAUDE.md
"""

import os
import json
from datetime import datetime
from pathlib import Path

def get_doc_metadata(doc_path):
    """Extract metadata from a processed doc file"""
    try:
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Get first non-empty line as summary
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        summary = lines[0][:200] if lines else "No content"

        # Get file stats
        stats = os.stat(doc_path)
        created_date = datetime.fromtimestamp(stats.st_mtime)

        return {
            "filename": os.path.basename(doc_path),
            "created": created_date.strftime("%Y-%m-%d"),
            "summary": summary,
            "size": stats.st_size
        }
    except Exception as e:
        return None

def archive_doc_tracking():
    """Main function to archive doc tracking"""

    # Paths
    project_root = Path("$HOME/Orchestrate Github/orchestrate-jarvis")
    processed_dir = project_root / "outline_docs_queue" / ".processed"
    archive_file = project_root / ".claude" / "archive" / "doc_history.json"
    claude_md = project_root / ".claude" / "CLAUDE.md"

    # Ensure archive directory exists
    archive_file.parent.mkdir(parents=True, exist_ok=True)

    # Get all processed docs sorted by date (newest first)
    docs = []
    for doc_file in processed_dir.glob("*.md"):
        metadata = get_doc_metadata(doc_file)
        if metadata:
            docs.append(metadata)

    # Sort by creation date (newest first)
    docs.sort(key=lambda x: x['created'], reverse=True)

    print(f"Found {len(docs)} processed documents")

    # Split into recent and archived
    recent_docs = docs[:20]
    archived_docs = docs[20:]

    print(f"Keeping {len(recent_docs)} recent, archiving {len(archived_docs)} older docs")

    # Load existing archive if it exists
    existing_archive = []
    if archive_file.exists():
        try:
            with open(archive_file, 'r') as f:
                data = json.load(f)
                # Handle both list and dict formats
                if isinstance(data, list):
                    existing_archive = data
                elif isinstance(data, dict):
                    existing_archive = []
        except:
            existing_archive = []

    # Merge archives (avoid duplicates)
    existing_filenames = {doc['filename'] for doc in existing_archive}
    for doc in archived_docs:
        if doc['filename'] not in existing_filenames:
            existing_archive.append(doc)

    # Sort archive by date
    existing_archive.sort(key=lambda x: x['created'], reverse=True)

    # Write archive
    with open(archive_file, 'w') as f:
        json.dump(existing_archive, f, indent=2)

    print(f"Archived {len(existing_archive)} total documents to {archive_file}")

    # Generate updated CLAUDE.md section
    doc_section = "## Doc Tracking Protocol\n\n"
    doc_section += "**Every Outline doc created gets logged here:**\n\n"
    doc_section += "### Recent Outline Docs (Last 20)\n\n"

    for doc in recent_docs:
        # Clean up filename for display
        display_name = doc['filename'].replace('.md', '').replace('-', ' ').title()
        doc_section += f"**{doc['filename']}** ({doc['created']})\n"
        doc_section += f"- {doc['summary']}\n\n"

    doc_section += f"**Older docs archived to `.claude/archive/doc_history.json` ({len(existing_archive)} entries)**\n"

    # Read current CLAUDE.md
    with open(claude_md, 'r') as f:
        content = f.read()

    # Find and replace doc tracking section
    start_marker = "## Doc Tracking Protocol"
    end_marker = "## Copywriting Framework"

    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)

    if start_idx != -1 and end_idx != -1:
        # Replace section
        new_content = content[:start_idx] + doc_section + "\n---\n\n" + content[end_idx:]

        # Write updated CLAUDE.md
        with open(claude_md, 'w') as f:
            f.write(new_content)

        print(f"Updated CLAUDE.md with {len(recent_docs)} recent docs")
    else:
        print("Could not find doc tracking section markers in CLAUDE.md")

    return {
        "status": "success",
        "recent_count": len(recent_docs),
        "archived_count": len(existing_archive),
        "archive_file": str(archive_file)
    }

if __name__ == "__main__":
    result = archive_doc_tracking()
    print(json.dumps(result, indent=2))
