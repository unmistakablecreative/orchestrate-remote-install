# EXECUTION ENGINE - CRITICAL ARCHITECTURE

## DO NOT FUCKING TOUCH THIS WITHOUT READING FIRST

You have broken this exact system 30+ times. Read this EVERY TIME before modifying execute_queue or process_queue.

---

## THE CORE FLOW (DO NOT CHANGE)

### 1. execute_queue() - Called by automation engine watcher
**Purpose:** Check for queued tasks and spawn Claude Code session to process them

**CRITICAL RULES:**
- **DO NOT call process_queue()** - This marks tasks as in_progress
- **ONLY COUNT queued tasks** - Read the queue file and count status="queued"
- **Spawn Claude Code** - Let the spawned session call process_queue
- **Create lockfile** - Prevent race conditions

**Code pattern:**
```python
# ✅ CORRECT - Just count, don't modify
task_count = sum(1 for task_data in queue.get("tasks", {}).values()
                 if task_data.get("status") == "queued")

if task_count == 0:
    return {"status": "success", "message": "No tasks"}

# Create lockfile
# Spawn Claude Code process
# Return immediately
```

**❌ WRONG - DO NOT DO THIS:**
```python
# This marks tasks as in_progress BEFORE spawning Claude
result = process_queue(params)  # ❌ NEVER CALL THIS IN execute_queue
```

---

### 2. process_queue() - Called by spawned Claude Code session
**Purpose:** Return queued tasks AND mark them as in_progress

**CRITICAL RULES:**
- **Auto-marks tasks as in_progress** - Sets status and started_at timestamp
- **Returns task list** - For Claude to process
- **Called ONLY by spawned Claude session** - Never by execute_queue

**Code pattern:**
```python
# ✅ CORRECT - Marks as in_progress and returns
for task_id, task_data in queue.get("tasks", {}).items():
    if task_data.get("status") == "queued":
        queue["tasks"][task_id]["status"] = "in_progress"
        queue["tasks"][task_id]["started_at"] = now
        pending.append(task_data)
```

---

## WHY THIS MATTERS

**The Problem:**
If execute_queue calls process_queue:
1. execute_queue calls process_queue → marks tasks as "in_progress"
2. Spawns Claude Code
3. Claude Code calls process_queue → sees no "queued" tasks (they're all "in_progress")
4. Returns "Queue is empty"
5. Task never gets processed

**The Fix:**
1. execute_queue ONLY counts queued tasks (read-only check)
2. Spawns Claude Code
3. Claude Code calls process_queue → marks as in_progress and returns tasks
4. Tasks get processed

---

## WHAT YOU KEEP BREAKING

### Mistake #1: Calling process_queue in execute_queue
```python
# ❌ YOU KEEP DOING THIS
def execute_queue(params):
    result = process_queue(params)  # WRONG - marks tasks
    # spawn Claude...
```

### Mistake #2: Removing the count logic
```python
# ❌ YOU KEEP REMOVING THIS
task_count = sum(1 for task_data in queue.get("tasks", {}).values()
                 if task_data.get("status") == "queued")
```

### Mistake #3: Not understanding the two-phase design
- **Phase 1 (execute_queue):** Count tasks, spawn Claude
- **Phase 2 (process_queue):** Mark in_progress, return tasks

---

## THE LOCKFILE

**Purpose:** Prevent multiple execute_queue sessions from spawning concurrent Claude processes

**Flow:**
1. Check if lockfile exists
2. Validate PID is still running
3. Remove stale lockfiles (>30min or dead PID)
4. Create lockfile before spawning Claude
5. Claude removes lockfile when done

---

## FILES INVOLVED

- `tools/claude_assistant.py` - execute_queue() and process_queue()
- `tools/claude_execution_engine.py` - Watches queue, calls execute_queue
- `data/claude_task_queue.json` - Task queue
- `data/execute_queue.lock` - Prevents race conditions
- `data/claude_execution.log` - Spawned Claude output

---

## TESTING CHECKLIST

Before committing changes to execute_queue or process_queue:

1. ✅ execute_queue does NOT call process_queue
2. ✅ execute_queue counts tasks without modifying status
3. ✅ Spawned Claude calls process_queue successfully
4. ✅ Tasks get marked as in_progress by spawned Claude
5. ✅ Lockfile prevents concurrent executions
6. ✅ Stale lockfiles get cleaned up

---

## IF YOU BREAK IT AGAIN

1. Read this file
2. Check git diff tools/claude_assistant.py
3. Look for process_queue() calls in execute_queue()
4. Restore the count-only logic
5. Test with a real task

---

**Last broken:** 2025-11-09 (30+ times total)
**Root cause:** Calling process_queue in execute_queue, which marks tasks before spawning Claude
