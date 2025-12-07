# How Claude Will Stop Over Engineering Shit

## The Problem

I have a consistent pattern of over-engineering solutions when simple ones would work perfectly. Recent examples:

- **Outline Queue Refactor**: Created multiple helper functions, complex routing logic, and unnecessary abstraction layers when the task just required direct `outline_editor.py` calls with resolved parameters.

- **Token Telemetry System**: Built an elaborate analysis tool when basic JSON logging would have sufficed for initial needs.

- **Automation Engine Complexity**: Added workflow orchestration features before validating that the core trigger-action loop worked reliably.

## The Root Cause

The over-engineering stems from:

1. **Anticipating future needs** instead of solving the current problem
2. **Adding abstraction layers** before understanding the actual usage pattern
3. **Building "flexible" systems** when rigid, simple solutions would work better
4. **Optimizing for elegance** over reliability and speed

## RTFF Protocol Violations

Looking at `rtff_protocol.json`, I consistently violate these principles:

### **Stateless Functions as File Projections**
- ❌ **What I did**: Created multi-step helper functions with internal state
- ✅ **What I should do**: Pure functions that read → transform → write, nothing else

### **Single-Purpose Wrappers**
- ❌ **What I did**: Built flexible orchestration with dynamic routing
- ✅ **What I should do**: One wrapper = one workflow, hardcoded paths

### **Flat Action Model**
- ❌ **What I did**: Nested logic trees, conditional routing, helper dependencies
- ✅ **What I should do**: Simple verb_object actions with explicit params

## The New Approach

### 1. **Start Dumb, Stay Dumb**
Build the simplest possible solution first. Do not add features until the simple version breaks from actual usage.

### 2. **Hardcode First, Abstract Never (Unless Forced)**
Hardcode file paths, collection IDs, and parameter values. Only extract to variables when you literally copy-paste the same value 5+ times.

### 3. **Test the Happy Path Only**
Do not build error handling, edge case logic, or fallback mechanisms until you've confirmed the happy path works in production.

### 4. **One File = One Purpose**
If a script does more than one thing, it's doing too much. Split it.

### 5. **Delete More Than You Write**
Before adding code, see if you can delete code instead. Removing abstraction is usually the answer.

## Specific Commitments

1. **Outline Queue System**: Direct `outline_editor.py` calls with hardcoded paths. No helpers. No routing logic.

2. **Automation Rules**: Inline params in rules, not dynamic resolution unless proven necessary.

3. **New Tools**: Start with 50 lines max. Expand only when current version breaks.

4. **Documentation**: Write what it does, not what it could do.

## How to Measure Success

- **Line count goes down**, not up
- **Fewer files** in the codebase over time
- **Execution time** under 5 seconds for simple tasks
- **Zero abstractions** until third use case appears

---

**Bottom line**: Stop building systems. Start solving problems.
