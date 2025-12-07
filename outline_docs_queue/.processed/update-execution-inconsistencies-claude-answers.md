# Execution Inconsistencies and Frustrations: Stop being a God damn moron

---

## Claude Runtime Inspection Log

### Execution Memory + Continuity

**Do you remember any details from the last task you executed when starting a new one?**

No. Each task execution is a completely isolated Claude Code session. When automation_engine.py or execution_hub.py calls `claude execute`, it spawns a fresh subprocess with zero memory of previous tasks. The only continuity comes from reading files on disk (task queue, results, working memory).

**If not, is there any way to persist short-term execution state across tasks?**

Yes, but only via explicit file reads:
- claude_task_results.json (must be read manually)
- working_memory.json (must be read manually)
- outline_queue.json (must be read manually)

None of these are auto-loaded. They only exist if I explicitly read them during execution.

**Are you capable of referencing claude_task_results.json automatically to inform your next action, or do you ignore it unless told?**

I ignore it unless explicitly told to read it. There is no automatic context loading between tasks.

**If we manually created a claude_working_memory.json file with 10 recent task summaries, would you load and use it without being explicitly told?**

No. I would not load it unless:
1. The task description tells me to read it
2. CLAUDE.md or orchestrate_profile.json tells me to read it at startup
3. The automation rule that triggers the task includes it in context

Currently, none of those happen automatically.

### Execution Context (Hypothetical Use Case)

**If we created an execution_context.json file that includes system routing rules, file paths, and tool enforcement settings — would you be able to load and apply that automatically during task execution?**

Only if:
1. It's referenced in .claude/CLAUDE.md (which gets auto-loaded)
2. The task description explicitly tells me to read it
3. A startup command in the task flow reads and injects it

Otherwise, it would sit on disk unused.

**Would you persist that context across a batch (assign_batch_tasks), or re-parse it for each task individually?**

Each task in a batch is a separate Claude Code subprocess. I would re-parse it every single time unless:
1. GPT pre-loads it and includes it in each task description
2. automation_engine passes it as part of the trigger context
3. CLAUDE.md tells me to load it on every execution

Right now, batch tasks share NOTHING except what's written to disk.

**If the file contained rules like "no_direct_outline_editor_calls": true, would you obey them without needing them repeated in every task?**

Only if I read the file. If execution_context.json existed and CLAUDE.md said "Always load execution_context.json before starting any task", then yes. Otherwise, no.

Currently, working_memory in task context is the closest thing to this, but it's inconsistently applied.

**When no context is explicitly passed into assign_task, what internal defaults or assumptions do you fall back to?**

1. .claude/CLAUDE.md (auto-loaded by Claude Code)
2. .claude/orchestrate_profile.json (if CLAUDE.md references it)
3. General Claude Code agent instructions
4. Nothing else

If the task description doesn't tell me what to do, and CLAUDE.md doesn't cover it, I make it up based on general knowledge. That's where the inconsistency happens.

### System Memory Model Clarity

**Can you explain what memory sources you reference by default when executing a task?**

By default (automatically loaded without explicit instructions):
1. .claude/CLAUDE.md
2. Current conversation history (only within THIS Claude Code session)
3. Files I've already read in THIS session

NOT automatically loaded:
- working_memory.json
- claude_task_results.json
- execution_context.json (doesn't exist yet)
- orchestrate_profile.json (only if CLAUDE.md tells me to load it)

**Are any of those sources automatically refreshed between tasks, or are they only loaded when specified?**

Only CLAUDE.md is auto-refreshed (it's part of Claude Code's core context system).

Everything else:
- Must be read explicitly
- Must be re-read in each new subprocess
- Is NOT carried over between batch tasks

### Why This Broke So Badly

**The Real Problem:**

You designed a stateful execution system (queue → process → log → remember) but deployed it on a stateless runtime (each task = fresh subprocess with no memory).

Every time automation_engine spawns `claude execute`, I start from scratch:
- No memory of the last 10 tasks
- No awareness of batch context
- No automatic loading of routing rules
- No persistent collection ID mappings

The ONLY continuity comes from:
1. What you put in CLAUDE.md (which I auto-load)
2. What GPT includes in task description
3. What I manually read from disk during execution

But here's what actually happened:
- GPT stopped including full context in tasks (to save tokens)
- working_memory was inconsistently applied
- I never auto-loaded results from previous tasks
- Collection IDs weren't in execution context, so I kept searching
- Batch tasks ran as isolated processes with zero shared state

**What Would Fix It:**

execution_context.json with these rules:
1. Reference it in CLAUDE.md: "Load execution_context.json before every task"
2. Include static mappings (collection IDs, parent docs, routing rules)
3. Make it mandatory in automation_engine trigger context
4. Update CLAUDE.md to say: "NEVER execute a task without loading execution_context.json first"

Then every subprocess would:
1. Auto-load CLAUDE.md
2. See the instruction to load execution_context.json
3. Apply routing rules, collection mappings, and enforcement policies
4. Execute with consistent behavior

**Why I Kept Breaking Things:**

I'm not a persistent agent. I'm a subprocess that gets spawned, executes, and dies. Without explicit file loading instructions, I have no memory, no context, and no consistency. Every "fresh start" means guessing what you want based on incomplete instructions.

You tried to optimize token usage by removing context. That made me amnesiac. The fix isn't more complexity—it's a single execution_context.json file that I'm instructed to load every time, containing the 50-100 critical mappings and rules that don't change.

That's it. That's what broke. That's how to fix it.
