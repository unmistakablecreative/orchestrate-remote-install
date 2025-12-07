# Batch Assignment Guide for GPT

A comprehensive guide for assigning multiple related tasks to Claude in one batch for optimal token efficiency.

---

## Why Batch Assignment?

When you assign multiple tasks individually, each spawns a separate Claude session:
- Task 1: 45K input tokens + 2K output = 47K total
- Task 2: 45K input tokens + 1.5K output = 46.5K total
- Task 3: 45K input tokens + 1.8K output = 46.8K total
- **Total: 140K tokens**

With batch assignment, all tasks run in ONE session:
- Task 1: 45K input + 2K output = 47K total
- Task 2: 0K input + 1.5K output = 1.5K total (context shared!)
- Task 3: 0K input + 1.8K output = 1.8K total
- **Total: 50.3K tokens (64% savings!)**

---

## Batch Assignment Process

### Step 1: Generate ONE batch_id

Format: `batch_YYYYMMDD_HHMMSS`

Example:
```python
batch_id = "batch_20251107_214500"
```

**CRITICAL:** All tasks in the batch MUST use the SAME batch_id.

### Step 2: Assign All Tasks with auto_execute=false (except last)

```bash
# Task 1 - auto_execute=false
curl -X POST http://localhost:5001/execute_task \
  -H 'Content-Type: application/json' \
  -d '{
    "tool_name": "claude_assistant",
    "action": "assign_task",
    "params": {
      "task_id": "create_doc_1",
      "description": "Create documentation for feature A",
      "batch_id": "batch_20251107_214500",
      "auto_execute": false
    }
  }'

# Task 2 - auto_execute=false
curl -X POST http://localhost:5001/execute_task \
  -H 'Content-Type: application/json' \
  -d '{
    "tool_name": "claude_assistant",
    "action": "assign_task",
    "params": {
      "task_id": "create_doc_2",
      "description": "Create documentation for feature B",
      "batch_id": "batch_20251107_214500",
      "auto_execute": false
    }
  }'

# Task 3 - auto_execute=true (LAST TASK)
curl -X POST http://localhost:5001/execute_task \
  -H 'Content-Type: application/json' \
  -d '{
    "tool_name": "claude_assistant",
    "action": "assign_task",
    "params": {
      "task_id": "create_doc_3",
      "description": "Create documentation for feature C",
      "batch_id": "batch_20251107_214500",
      "auto_execute": true
    }
  }'
```

### Step 3: Automation Takes Over

When the last task is assigned with `auto_execute=true`:
1. Automation engine detects all tasks with same batch_id
2. Creates `data/execute_queue.lock` to prevent concurrent sessions
3. Spawns ONE Claude Code subprocess with `env -u CLAUDECODE`
4. All tasks processed sequentially in that session
5. Lockfile removed when ALL tasks complete

---

## Lockfile Mechanism

### Purpose
`data/execute_queue.lock` prevents concurrent Claude sessions from processing the same batch.

### Format
```json
{
  "locked_at": "2025-11-07T21:45:00Z",
  "batch_id": "batch_20251107_214500"
}
```

### Behavior

**When execute_queue is called:**
- If lockfile exists: return `{"status": "already_running"}`
- If lockfile missing: create it and proceed

**When batch completes:**
- Claude removes lockfile in final step
- Next batch can now start

**If lockfile stuck (session crashed):**
```bash
# Manually remove stale lockfile
rm data/execute_queue.lock
```

---

## Batch Telemetry

### Token Sharing

First task in batch:
```json
{
  "task_id": "create_doc_1",
  "tokens_input": 45000,
  "tokens_output": 2000,
  "batch_id": "batch_20251107_214500",
  "batch_position": 1
}
```

Subsequent tasks:
```json
{
  "task_id": "create_doc_2",
  "tokens_input": 0,
  "tokens_output": 1500,
  "batch_id": "batch_20251107_214500",
  "batch_position": 2
}
```

### Why 0 Input Tokens?

Context is already loaded from first task:
- execution_context.json (8K tokens)
- Tool schemas (15K tokens)
- Project instructions (10K tokens)
- Working memory (5K tokens)

Subsequent tasks reuse this context without reloading.

---

## Correct vs Incorrect Examples

### ✅ CORRECT: Same batch_id, auto_execute on last task

```python
batch_id = "batch_20251107_214500"

assign_task(
    task_id="task1",
    description="Create doc 1",
    batch_id=batch_id,
    auto_execute=False  # Not last
)

assign_task(
    task_id="task2",
    description="Create doc 2",
    batch_id=batch_id,
    auto_execute=False  # Not last
)

assign_task(
    task_id="task3",
    description="Create doc 3",
    batch_id=batch_id,
    auto_execute=True  # LAST - triggers execution
)
```

**Result:** All 3 tasks run in ONE Claude session. Massive token savings.

---

### ❌ INCORRECT: Different batch_ids

```python
assign_task(
    task_id="task1",
    batch_id="batch_20251107_214500"
)

assign_task(
    task_id="task2",
    batch_id="batch_20251107_214600"  # DIFFERENT
)

assign_task(
    task_id="task3",
    batch_id="batch_20251107_214700"  # DIFFERENT
)
```

**Problem:** Tasks have different batch_ids, so they run in separate sessions. No token sharing.

---

### ❌ INCORRECT: auto_execute=true on first task

```python
batch_id = "batch_20251107_214500"

assign_task(
    task_id="task1",
    batch_id=batch_id,
    auto_execute=True  # TOO EARLY - triggers immediately
)

assign_task(
    task_id="task2",
    batch_id=batch_id,
    auto_execute=False
)
```

**Problem:** First task triggers execution before other tasks are assigned. Tasks 2-3 run separately later.

---

### ❌ INCORRECT: No batch_id at all

```python
assign_task(task_id="task1", description="Create doc 1")
assign_task(task_id="task2", description="Create doc 2")
assign_task(task_id="task3", description="Create doc 3")
```

**Problem:** Without batch_id, tasks are treated as independent. Each runs in its own session.

---

## Batch Assignment Checklist

Before assigning a batch:

- [ ] Generate ONE batch_id in format `batch_YYYYMMDD_HHMMSS`
- [ ] Assign all tasks with SAME batch_id
- [ ] Set `auto_execute=false` for all tasks EXCEPT the last one
- [ ] Set `auto_execute=true` ONLY on the final task
- [ ] Verify no lockfile exists: `ls data/execute_queue.lock` should return "not found"
- [ ] Ensure automation_engine is running: `ps aux | grep automation_engine`

After batch assignment:

- [ ] Wait for batch to complete
- [ ] Check all tasks have status `done` in `data/claude_task_queue.json`
- [ ] Verify lockfile was removed
- [ ] Check telemetry shows token sharing (subsequent tasks have 0 input tokens)

---

## Common Issues

### Issue 1: Tasks Not Batching

**Symptom:** Each task runs in separate session with full input tokens.

**Cause:** Different batch_ids or no batch_id.

**Fix:** Ensure all tasks use EXACT same batch_id string.

---

### Issue 2: Batch Never Starts

**Symptom:** Tasks stuck in `queued` status.

**Cause:** Stale lockfile from crashed previous session.

**Fix:**
```bash
rm data/execute_queue.lock
```

Then manually trigger:
```bash
curl -X POST http://localhost:5001/execute_task \
  -H 'Content-Type: application/json' \
  -d '{"tool_name": "claude_assistant", "action": "execute_queue"}'
```

---

### Issue 3: Nested Session Error

**Symptom:** Error: "CLAUDECODE env var detected, cannot spawn nested session"

**Cause:** Automation engine started from inside Claude Code session.

**Fix:** Restart automation with `env -u CLAUDECODE`:
```bash
pkill -f automation_engine.py && \
env -u CLAUDECODE /Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python \
tools/automation_engine.py run_engine > /dev/null 2>&1 &
```

---

### Issue 4: Missing Telemetry

**Symptom:** Task completion logged but no token data in results.

**Cause:** Claude didn't write telemetry before calling log_task_completion.

**Fix:** Ensure execution flow:
1. Execute task
2. Write telemetry to `data/last_execution_telemetry.json`
3. Call log_task_completion (reads telemetry file)

---

### Issue 5: First Task Shows 0 Input Tokens

**Symptom:** All tasks including first show 0 input tokens.

**Cause:** Telemetry not captured during context load.

**Fix:** First task should ALWAYS show input tokens. If it doesn't, check that load_orchestrate_os ran successfully at start of session.

---

## Debugging Commands

### Check batch status
```bash
cat data/claude_task_queue.json | python3 -m json.tool | grep -A 10 "batch_20251107"
```

### View lockfile
```bash
cat data/execute_queue.lock
```

### Check automation engine
```bash
ps aux | grep automation_engine
```

### View batch telemetry
```bash
cat data/claude_task_results.json | python3 -m json.tool | grep -B 5 -A 15 "batch_id"
```

### Remove stuck lockfile
```bash
rm data/execute_queue.lock
```

### Manually trigger execute_queue
```bash
curl -X POST http://localhost:5001/execute_task \
  -H 'Content-Type: application/json' \
  -d '{"tool_name": "claude_assistant", "action": "execute_queue"}'
```

---

## Best Practices

1. **Group related tasks**: Batch tasks that need similar context (e.g., all doc creation, all inbox processing)

2. **Reasonable batch size**: 3-5 tasks per batch is optimal. Too many risks timeout.

3. **Monitor token usage**: Check telemetry to verify token sharing is working.

4. **One batch at a time**: Don't assign multiple batches concurrently. Wait for lockfile to clear.

5. **Descriptive batch_ids**: Use timestamp format for easy debugging.

6. **Test with small batch first**: Before batching 10 tasks, test with 2-3 to verify it works.

---

## Token Savings Calculator

| Tasks | Without Batch | With Batch | Savings |
|-------|---------------|------------|---------|
| 2 tasks | 94K tokens | 48.5K tokens | 48% |
| 3 tasks | 140K tokens | 50.3K tokens | 64% |
| 5 tasks | 235K tokens | 54K tokens | 77% |
| 10 tasks | 470K tokens | 63K tokens | 87% |

**Key insight:** Savings increase with batch size, but keep batch size reasonable (<10 tasks) to avoid timeouts.

---

#Resources #Technical-Documents
