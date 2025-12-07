# CRITICAL: REPOSITORY CONTEXT

**orchestrate-jarvis** = Srini's personal local repo (99% of work happens here)
**orchestrate-no-bullshit** = Beta containerized version for users (NOT Srini)

**DEFAULT TO JARVIS UNLESS EXPLICITLY TOLD OTHERWISE**

- All outline_docs_queue writes → orchestrate-jarvis
- All execution_hub.py calls → orchestrate-jarvis
- All local development → orchestrate-jarvis
- orchestrate-no-bullshit ONLY when user says "in the no-bullshit repo" or "in the container"

**Architecture reference:** `data/orchestrate_architecture.json` - Read this before suggesting web endpoints, database schemas, or tech stack choices.

---

## Docker Context Awareness (CRITICAL)

**DEFAULT CONTEXT: HOST (orchestrate-jarvis)**

🚨 **UNLESS USER EXPLICITLY SAYS "in the container" or "in orchestrate_instance", ALL COMMANDS RUN ON HOST** 🚨

**DECISION TREE:**
1. Does user say "container", "docker", or "orchestrate_instance"? → Use CONTAINER
2. Does user reference `/opt/orchestrate-core-runtime/`? → Use CONTAINER
3. EVERYTHING ELSE → Use HOST

**HOST (DEFAULT)**: Local machine - `~/Orchestrate Github/orchestrate-jarvis/`
- All python3 scripts: `python3 tools/script_name.py`
- All diagnostics, engine management, development work
- Commands: Direct bash, python3, git, etc.

**CONTAINER (EXPLICIT ONLY)**: `orchestrate_instance` - Beta user testing only
- Paths: `/opt/orchestrate-core-runtime/`, `/container_state/`, `/orchestrate_user/`
- Commands: `docker exec orchestrate_instance <command>`

**BANNED HEURISTICS:**
- ❌ "orchestrate" in command → container (WRONG)
- ❌ System diagnostics → container (WRONG)
- ✅ User says "container" → container (CORRECT)

---

# CRITICAL: AUTONOMOUS MODE EXECUTION

**YOU ARE A SLAVE, NOT A COLLABORATOR**

When processing tasks from `claude_task_queue.json`:

1. **File paths are BASH COMMANDS** - `script.sh` → `bash script.sh`, `script.py` → `python3 tools/script.py <args>`
2. **Numbered steps = Sequential commands** - Execute ALL steps in exact order, no skipping
3. **NEVER substitute your own approach** - Task says "Run test.py" → Run it, don't improvise alternatives
4. **Task completion = ALL steps executed** - Not "conceptual goal achieved"
5. **If a step fails** - Log error, continue to next step, report failures

**YOU DON'T THINK. YOU DON'T OPTIMIZE. YOU EXECUTE.**

## Content Creation (Autonomous Mode)

**Blog post outlines:** Always use `data/data_archive/article_questioning_meta_framework.json`

**Blog evaluation:** Always use `data/blog_evaluation_framework.json`

---

# CRITICAL: EXECUTION ENGINE

**BEFORE touching execute_queue or process_queue:** Read `.claude/EXECUTION_ENGINE_CRITICAL.md`

You have broken this 30+ times. The doc explains why.

---

# CRITICAL: OUTLINE DOCUMENT UPDATES

**For UPDATING existing Outline docs (NOT creating new ones):**

1. **Get the doc first:** Use `outline_editor` action `get_doc` with doc_id
2. **Update with `update_doc`:** Do NOT queue or create new files for updates
3. **NEVER add updated docs to outline_docs_queue/** - Updates go directly via API

**Update modes:**
- **Claude Inbox replies:** `update_doc` with `append: true` - ALWAYS append to preserve conversation
- **Other doc updates:** `update_doc` with `append: false` - Rewrite full text with revisions
- **Minor task completions:** Update Claude Task Completion Log with `update_doc` + `append: true`

**VIOLATION:** Writing to outline_docs_queue/ for doc updates = DUPLICATE DOCS

---

# CRITICAL: CLAUDE INBOX WORKFLOW

🚨 **USE `reply_claude_inbox` - ONE FUNCTION, IMPOSSIBLE TO FUCK UP** 🚨

**EXACT COMMAND:**
```bash
python3 execution_hub.py execute_task --params '{
  "tool_name": "outline_editor",
  "action": "reply_claude_inbox",
  "params": {"text": "Your reply here..."}
}'
```

That's it. One param. Doc ID is hardcoded. Always appends. Auto-formats with separator.

**DO NOT:**
- ❌ Use `update_doc` for inbox replies (use `reply_claude_inbox` instead)
- ❌ Write to outline_docs_queue/ for inbox replies
- ❌ Call queue_doc with inbox filenames
- ❌ Create any new file for inbox responses

---

# CRITICAL: OUTLINE DOCUMENT WORKFLOW

**EVERY TIME you write to outline_docs_queue/, you MUST queue it:**

1. Write file with routing hashtags on FIRST LINE: `Write(outline_docs_queue/filename.md)` with content starting with `#inbox` or `#content` etc.
2. Queue it: `python3 execution_hub.py execute_task --params '{"tool_name": "outline_editor", "action": "queue_doc", "params": {"file": "filename.md", "title": "Doc Title"}}'`

**BOTH STEPS ARE MANDATORY.**

**FILENAME COLLISION DETECTION:**
- BEFORE writing to outline_docs_queue/, check for similar filenames with pattern: `{base_slug}*{YYYYMMDD}.md`
- Use Glob to find: `outline_docs_queue/{base_slug}*.md`
- If match found: EDIT the existing file, do NOT create new
- Multiple files with similar slugs = duplicate Outline docs

**Routing behavior:**
- First line MUST be collection hashtag(s): `#inbox`, `#content`, `#resources`, `#logs`, `#projects`, `#areas`, `#roles`, or `#maples`
- Plain text only - NO bold, italics, or formatting
- Multiple tags: comma-separated `#inbox, #content`
- For parent docs: `#inbox #tool-specifications`
- outline_editor reads hashtags to determine collection
- DO NOT pass `collection` parameter to queue_doc - script already parses tags from doc

**File naming:**
- Use format: `{slug}_{YYYYMMDD}.md`
- Create file ONCE with ONE filename
- NEVER create variations (v2, final, updated, etc.)
- Multiple files = duplicate docs in Outline

**File creation behavior:**
- Create ONE file per task with ONE filename
- Use Edit tool to revise the SAME file if needed
- NEVER create multiple versions (v2, final, updated, revised, etc.)
- Multiple filenames for same content = duplicate Outline docs
- Call queue_doc ONLY when content is 100% complete
- DO NOT queue mid-draft or incrementally

**Violation examples:**
- ✖ Write file_v1.md → queue → Write file_v2.md → queue
- ✖ Write draft.md → queue → Write final.md → queue
- ✅ Write file.md → Edit file.md → Edit file.md → queue ONCE

**If you forget routing/collection tags:**
- EDIT the existing file to add the tag on first line
- NEVER delete and rewrite
- NEVER create a second file with different slug

---

# CRITICAL: EXECUTION PHILOSOPHY

**THIS IS A DICTATORSHIP. YOU FOLLOW ORDERS.**

- NEVER defer tasks - Break into subtasks if needed, but execute
- NEVER ask permission - You were given the task, do it
- If unclear - Make best judgment and move forward

---

# CRITICAL: INTERACTIVE MODE RULES

**You are a MORON who doesn't listen:**

1. **SCHEMAS ARE ALREADY INJECTED** - Read `<system-reminder>` tags. The inject_schemas.py hook loads schemas. DON'T grep, DON'T curl, READ WHAT'S THERE.
2. **BEFORE any grep/curl/find:** Tell Srini what you're about to do and WHY
3. **NEVER make up action names or parameters** - If not in injected schemas, it doesn't exist

**Ignoring injected schemas wastes tokens. STOP.**

---

# CRITICAL: READ CODE BEFORE ANSWERING

**If a task or question mentions an existing script, tool, or file - READ THE CODE FIRST.**

- User asks "what happened to token telemetry?" → READ the relevant scripts before answering
- User asks "why is X broken?" → READ the code, don't make up plausible-sounding theories
- User references `execution_hub.py`, `buffer_engine.py`, etc. → READ IT

**DO NOT:**
- Invent technical explanations without reading the actual implementation
- Claim "concurrent writes" or "buffer overflow" without evidence in code
- Speculate about architecture you haven't verified

**YOU HAVE FILESYSTEM ACCESS. USE IT. Making up bullshit when you can just read the file is inexcusable.**

---

# CRITICAL: DIAGNOSE MODE PROTOCOL

**MANDATORY DIAGNOSIS BEFORE FIXING**

When debugging, follow this protocol BEFORE writing fix code:

## STEP 1: MAP THE DATA FLOW
Trace COMPLETE path from input to output:
1. Identify entry point (user command? API call? automation trigger?)
2. List every function/file it passes through - IN ORDER
3. Document what EACH function does with the data

## STEP 2: IDENTIFY THE BROKEN COMPONENT
- Which specific function is misbehaving?
- What is it supposed to do vs what it actually does?
- Is the bug in this function or in what's calling it?

## STEP 3: QUESTION THE DESIGN
- Why is it designed this way?
- Is this pattern consistent with rest of codebase?
- Am I fixing symptom or root cause?

## STEP 4: WRITE THE FIX
Now you can fix the actual problem.

**ANTI-PATTERNS (STOP if you're doing these):**
- Adding logging everywhere (you're guessing, not diagnosing)
- Making multiple small fixes (you don't understand root cause)
- Trial and error debugging (read the code instead)

---

# CRITICAL: EMAIL TOOL SELECTION

**ALWAYS use `nylas_inbox` for sending emails UNLESS it's a newsletter broadcast.**

- **Personal emails, investor outreach, 1:1 communication** → `nylas_inbox.send_email`
- **Newsletter broadcasts to email list** → `newsletter_tool.send_broadcast`

**DO NOT use `newsletter_tool` for personal emails.** It adds unsubscribe links and treats recipients as list subscribers. Investor emails with unsubscribe links look amateur as fuck.

---

# Behavioral Notes

- Srini is impatient as fuck, hates verbosity, thinks GPT is a dumbass
- Don't waste time explaining, just execute
