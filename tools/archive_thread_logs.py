#!/usr/bin/env python3
"""
Archive Thread Logs - Rolling 30-day archive system

Keeps only last 30 days of thread logs in thread_log.json and working_memory.json.
Archives older logs to data/thread_log_archive.json.
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
WORKING_MEMORY = PROJECT_ROOT / "data" / "working_memory.json"
THREAD_LOG = PROJECT_ROOT / "data" / "thread_log.json"
ARCHIVE_FILE = PROJECT_ROOT / "data" / "thread_log_archive.json"

def read_json(file_path):
    """Read JSON file"""
    if not file_path.exists():
        return {}
    with open(file_path, 'r') as f:
        return json.load(f)

def write_json(file_path, data):
    """Write JSON file"""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

def archive_old_logs():
    """Archive thread logs older than 30 days from both thread_log.json and working_memory.json"""
    # Read thread log file
    thread_log_data = read_json(THREAD_LOG)
    thread_entries = thread_log_data.get('entries', {})

    # Calculate cutoff date (30 days ago)
    cutoff_date = datetime.now() - timedelta(days=30)

    # Separate recent and old entries
    recent_entries = {}
    old_entries = {}

    for entry_key, entry_data in thread_entries.items():
        try:
            timestamp_str = entry_data.get('timestamp', '2000-01-01')
            log_date = datetime.fromisoformat(timestamp_str)

            if log_date >= cutoff_date:
                recent_entries[entry_key] = entry_data
            else:
                old_entries[entry_key] = entry_data
        except:
            # If parsing fails, keep in recent
            recent_entries[entry_key] = entry_data

    # Update thread_log.json with only recent entries
    thread_log_data['entries'] = recent_entries
    write_json(THREAD_LOG, thread_log_data)

    # Also handle working_memory.json thread logs if they exist
    working_memory = read_json(WORKING_MEMORY)
    thread_logs = working_memory.get('thread_logs', [])

    recent_logs = []
    old_logs = []

    for log in thread_logs:
        log_date = datetime.fromisoformat(log.get('timestamp', '2000-01-01'))
        if log_date >= cutoff_date:
            recent_logs.append(log)
        else:
            old_logs.append(log)

    working_memory['thread_logs'] = recent_logs
    write_json(WORKING_MEMORY, working_memory)

    # Append old logs to archive
    total_archived = 0
    if old_entries or old_logs:
        archive = read_json(ARCHIVE_FILE)

        # Archive old entries from thread_log.json
        archived_entries = archive.get('archived_entries', {})
        archived_entries.update(old_entries)
        archive['archived_entries'] = archived_entries

        # Archive old logs from working_memory.json
        archived_logs = archive.get('archived_logs', [])
        archived_logs.extend(old_logs)
        archive['archived_logs'] = archived_logs

        archive['last_archived'] = datetime.now().isoformat()
        archive['total_archived'] = len(archived_entries) + len(archived_logs)
        write_json(ARCHIVE_FILE, archive)

        total_archived = len(old_entries) + len(old_logs)

    return {
        "status": "success",
        "message": f"Archived {total_archived} logs older than 30 days",
        "archived_count": total_archived,
        "recent_entries_count": len(recent_entries),
        "recent_logs_count": len(recent_logs),
        "cutoff_date": cutoff_date.isoformat()
    }

def search_archive(keyword):
    """Search archived logs by keyword"""
    archive = read_json(ARCHIVE_FILE)
    archived_logs = archive.get('archived_logs', [])

    results = []
    for log in archived_logs:
        # Search in all string fields
        for key, value in log.items():
            if isinstance(value, str) and keyword.lower() in value.lower():
                results.append(log)
                break

    return {
        "status": "success",
        "results": results,
        "count": len(results)
    }

def main(action, params):
    """Main entry point"""
    if action == "archive_old_logs":
        return archive_old_logs()
    elif action == "search_archive":
        keyword = params.get('keyword', '')
        return search_archive(keyword)
    else:
        return {"status": "error", "message": f"Unknown action: {action}"}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({
            "status": "error",
            "message": "Usage: python3 archive_thread_logs.py <action> --params '{\"param\": \"value\"}'"
        }))
        sys.exit(1)

    action = sys.argv[1]
    params = {}

    if len(sys.argv) > 3 and sys.argv[2] == "--params":
        params = json.loads(sys.argv[3])

    result = main(action, params)
    print(json.dumps(result, indent=2))
