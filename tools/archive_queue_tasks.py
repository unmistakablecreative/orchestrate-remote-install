#!/usr/bin/env python3
"""
Archive completed tasks from claude_task_queue.json to reduce context bloat.
"""

import json
import os
from datetime import datetime

def read_json(filepath):
    """Read JSON file"""
    if not os.path.exists(filepath):
        return {}
    with open(filepath, 'r') as f:
        return json.load(f)

def write_json(filepath, data):
    """Write JSON file with proper formatting"""
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def archive_completed_tasks():
    """Archive completed tasks from queue"""

    # Paths
    queue_file = os.path.expanduser("~/Orchestrate Github/orchestrate-jarvis/")
    archive_file = os.path.expanduser("~/Orchestrate Github/orchestrate-jarvis/")

    # Read current queue
    queue_data = read_json(queue_file)
    tasks = queue_data.get('tasks', {})

    # Read existing archive
    archive_data = read_json(archive_file)
    if 'archived_tasks' not in archive_data:
        archive_data = {'archived_tasks': {}, 'last_archived': None, 'total_archived': 0}

    # Separate active and completed tasks
    active_tasks = {}
    completed_tasks = {}

    for task_id, task_data in tasks.items():
        status = task_data.get('status', 'queued')
        if status in ['done', 'error', 'cancelled']:
            completed_tasks[task_id] = task_data
        else:
            active_tasks[task_id] = task_data

    # Add completed tasks to archive
    archive_data['archived_tasks'].update(completed_tasks)
    archive_data['last_archived'] = datetime.now().isoformat()
    archive_data['total_archived'] = len(archive_data['archived_tasks'])

    # Write archive
    write_json(archive_file, archive_data)

    # Write cleaned queue with only active tasks
    queue_data['tasks'] = active_tasks
    write_json(queue_file, queue_data)

    # Return stats
    return {
        'status': 'success',
        'archived_count': len(completed_tasks),
        'remaining_count': len(active_tasks),
        'total_in_archive': archive_data['total_archived'],
        'message': f'Archived {len(completed_tasks)} completed tasks. {len(active_tasks)} active tasks remain in queue.'
    }

if __name__ == '__main__':
    result = archive_completed_tasks()
    print(json.dumps(result, indent=2))
