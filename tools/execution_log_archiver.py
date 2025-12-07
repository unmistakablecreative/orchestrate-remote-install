#!/usr/bin/env python3
"""
Execution Log Archiver

Rotates execution_log.json daily to prevent corruption from massive file growth.
Writes to NDJSON archive (append-only, no corruption risk).
"""

import json
import os
import glob
from datetime import datetime, timedelta

def archive_execution_log(params=None):
    """
    Archive execution_log.json to daily NDJSON files.

    Process:
    1. Read current execution_log.json
    2. Group executions by date
    3. Append to date-specific NDJSON archives (data/execution_archive/YYYY-MM-DD.ndjson)
    4. Clear old entries from execution_log.json (keep last 24 hours only)

    NDJSON format prevents corruption - each line is independent JSON object.
    If write fails mid-stream, only that line is lost, not entire file.

    Returns:
        Stats on archived entries
    """
    params = params or {}
    retention_days = params.get("retention_days", 1)  # Keep last N days in main log

    log_file = os.path.join(os.getcwd(), "data/execution_log.json")
    archive_dir = os.path.join(os.getcwd(), "data/execution_archive")

    os.makedirs(archive_dir, exist_ok=True)

    if not os.path.exists(log_file):
        return {
            "status": "success",
            "message": "No execution_log.json to archive"
        }

    # Read current log
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
    except json.JSONDecodeError as e:
        # Log is corrupted - try to salvage what we can
        return {
            "status": "error",
            "message": f"execution_log.json is corrupted: {str(e)}",
            "recommendation": "Run repair_corrupted_log first"
        }

    executions = log_data.get("executions", [])

    if not executions:
        return {
            "status": "success",
            "message": "No executions to archive"
        }

    # Group by date
    by_date = {}
    cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d")
    recent_entries = []

    for entry in executions:
        timestamp = entry.get("timestamp", "")
        try:
            entry_date = timestamp[:10]  # YYYY-MM-DD
        except:
            continue

        # Keep recent entries in main log
        if entry_date >= cutoff_date:
            recent_entries.append(entry)
        else:
            # Archive older entries
            if entry_date not in by_date:
                by_date[entry_date] = []
            by_date[entry_date].append(entry)

    # Write to NDJSON archives (one file per date)
    archived_count = 0
    for date, entries in by_date.items():
        archive_file = os.path.join(archive_dir, f"{date}.ndjson")

        # Append to existing archive (NDJSON is append-safe)
        with open(archive_file, 'a', encoding='utf-8') as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
                archived_count += 1

    # Rewrite main log with only recent entries
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump({"executions": recent_entries}, f, indent=2)

    return {
        "status": "success",
        "message": f"✅ Archived {archived_count} entries across {len(by_date)} dates",
        "archived_entries": archived_count,
        "archived_dates": list(by_date.keys()),
        "retained_entries": len(recent_entries),
        "archive_location": archive_dir
    }


def read_archived_executions(start_date, end_date):
    """
    Read executions from NDJSON archives for a date range.

    Args:
        start_date: YYYY-MM-DD
        end_date: YYYY-MM-DD

    Returns:
        List of execution entries
    """
    archive_dir = os.path.join(os.getcwd(), "data/execution_archive")

    if not os.path.exists(archive_dir):
        return []

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    executions = []

    # Read each date's archive
    current = start
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        archive_file = os.path.join(archive_dir, f"{date_str}.ndjson")

        if os.path.exists(archive_file):
            with open(archive_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        executions.append(entry)
                    except:
                        # Skip corrupted lines (NDJSON advantage - one bad line doesn't kill whole file)
                        continue

        current += timedelta(days=1)

    return executions


def repair_corrupted_log(params=None):
    """
    Attempt to salvage data from corrupted execution_log.json.

    Strategy:
    1. Try to read as much valid JSON as possible
    2. Extract individual execution entries
    3. Write salvaged data to new file
    4. Move corrupted file to backup

    Returns:
        Stats on salvaged entries
    """
    log_file = os.path.join(os.getcwd(), "data/execution_log.json")

    if not os.path.exists(log_file):
        return {"status": "error", "message": "No execution_log.json found"}

    # Backup corrupted file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(os.getcwd(), f"data/execution_log_corrupt_{timestamp}.json")

    with open(log_file, 'r', encoding='utf-8') as f:
        raw_content = f.read()

    # Try to extract execution objects using regex
    import re

    # Pattern to match execution entries
    pattern = r'\{\s*"tool":\s*"[^"]*".*?\}'

    matches = re.findall(pattern, raw_content, re.DOTALL)

    salvaged = []
    for match in matches:
        try:
            entry = json.loads(match)
            if "tool" in entry and "timestamp" in entry:
                salvaged.append(entry)
        except:
            continue

    if not salvaged:
        return {
            "status": "error",
            "message": "Could not salvage any valid entries",
            "backup_file": backup_file
        }

    # Move corrupted file to backup
    os.rename(log_file, backup_file)

    # Write salvaged data
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump({"executions": salvaged}, f, indent=2)

    return {
        "status": "success",
        "message": f"✅ Salvaged {len(salvaged)} entries from corrupted log",
        "salvaged_count": len(salvaged),
        "backup_file": backup_file,
        "recommendation": "Run archive_execution_log to move old entries to NDJSON"
    }


def main():
    """CLI entry point"""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Manage execution log archives")
    parser.add_argument('action', choices=['archive', 'repair'],
                       help='Action to perform')
    parser.add_argument('--retention-days', type=int, default=1,
                       help='Days to keep in main log (default: 1)')

    args = parser.parse_args()

    if args.action == 'archive':
        result = archive_execution_log({"retention_days": args.retention_days})
    elif args.action == 'repair':
        result = repair_corrupted_log()

    print(json.dumps(result, indent=2))

    sys.exit(0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()
