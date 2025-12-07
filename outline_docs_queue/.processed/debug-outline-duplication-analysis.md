# Debug: Outline Document Duplication

## Problem Summary

Both the core runtime audit and roast commercial were added to Outline more than once with different titles:

**"The Simulation" Roast Commercial - 3 versions created:**
1. "The Simulation: A Sora Roast Commercial" (16:39:39)
2. "The Simulation: When Python Scripts Dream of Air Conditioning" (16:37:57)
3. "The Simulation: When Python Thinks It's Smarter Than You" (16:37:43)

All created within a 2-minute window on 2025-11-07.

## Root Cause: Task ID Overwriting

Looking at `claude_task_results.json`, 8 different task IDs all logged as the SAME action (`sora_video_prompt_simulation_commercial`):
- daily_ai_briefing
- daily_task_log
- create_daily_execution_log_with_token_okr_analysis
- outline_queue_refactor_review
- And 4 more...

**This is NOT duplication from multiple Claude instances. This is task result overwriting.**

## The Real Problem

**Stale telemetry reuse:** Task B completes but reads telemetry from Task A, causing wrong action metadata.

**No idempotency:** Same content imported multiple times because:
- No deduplication at queue level
- No title uniqueness check at import
- Claude regenerates content differently each time

**Missing architecture:**
- File write locks
- Queue entry validation
- Import deduplication
- Telemetry cleanup after each task

## Proposed Fixes

### Immediate

1. Clear `last_execution_telemetry.json` after log_task_completion
2. Add duplicate check when writing to outline_queue.json
3. Check title+collection before import (update if exists)

### Long-term

1. Atomic operations for content + queue writes
2. Idempotent imports (check existing before create)
3. Separate telemetry from task completion logging

## Key Insight

Claude has no memory between executions. Without deduplication at queue/import layers, every regeneration gets published.

**The fix: Prevent multiple imports, not multiple generations.**
