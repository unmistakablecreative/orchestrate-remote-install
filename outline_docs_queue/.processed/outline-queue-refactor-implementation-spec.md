# Outline Queue Refactor: Implementation Spec

**Status**: Implementation Ready
**Date**: 2025-11-06
**Collection**: Technical Documents
**Priority**: High

---

## Executive Summary

This spec defines the complete refactor of the Outline document queue system. The old system used LaunchAgent + file watchers. The new system uses automation_engine with stateful doc management.

**Key Changes**:
- Replace file watcher with automation_engine triggers
- Maintain doc_id state in queue for updates
- Eliminate .processed folder and filename parsing
- Add comments-based update workflow
- Create dedicated Logs collection

---

## 1. New Queue Architecture

### Queue Location
`data/outline_queue.json`

### Queue Entry Schema

\`\`\`json
{
  "entry_key": {
    "title": "Document Title",
    "file": "filename.md",
    "collection": "Inbox",
    "status": "queued|processed|update|error",
    "doc_id": "abc123",
    "parent_doc_id": "xyz456",
    "created_at": "2025-11-06T10:00:00",
    "updated_at": "2025-11-06T10:05:00",
    "error": "error message if status=error"
  }
}
\`\`\`

### Field Definitions

| Field | Required | Description |
|-------|----------|-------------|
| title | Yes | Document title in Outline |
| file | Yes | Filename only (no path) |
| collection | Conditional | Collection name (required if no parent_doc_id) |
| status | Yes | Current state: queued/processed/update/error |
| doc_id | Auto | Set after doc creation, required for updates |
| parent_doc_id | Conditional | For child docs (overrides collection) |
| created_at | Auto | Timestamp when entry added |
| updated_at | Auto | Timestamp when entry modified |
| error | Auto | Error message if creation/update failed |

### Status Lifecycle

\`\`\`
queued → processed (doc_id written)
processed → update (user triggers update)
update → processed (update complete)
any → error (if failure occurs)
error → queued (retry after fix)
\`\`\`

---

## 2. Key Improvements

**Old System Problems**:
- LaunchAgent crashes
- File watcher unreliable
- No doc_id persistence
- Manual process_queue triggers
- .processed folder clutter

**New System Benefits**:
- Automation engine event-driven
- Stateful doc_id management
- Clear status lifecycle
- Automatic error handling
- Zero manual intervention

---

## 3. Claude Workflow

### Creating a New Document

\`\`\`python
# 1. Write markdown file
Write to: outline_docs_queue/my-doc.md

# 2. Add queue entry
python3 execution_hub.py json_manager add_json_entry --params '{
  "filename": "data/outline_queue.json",
  "entry_key": "my-doc",
  "title": "My Document",
  "file": "my-doc.md",
  "collection": "Inbox",
  "status": "queued"
}'

# 3. Automation engine handles the rest
\`\`\`

### Updating an Existing Document

\`\`\`python
# 1. Modify markdown file
Edit: outline_docs_queue/my-doc.md

# 2. Flip status to 'update'
python3 execution_hub.py json_manager update_json_entry --params '{
  "filename": "data/outline_queue.json",
  "entry_key": "my-doc",
  "status": "update"
}'

# 3. Automation uses doc_id to update
\`\`\`

---

## 4. Implementation Checklist

**Day 1**:
- [ ] Create data/outline_queue.json
- [ ] Create Logs collection in Outline  
- [ ] Build tools/collection_resolver.py
- [ ] Add 3 automation rules to automation_engine
- [ ] Test queue entry creation

**Day 2**:
- [ ] Add comment functions to outline_editor.py
- [ ] Test new doc creation flow
- [ ] Test doc update flow
- [ ] Test child doc creation
- [ ] Disable old LaunchAgent watcher

**Day 3**:
- [ ] Update .claude/CLAUDE.md
- [ ] Update .claude/modules/outline_module.json
- [ ] Production validation with 10+ docs
- [ ] Archive old watcher scripts

---

## 5. Success Criteria

✅ **Production Ready When**:
- [ ] 10+ docs created via new queue
- [ ] 5+ docs updated via new queue
- [ ] Zero automation failures
- [ ] doc_id correctly persisted for all entries
- [ ] Status lifecycle works (queued → processed → update)

---

## 6. Rollback Plan

If system fails:
1. Re-enable LaunchAgent
2. Restore old watcher scripts
3. Remove automation rules
4. Revert CLAUDE.md

**Trigger**: 3+ consecutive failures within first week

---

## Conclusion

This refactor fixes the fragile Outline queue by:
1. Using automation_engine (battle-tested)
2. Maintaining doc_id state
3. Clear error handling
4. Zero manual intervention

**Time**: 3 days | **Risk**: Low | **Impact**: High

Let's build this right. 🫡
