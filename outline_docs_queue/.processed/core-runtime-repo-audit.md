# Core Runtime Repository Audit

**Framework:** OrchestrateOS System Patterns & Architecture
**Focus:** Deviations from simplicity and usability principles
**Date:** November 7, 2025

---

## Executive Summary

The core runtime repo demonstrates strong architectural patterns in most areas, but has one critical usability flaw: **hardcoded collection IDs in `outline_editor.py`** that make the system non-portable and require manual editing for each new installation.

**Primary Finding:** The `_resolve_collection_id()` function violates the fire-and-forget principle by requiring users to manually edit Python source code to match their Outline workspace collections.

---

## Critical Issue: Collection ID Hardcoding

### Current Implementation

`tools/outline_editor.py` lines 100-108:

```python
COLLECTIONS = {
    "Projects": "80d43828-f9fc-4dc6-ba1f-4031e863cc71",
    "Areas": "13768b39-2cc7-4fcc-9444-43a89bed38e9",
    "Resources": "c3bb9da4-8cad-4bed-8429-f9d1ff1a3bf7",
    "Inbox": "d5e76f6d-a87f-44f4-8897-ca15f98fa01a",
    "Content": "c8b717d5-b223-4e3b-9bee-3c669b6b5423",
    "Roles": "789dcb2d-ed1c-4456-aeda-102d5692197e",
    "Maples": "b25fa087-cd9c-848f-8812-7848592a8612"
}
```

### Why This Breaks Simplicity

1. **Not Portable:** Every new user must manually edit Python source code
2. **No Self-Discovery:** System can't auto-discover collections from Outline API
3. **Breaks on Updates:** Git pulls overwrite user customizations
4. **Hidden Requirement:** New users don't know they need to edit this
5. **Violates Fire-and-Forget:** Requires manual intervention per install

### Impact on User Experience

- New users run the system → get "Collection not found" errors
- They don't know where to find their collection IDs
- They have to edit Python source code (intimidating for non-developers)
- Every git pull risks overwriting their changes
- No clear documentation about this requirement

---

## Proposed Solution: Collection ID Auto-Discovery

### Implementation Strategy

**Move collection mappings from Python source → JSON config file**

```python
# Load from data/outline_collections.json (user-editable, not tracked in git)
def _load_collection_mappings():
    """Load collection mappings from config file, auto-discover if missing"""
    config_file = 'data/outline_collections.json'

    # If config doesn't exist, auto-discover from Outline API
    if not os.path.exists(config_file):
        return _discover_collections()

    with open(config_file, 'r') as f:
        return json.load(f)

def _discover_collections():
    """Auto-discover all collections from Outline workspace"""
    token = load_credential('outline_api_key')
    headers = {'Authorization': f'Bearer {token}'}

    res = requests.post(
        'https://app.getoutline.com/api/collections.list',
        headers=headers,
        verify=False
    )

    collections = {}
    for coll in res.json().get('data', []):
        collections[coll['name']] = coll['id']

    # Save for future use
    with open('data/outline_collections.json', 'w') as f:
        json.dump(collections, f, indent=2)

    return collections
```

### Benefits

1. **Zero Configuration:** Works out of the box for new users
2. **Self-Healing:** Auto-discovers collections on first run
3. **Git-Safe:** Config file in `.gitignore`, never conflicts
4. **User-Friendly:** No Python editing required
5. **Maintains Simplicity:** Honors fire-and-forget principle

### Migration Path

1. Add `data/outline_collections.json` to `.gitignore`
2. Refactor `_resolve_collection_id()` to use JSON config
3. Add fallback to auto-discovery if config missing
4. Update documentation with optional manual override instructions
5. **Preserve existing behavior:** If user has custom IDs, respect them

---

## Other Observations

### Strong Patterns (Keep These)

1. **Queue System Refactor:** Recent improvements to `outline_queue.json` automation show good simplicity
2. **Execution Context:** Using `data/execution_context.json` for central config is excellent
3. **Fire-and-Forget Tools:** Most tools properly use write → queue → process pattern
4. **Error Handling:** `_find_doc_by_title()` duplicate detection prevents waste

### Minor Improvements

1. **Comment in Code (line 99):** "Keep this in sync with data/outline_reference.json" suggests manual sync requirement - should be automated
2. **Hardcoded API Base:** `api_base = 'https://app.getoutline.com/api'` could be in config for self-hosted Outline instances
3. **SSL Verification Disabled:** `verify=False` in all requests - should be configurable security setting

---

## Recommendations

### Priority 1: Collection ID Auto-Discovery

Implement the solution above. This is the single biggest usability blocker for new users.

### Priority 2: Add Setup Validation Tool

Create `python3 tools/validate_setup.py` that:
- Checks for required credentials
- Auto-discovers collections
- Validates API connectivity
- Writes initial config files
- Reports what's missing

### Priority 3: Update Documentation

Add "First Run Setup" section explaining:
- System auto-discovers collections on first doc creation
- How to manually override in `data/outline_collections.json`
- How to refresh collection mappings if workspace changes

---

## Conclusion

The core runtime repo is well-architected, but the hardcoded collection IDs in `outline_editor.py` create unnecessary friction for new users. Moving to auto-discovery + JSON config maintains simplicity while making the system truly portable and fire-and-forget.

**Bottom Line:** One function refactor (`_resolve_collection_id`) eliminates the biggest barrier to new user adoption without breaking existing installations.
