# System Flows Documentation

#Resources

This document describes the three major operational flows in OrchestrateOS. Understanding these flows is critical for debugging, optimization, and extending the system.

---

## Flow 1: Task Execution Flow

The core workflow for executing user tasks through the automation system.

### Sequence

1. **User initiates task** via GPT interface
2. **GPT calls execution_hub**
   - Endpoint: `http://localhost:5001/execute_task`
   - Tool: `claude_assistant`
   - Action: `assign_task`
   - Params: `task_id`, `description`, optional `batch_id`

3. **Task added to queue**
   - File: `data/claude_task_queue.json`
   - Status: `queued`
   - Task includes: description, context, priority, batch_id

4. **execute_queue triggered** (manually or via automation)
   - Creates lockfile: `data/execute_queue.lock`
   - Prevents concurrent sessions
   - Spawns Claude Code subprocess

5. **Claude subprocess processes tasks**
   - Reads queue via internal process_queue function
   - Marks each task `in_progress` before starting
   - Executes task using execution_hub.py for all tool calls
   - Writes telemetry before completion: `data/last_execution_telemetry.json`
   - Logs completion with status, actions_taken, output, errors

6. **Results logged**
   - File: `data/claude_task_results.json`
   - Includes: task_id, status, tokens (input/output), execution time
   - Task status updated to `done` or `error`

7. **Lockfile removed** when ALL tasks complete
   - Allows next batch to start
   - Removed by Claude session at end

### Dependencies

- `execution_hub.py` must be running (Flask server on port 5001)
- `data/claude_task_queue.json` must be writable
- CLAUDECODE env var must NOT be set (automation handles removal)

### Common Failure Points

- **Lockfile not removed**: Claude crashed before completion → manually `rm data/execute_queue.lock`
- **Task stuck in_progress**: Claude subprocess died → check logs, manually update status to `error`
- **Nested session error**: CLAUDECODE env var set → automation must use `env -u CLAUDECODE`
- **Missing telemetry**: Claude forgot to write before log_completion → token data incomplete

### Debugging

```bash
# Check if execution_hub is running
curl http://localhost:5001/get_supported_actions

# Check queue status
cat data/claude_task_queue.json | python3 -m json.tool

# Check if lockfile exists
ls -la data/execute_queue.lock

# Check recent results
tail -20 data/claude_task_results.json

# Check automation engine status
ps aux | grep automation_engine
```

---

## Flow 2: Outline Doc Creation Flow

The workflow for creating and importing documents into Outline knowledge base.

### Sequence

1. **Write markdown file**
   - Directory: `outline_docs_queue/`
   - Filename: `my-doc-title.md`
   - Content includes collection hashtag (e.g., `#Resources`)

2. **Add entry to queue**
   - File: `data/outline_queue.json`
   - **CRITICAL**: Entry MUST be inside `entries` object
   - Format:
   ```json
   {
     "entries": {
       "my-doc-key": {
         "title": "Doc Title",
         "file": "my-doc-title.md",
         "collection": "resources",
         "status": "queued",
         "created_at": "2025-11-07T12:00:00Z",
         "publish": true,
         "parent_doc_id": "technical-documents"
       }
     }
   }
   ```

3. **Automation detects event**
   - Tool: `automation_engine.py`
   - Trigger: `outline_entry_added` (detects `status: "queued"`)
   - Polls `data/outline_queue.json` for changes

4. **import_doc_from_file executed**
   - Tool: `outline_editor.py`
   - Action: `import_doc_from_file`
   - Params resolved from queue entry (file_path, collection, parent_doc_id, publish)

5. **Doc created in Outline**
   - Outline API returns doc_id
   - Document appears in correct collection
   - Parent relationship established if parent_doc_id provided

6. **Status updated in queue**
   - Entry status changed to `processed`
   - **Note**: doc_id is NOT written back (by design)
   - Timestamp added

### Dependencies

- `automation_engine.py` must be running
- `outline_docs_queue/` directory must exist
- `data/outline_queue.json` must have correct structure
- Collection aliases resolved via `data/outline_aliases.json`

### Common Failure Points

- **Entry not processed**:
  - Check entry is inside `entries` object (not top level)
  - Verify status is `queued` (not `pending`)
  - Confirm automation_engine is running

- **Wrong collection routing**:
  - Use aliases from outline_aliases.json
  - Add hashtag to markdown content
  - Verify collection name spelling

- **Duplicate documents**:
  - Multiple Claude sessions due to missing lockfile
  - Automation triggered multiple times
  - Check for duplicate entries in queue

- **File not found**:
  - Verify file path in queue matches actual file
  - Check file is in outline_docs_queue/ directory

### Debugging

```bash
# Check automation engine status
ps aux | grep automation_engine

# View automation engine logs
tail -f logs/automation_engine.log

# Check queue structure
cat data/outline_queue.json | python3 -m json.tool

# List files in docs queue
ls -la outline_docs_queue/

# Verify collection aliases
cat data/outline_aliases.json | python3 -m json.tool

# Check if entry was processed (status changed)
cat data/outline_queue.json | grep -A 10 "my-doc-key"
```

### Verification Process

After adding entry with `status: "queued"`:
1. Wait 10-15 seconds
2. Re-read `data/outline_queue.json`
3. Verify status changed to `processed`
4. Check Outline web UI for new document

If status still `queued`, automation failed.

---

## Flow 3: Batch Processing Flow

Optimized workflow for processing multiple related tasks with shared context.

### Sequence

1. **Generate batch_id**
   - Format: `batch_YYYYMMDD_HHMMSS`
   - Example: `batch_20251107_214500`
   - ONE batch_id for all related tasks

2. **Assign tasks with same batch_id**
   - Call `assign_task` multiple times
   - Pass same `batch_id` to each call
   - Set `auto_execute=false` for all except last task
   - Last task triggers execution

3. **execute_queue creates lockfile**
   - File: `data/execute_queue.lock`
   - Prevents concurrent sessions
   - Returns `already_running` if lockfile exists

4. **Single Claude session spawned**
   - ONE subprocess for entire batch
   - Shared context across all tasks
   - Sequential processing (maintains order)

5. **Tasks processed with shared context**
   - First task: full context loaded (all input tokens)
   - Subsequent tasks: incremental context only (0 additional input tokens)
   - Each task marked `in_progress` → work done → `completed`

6. **Telemetry with token sharing**
   - First task: tokens_input = 40K (full context)
   - Task 2: tokens_input = 0 (shared context)
   - Task 3: tokens_input = 0 (shared context)
   - Total input tokens = 40K (not 120K)
   - Massive token savings

7. **Lockfile removed when ALL tasks complete**
   - Claude removes lockfile at session end
   - Next batch can now start

### Dependencies

- All tasks must have same batch_id
- Tasks must be assigned before execute_queue called
- Lockfile must not exist (previous batch must be complete)

### Common Failure Points

- **Concurrent batches**:
  - Two batches assigned simultaneously
  - Second batch gets `already_running`
  - Wait for first batch to complete

- **Lockfile not removed**:
  - Claude crashed mid-batch
  - Manually remove: `rm data/execute_queue.lock`
  - Check logs for crash reason

- **Batch split across sessions**:
  - Different batch_ids used
  - auto_execute=true on early tasks
  - Context not shared, tokens wasted

- **Missing batch_position**:
  - Tasks not logged with position
  - Telemetry incomplete
  - Cannot track token sharing

### Debugging

```bash
# Check if batch is running
ls -la data/execute_queue.lock

# View tasks in batch
cat data/claude_task_queue.json | grep -B 2 -A 10 "batch_20251107"

# Check batch telemetry
cat data/claude_task_results.json | grep -B 2 -A 10 "batch_20251107"

# Calculate token savings
# First task tokens_input: X
# Subsequent tasks tokens_input: 0
# Savings = (X * num_tasks) - X

# Monitor batch execution
tail -f logs/execution_hub.log
```

### Token Optimization

**Without batching:**
- Task 1: 40K input tokens
- Task 2: 40K input tokens
- Task 3: 40K input tokens
- **Total: 120K input tokens**

**With batching:**
- Task 1: 40K input tokens
- Task 2: 0 input tokens (shared)
- Task 3: 0 input tokens (shared)
- **Total: 40K input tokens**
- **Savings: 80K tokens (67%)**

---

## Component Dependencies

### Critical Files

- `execution_hub.py`: Flask server, task routing
- `automation_engine.py`: Event detection, rule execution
- `outline_editor.py`: Outline API wrapper
- `data/claude_task_queue.json`: Active task queue
- `data/claude_task_results.json`: Completed task results
- `data/outline_queue.json`: Outline doc import queue
- `data/outline_aliases.json`: Collection/parent doc aliases
- `data/execute_queue.lock`: Batch execution lockfile

### Running Services

- **execution_hub** (Flask on :5001): Always running
- **automation_engine**: Always running, event loop
- **Claude Code subprocess**: Spawned on-demand by execute_queue

### Environment Requirements

- Python 3.9+
- CLAUDECODE env var NOT set (automation handles)
- Write access to data/ directory
- Outline API token configured

---

## Quick Reference

### Create a task

```bash
curl -X POST http://localhost:5001/execute_task \
  -H 'Content-Type: application/json' \
  -d '{
    "tool_name": "claude_assistant",
    "action": "assign_task",
    "params": {
      "task_id": "my_task_id",
      "description": "Do something",
      "batch_id": "batch_20251107_120000"
    }
  }'
```

### Create Outline doc (queue method)

1. Write file: `outline_docs_queue/my-doc.md`
2. Update queue:
```json
{
  "entries": {
    "my-doc": {
      "title": "My Doc",
      "file": "my-doc.md",
      "collection": "resources",
      "status": "queued",
      "publish": true
    }
  }
}
```

### Check system status

```bash
# Execution hub
curl http://localhost:5001/get_supported_actions

# Automation engine
ps aux | grep automation_engine

# Active batch
ls -la data/execute_queue.lock

# Recent tasks
tail -20 data/claude_task_queue.json
```
