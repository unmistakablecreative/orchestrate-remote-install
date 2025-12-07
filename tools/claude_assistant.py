import sys
import json
import os
import subprocess
import time
import requests
import stat
import re
import glob as glob_module
from datetime import datetime
from pathlib import Path


def run_precondition_check(check_config, task_description):
    """
    Run precondition checks before a task can be processed.

    Supports check types:
    - file_exists: Uses glob pattern to check if files exist
    - file_not_empty: Verifies file exists and has content
    - json_field_exists: Checks if a specific field exists in a JSON file

    Args:
        check_config: Dict with keys:
            - type: 'file_exists', 'file_not_empty', or 'json_field_exists'
            - pattern: Glob pattern or file path (can include {placeholder} for extraction)
            - field: For json_field_exists, the field path (e.g., 'entries.articles')
        task_description: Task description string for variable extraction

    Returns:
        {"passed": bool, "error": str or None}
    """
    check_type = check_config.get("type")
    pattern = check_config.get("pattern", "")

    # Extract variables from task_description if pattern has placeholders
    # e.g., pattern="semantic_memory/images/{campaign_id}_*.png" with task "for campaign saasstackblog"
    # extracts campaign_id=saasstackblog
    if "{" in pattern:
        # Find placeholders
        placeholders = re.findall(r'\{(\w+)\}', pattern)
        for placeholder in placeholders:
            # Try to extract from task description
            # Look for patterns like "campaign_id: value", "campaign: value", "for value campaign"
            extraction_patterns = [
                rf'{placeholder}[:\s]+["\']?(\w+)["\']?',  # campaign_id: value
                rf'for\s+["\']?(\w+)["\']?\s+{placeholder}',  # for value campaign_id
                rf'{placeholder}[=\s]+["\']?(\w+)["\']?',  # campaign_id=value
            ]

            extracted = None
            for ep in extraction_patterns:
                match = re.search(ep, task_description, re.IGNORECASE)
                if match:
                    extracted = match.group(1)
                    break

            if extracted:
                pattern = pattern.replace(f'{{{placeholder}}}', extracted)
            else:
                # Placeholder not found - can't run check
                return {
                    "passed": False,
                    "error": f"Could not extract '{placeholder}' from task description to complete precondition check"
                }

    # Resolve to absolute path if relative
    if not os.path.isabs(pattern):
        pattern = os.path.join(os.getcwd(), pattern)

    if check_type == "file_exists":
        # Use glob to check if files matching pattern exist
        matches = glob_module.glob(pattern)
        if matches:
            return {"passed": True, "error": None}
        else:
            return {
                "passed": False,
                "error": f"Precondition failed: No files found matching '{pattern}'"
            }

    elif check_type == "file_not_empty":
        # Check file exists AND has content
        matches = glob_module.glob(pattern)
        if not matches:
            return {
                "passed": False,
                "error": f"Precondition failed: File not found: '{pattern}'"
            }

        for match in matches:
            try:
                if os.path.getsize(match) > 0:
                    return {"passed": True, "error": None}
            except OSError:
                pass

        return {
            "passed": False,
            "error": f"Precondition failed: File(s) matching '{pattern}' exist but are empty"
        }

    elif check_type == "json_field_exists":
        field_path = check_config.get("field", "")
        if not field_path:
            return {"passed": False, "error": "json_field_exists check requires 'field' parameter"}

        matches = glob_module.glob(pattern)
        if not matches:
            return {
                "passed": False,
                "error": f"Precondition failed: JSON file not found: '{pattern}'"
            }

        for match in matches:
            try:
                with open(match, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Navigate nested field path (e.g., "entries.articles" -> data["entries"]["articles"])
                current = data
                for key in field_path.split('.'):
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                    else:
                        return {
                            "passed": False,
                            "error": f"Precondition failed: Field '{field_path}' not found in '{match}'"
                        }

                return {"passed": True, "error": None}

            except json.JSONDecodeError as e:
                return {
                    "passed": False,
                    "error": f"Precondition failed: Invalid JSON in '{match}': {str(e)}"
                }
            except Exception as e:
                return {
                    "passed": False,
                    "error": f"Precondition failed: Error reading '{match}': {str(e)}"
                }

    else:
        return {
            "passed": False,
            "error": f"Unknown precondition check type: '{check_type}'"
        }


def run_validator(validator_config, task_output):
    """
    Run validators on task output before marking complete.

    Supports validator types:
    - entry_key_format: Validates entry_keys match regex pattern
    - image_binding_valid: Cross-references entry_key prefixes with actual image files
    - diagnosis_documented: Checks if output has required diagnosis fields
    - root_cause_identified: Validates output mentions root cause analysis
    - fix_tested: Checks if output mentions testing/verification
    - file_exists_in_queue: Checks if file exists in outline_docs_queue/
    - has_collection_hashtag: Validates first line starts with #collection hashtag
    - doc_queued: Checks if document is registered in outline_queue.json
    - doc_has_images: Checks if document content contains image URLs (.png, .jpg, gamma.app, etc.)
    - social_posts_queued: Validates social posts exist in post_queue.json for a campaign
    - json_schema: Basic structure validation for JSON outputs

    Args:
        validator_config: Dict with keys:
            - type: 'entry_key_format', 'image_binding_valid', or 'json_schema'
            - pattern: For entry_key_format, the regex pattern to match
            - required_fields: For json_schema, list of required fields
        task_output: The output data from the task

    Returns:
        {"passed": bool, "error": str or None}
    """
    validator_type = validator_config.get("type")

    if validator_type == "entry_key_format":
        pattern = validator_config.get("pattern", "")
        if not pattern:
            return {"passed": False, "error": "entry_key_format validator requires 'pattern' parameter"}

        # Extract entry_keys from task output
        entry_keys = []

        # Handle various output structures
        if isinstance(task_output, dict):
            # Check for posts array (buffer_engine output)
            if "posts" in task_output:
                for post in task_output.get("posts", []):
                    if isinstance(post, dict) and "entry_key" in post:
                        entry_keys.append(post["entry_key"])
            # Check for direct entry_key
            elif "entry_key" in task_output:
                entry_keys.append(task_output["entry_key"])
            # Check for entries list
            elif "entries" in task_output:
                for entry in task_output.get("entries", []):
                    if isinstance(entry, dict) and "entry_key" in entry:
                        entry_keys.append(entry["entry_key"])

        if not entry_keys:
            # No entry keys to validate - that's OK if output doesn't contain posts
            return {"passed": True, "error": None}

        # Validate each entry_key matches pattern
        compiled_pattern = re.compile(pattern)
        invalid_keys = []
        for key in entry_keys:
            if not compiled_pattern.match(key):
                invalid_keys.append(key)

        if invalid_keys:
            return {
                "passed": False,
                "error": f"Validation failed: entry_key(s) don't match pattern '{pattern}': {invalid_keys[:5]}"
            }

        return {"passed": True, "error": None}

    elif validator_type == "image_binding_valid":
        # Cross-reference entry_key prefixes with actual image files
        # entry_key format: {campaign_id}_post_{N}_{date}
        # Image files: semantic_memory/images/{campaign_id}_*.png

        entry_keys = []

        # Extract entry_keys from output
        if isinstance(task_output, dict):
            if "posts" in task_output:
                for post in task_output.get("posts", []):
                    if isinstance(post, dict) and "entry_key" in post:
                        entry_keys.append(post["entry_key"])
            elif "entry_key" in task_output:
                entry_keys.append(task_output["entry_key"])

        if not entry_keys:
            return {"passed": True, "error": None}

        # Extract campaign_ids and check image availability
        images_dir = os.path.join(os.getcwd(), "semantic_memory/images")
        missing_campaigns = set()

        for key in entry_keys:
            # Extract campaign_id from entry_key (format: {campaign_id}_post_{N}_{date})
            match = re.match(r'^([a-z0-9]+)_post_\d+_\d+$', key)
            if match:
                campaign_id = match.group(1)
                # Check if images exist for this campaign
                image_pattern = os.path.join(images_dir, f"{campaign_id}_*.png")
                if not glob_module.glob(image_pattern):
                    missing_campaigns.add(campaign_id)

        if missing_campaigns:
            return {
                "passed": False,
                "error": f"Validation failed: No images found for campaign(s): {list(missing_campaigns)}. Expected files at semantic_memory/images/{{campaign_id}}_*.png"
            }

        return {"passed": True, "error": None}

    elif validator_type == "diagnosis_documented":
        # Check if diagnosis fields exist in output
        required_fields = validator_config.get("required_fields", ["diagnosis", "root_cause"])

        if not isinstance(task_output, dict):
            return {
                "passed": False,
                "error": validator_config.get("error_message", "Output must be JSON with diagnosis fields")
            }

        missing_fields = []
        for field in required_fields:
            if field not in task_output or not task_output.get(field):
                missing_fields.append(field)

        if missing_fields:
            return {
                "passed": False,
                "error": validator_config.get("error_message", f"Missing diagnosis fields: {missing_fields}")
            }
        return {"passed": True, "error": None}

    elif validator_type == "root_cause_identified":
        # Check if output mentions root cause patterns
        patterns = validator_config.get("required_patterns", ["root cause", "root_cause", "because"])

        output_text = ""
        if isinstance(task_output, dict):
            output_text = str(task_output.get("diagnosis", "")) + " " + str(task_output.get("root_cause", "")) + " " + str(task_output.get("summary", ""))
        elif isinstance(task_output, str):
            output_text = task_output

        found = False
        for pattern in patterns:
            if pattern.lower() in output_text.lower():
                found = True
                break

        if not found:
            return {
                "passed": False,
                "error": validator_config.get("error_message", "Root cause not documented")
            }
        return {"passed": True, "error": None}

    elif validator_type == "fix_tested":
        # Check if output mentions testing
        patterns = validator_config.get("required_patterns", ["tested", "verified", "confirmed"])

        output_text = ""
        if isinstance(task_output, dict):
            output_text = str(task_output)
        elif isinstance(task_output, str):
            output_text = task_output

        found = False
        for pattern in patterns:
            if pattern.lower() in output_text.lower():
                found = True
                break

        if not found:
            return {
                "passed": False,
                "error": validator_config.get("error_message", "Fix not tested")
            }
        return {"passed": True, "error": None}

    elif validator_type == "file_exists_in_queue":
        # Check if file exists in outline_docs_queue/
        check_path = validator_config.get("check_path", "outline_docs_queue/")

        # Get filename from output
        filename = ""
        if isinstance(task_output, dict):
            filename = task_output.get("filename", task_output.get("file", ""))

        if not filename:
            # No filename to validate - pass by default
            return {"passed": True, "error": None}

        file_path = os.path.join(os.getcwd(), check_path, filename)
        if not os.path.exists(file_path):
            return {
                "passed": False,
                "error": validator_config.get("error_message", f"File not found: {file_path}")
            }
        return {"passed": True, "error": None}

    elif validator_type == "has_collection_hashtag":
        # Check if first line has collection hashtag
        pattern = validator_config.get("pattern", "^#[a-z]+")

        # Get file content from output
        content = ""
        if isinstance(task_output, dict):
            content = task_output.get("content", task_output.get("file_content", ""))
            # Also try to read from filename if provided
            if not content and task_output.get("filename"):
                filename = task_output.get("filename")
                file_path = os.path.join(os.getcwd(), "outline_docs_queue", filename)
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                    except:
                        pass

        if not content:
            # No content to validate - pass by default
            return {"passed": True, "error": None}

        first_line = content.split('\n')[0] if content else ""
        if not re.match(pattern, first_line):
            return {
                "passed": False,
                "error": validator_config.get("error_message", f"First line '{first_line}' doesn't match pattern {pattern}")
            }
        return {"passed": True, "error": None}

    elif validator_type == "doc_queued":
        # Check if document is registered in outline_queue.json
        check_file = validator_config.get("check_file", "data/outline_queue.json")

        # Get filename from output
        filename = ""
        if isinstance(task_output, dict):
            filename = task_output.get("filename", task_output.get("file", ""))

        if not filename:
            # No filename to validate - pass by default
            return {"passed": True, "error": None}

        queue_path = os.path.join(os.getcwd(), check_file)
        if not os.path.exists(queue_path):
            return {
                "passed": False,
                "error": f"Queue file not found: {check_file}"
            }

        try:
            with open(queue_path, 'r', encoding='utf-8') as f:
                queue_data = json.load(f)

            # Search for entry with matching filename
            entries = queue_data if isinstance(queue_data, list) else queue_data.get("queue", queue_data.get("entries", []))

            found = False
            for entry in entries:
                if isinstance(entry, dict):
                    entry_file = entry.get("file", entry.get("filename", ""))
                    if entry_file == filename or filename in entry_file:
                        found = True
                        break

            if not found:
                return {
                    "passed": False,
                    "error": validator_config.get("error_message", f"Document '{filename}' not found in {check_file}")
                }

            return {"passed": True, "error": None}

        except Exception as e:
            return {
                "passed": False,
                "error": f"Error checking queue file: {e}"
            }

    elif validator_type == "doc_has_images":
        # Check if document content contains image URLs
        patterns = validator_config.get("patterns", ["\\.png", "\\.jpg", "\\.jpeg", "\\.gif", "\\.webp", "gamma\\.app"])

        # Get doc content from output
        doc_content = ""
        if isinstance(task_output, dict):
            doc_content = task_output.get("doc_content", task_output.get("content", ""))
            if isinstance(doc_content, dict):
                doc_content = doc_content.get("text", str(doc_content))
        elif isinstance(task_output, str):
            doc_content = task_output

        # Check if any pattern matches
        has_images = False
        for pattern in patterns:
            if re.search(pattern, str(doc_content), re.IGNORECASE):
                has_images = True
                break

        if not has_images:
            return {
                "passed": False,
                "error": validator_config.get("error_message", "No images found in document")
            }
        return {"passed": True, "error": None}

    elif validator_type == "social_posts_queued":
        # Check if social posts were queued for the campaign
        check_file = validator_config.get("check_file", "data/post_queue.json")
        match_field = validator_config.get("match_field", "campaign")

        # Get campaign identifier from output
        campaign_id = ""
        if isinstance(task_output, dict):
            campaign_id = task_output.get("campaign_id", task_output.get("campaign", ""))

        if not campaign_id:
            # Can't validate without campaign_id - pass by default
            return {"passed": True, "error": None}

        # Check post_queue.json for matching entries
        queue_path = os.path.join(os.getcwd(), check_file)
        if not os.path.exists(queue_path):
            return {
                "passed": False,
                "error": f"Post queue file not found: {check_file}"
            }

        try:
            with open(queue_path, 'r', encoding='utf-8') as f:
                post_queue = json.load(f)

            # Search for posts matching the campaign
            posts_found = False
            entries = post_queue if isinstance(post_queue, list) else post_queue.get("posts", post_queue.get("entries", []))

            for entry in entries:
                if isinstance(entry, dict):
                    entry_campaign = entry.get(match_field, "")
                    if campaign_id.lower() in entry_campaign.lower():
                        posts_found = True
                        break

            if not posts_found:
                return {
                    "passed": False,
                    "error": validator_config.get("error_message", f"No social posts queued for campaign '{campaign_id}'")
                }

            return {"passed": True, "error": None}

        except Exception as e:
            return {
                "passed": False,
                "error": f"Error checking post queue: {e}"
            }

    elif validator_type == "json_schema":
        required_fields = validator_config.get("required_fields", [])
        if not required_fields:
            return {"passed": True, "error": None}

        if not isinstance(task_output, dict):
            return {
                "passed": False,
                "error": "Validation failed: Task output must be a JSON object for json_schema validation"
            }

        missing_fields = []
        for field in required_fields:
            # Support nested field paths (e.g., "posts.0.content")
            current = task_output
            field_parts = field.split('.')
            found = True

            for part in field_parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                elif isinstance(current, list):
                    try:
                        idx = int(part)
                        if 0 <= idx < len(current):
                            current = current[idx]
                        else:
                            found = False
                            break
                    except ValueError:
                        found = False
                        break
                else:
                    found = False
                    break

            if not found:
                missing_fields.append(field)

        if missing_fields:
            return {
                "passed": False,
                "error": f"Validation failed: Missing required field(s): {missing_fields}"
            }

        return {"passed": True, "error": None}

    else:
        return {
            "passed": False,
            "error": f"Unknown validator type: '{validator_type}'"
        }


def atomic_write_json(filepath, data):
    """
    Atomic write using temp file + rename.
    Handles readonly files properly.
    Prevents corruption from partial writes.
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    # Handle read-only files
    was_readonly = False
    if filepath.exists():
        file_stat = filepath.stat()
        if not (file_stat.st_mode & stat.S_IWUSR):
            was_readonly = True
            filepath.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
    
    # Write to temp file
    temp_path = filepath.with_suffix(f'.tmp.{os.getpid()}.{int(time.time() * 1000000)}')
    
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        
        # Atomic rename
        temp_path.replace(filepath)
        
        # Restore readonly if needed
        if was_readonly:
            filepath.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        
        return True
        
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise e

def assign_task(params):
    """
    GPT assigns a task to Claude Code queue.

    FIXED: Auto-generates deterministic task_id from description hash.
    GPT only provides description, not task_id (prevents duplicates from creative ID variations).

    Required: description
    Optional: priority, auto_execute

    NOTE: Tasks are flat - no context field. Working memory loaded in process_queue.

    CONTEXT INJECTION: If description contains @prefix (e.g., @asshole-chronicles),
    loads task_context_triggers.json to inject context_file and steps.
    """
    import hashlib
    import re

    description = params.get("description")
    priority = params.get("priority", "medium")

    # === TASK-SPECIFIC CONTEXT INJECTION ===
    # Scan for @prefix triggers and inject context/steps
    triggers_file = os.path.join(os.getcwd(), "data/task_context_triggers.json")
    injected_context_file = None
    injected_steps = None

    if description and os.path.exists(triggers_file):
        try:
            with open(triggers_file, 'r', encoding='utf-8') as f:
                triggers_data = json.load(f)

            triggers = triggers_data.get("triggers", {})

            # Scan description for @prefix triggers
            for prefix, trigger_config in triggers.items():
                if prefix in description:
                    print(f"🎯 Found trigger '{prefix}' in task description", file=sys.stderr)

                    # Load context file if specified
                    context_file = trigger_config.get("context_file")
                    if context_file:
                        context_path = os.path.join(os.getcwd(), context_file)
                        if os.path.exists(context_path):
                            injected_context_file = context_file
                            print(f"📄 Will inject context from: {context_file}", file=sys.stderr)

                    # Get steps to inject
                    steps = trigger_config.get("inject_steps", [])
                    if steps:
                        injected_steps = steps
                        print(f"📋 Will inject {len(steps)} steps", file=sys.stderr)

                    # Only match first trigger
                    break
        except Exception as e:
            print(f"Warning: Could not load task_context_triggers.json: {e}", file=sys.stderr)

    if not description:
        return {"status": "error", "message": "Missing required field: description"}

    # Auto-generate deterministic task_id from description hash
    # Normalize: lowercase, strip whitespace, remove punctuation variations
    normalized_desc = description.lower().strip()
    normalized_desc = re.sub(r'[^\w\s]', '', normalized_desc)  # Remove punctuation
    normalized_desc = re.sub(r'\s+', ' ', normalized_desc)  # Normalize whitespace

    # Generate hash from normalized description
    desc_hash = hashlib.md5(normalized_desc.encode()).hexdigest()[:12]

    # Create slug from first few words (max 5 words, 30 chars)
    words = normalized_desc.split()[:5]
    slug = '_'.join(words)[:30].rstrip('_')

    # Combine slug + hash for deterministic ID
    task_id = f"{slug}_{desc_hash}"

    # Log that we auto-generated the ID (helpful for debugging)
    print(f"Auto-generated task_id: {task_id} (from description hash)", file=sys.stderr)

    try:
        subprocess.run(
            ["python3", "execution_hub.py", "load_orchestrate_os"],
            capture_output=True,
            timeout=10,
            cwd=os.getcwd()
        )
    except Exception:
        pass

    # NOTE: Tasks are now FLAT - no context field
    # Working memory and contextual awareness are loaded ONCE in process_queue
    # This prevents bloat in claude_task_queue.json

    queue_file = os.path.join(os.getcwd(), "data/claude_task_queue.json")
    os.makedirs(os.path.dirname(queue_file), exist_ok=True)

    if os.path.exists(queue_file):
        with open(queue_file, 'r', encoding='utf-8') as f:
            queue = json.load(f)
    else:
        queue = {"tasks": {}}

    # === DEDUPLICATION CHECK ===
    # Prevent duplicate task assignment by checking existing tasks
    for existing_id, existing_task in queue.get("tasks", {}).items():
        if not isinstance(existing_task, dict):
            continue
        
        existing_desc = existing_task.get("description", "")
        existing_status = existing_task.get("status", "")
        
        # Check if descriptions match (first 200 chars to catch variations)
        desc_match = existing_desc[:200] == description[:200]
        
        if desc_match and existing_status in ["queued", "in_progress"]:
            print(f"âš ï¸  Duplicate task detected: '{existing_id}' already {existing_status}", file=sys.stderr)
            return {
                "status": "duplicate",
                "message": f"âš ï¸  Task already exists as '{existing_id}' with status '{existing_status}'",
                "existing_task_id": existing_id,
                "existing_status": existing_status,
                "hint": "Task not added to queue - duplicate detected"
            }
    
    # Also check completed tasks to avoid re-doing finished work
    results_file = os.path.join(os.getcwd(), "data/claude_task_results.json")
    if os.path.exists(results_file):
        try:
            with open(results_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
            
            for result_id, result_data in results.get("results", {}).items():
                result_desc = result_data.get("description", "")
                
                # Check if this exact task was recently completed (within last hour)
                completed_at = result_data.get("completed_at", "")
                if completed_at:
                    try:
                        completed_time = datetime.fromisoformat(completed_at.replace('Z', ''))
                        age_minutes = (datetime.now() - completed_time).total_seconds() / 60
                        
                        if age_minutes < 60:  # Completed within last hour
                            desc_match = result_desc[:200] == description[:200]
                            if desc_match:
                                print(f"âš ï¸  Task recently completed: '{result_id}' finished {age_minutes:.1f} min ago", file=sys.stderr)
                                return {
                                    "status": "duplicate",
                                    "message": f"âš ï¸  Task recently completed as '{result_id}' ({age_minutes:.1f} min ago)",
                                    "existing_task_id": result_id,
                                    "existing_status": "completed",
                                    "completed_at": completed_at,
                                    "hint": "Task not added to queue - already completed"
                                }
                    except:
                        pass
        except:
            pass

    # No duplicate found - proceed with assignment
    # NOTE: Flat task structure - working memory loaded in process_queue
    # BUT: context_file and steps can be injected by @prefix triggers
    task_data = {
        "status": "queued",
        "created_at": datetime.now().isoformat(),
        "assigned_by": "GPT",
        "priority": priority,
        "description": description
    }

    # Inject context file and steps if triggered
    if injected_context_file:
        task_data["context_file"] = injected_context_file
    if injected_steps:
        task_data["inject_steps"] = injected_steps

    queue["tasks"][task_id] = task_data

    atomic_write_json(queue_file, queue)

    # FIXED: auto_execute defaults to FALSE
    # The claude_execution_engine.py handles spawning - no need for two spawn paths
    # This eliminates the race condition that caused duplicate task execution
    auto_execute = params.get("auto_execute", False)

    if auto_execute and not os.environ.get("CLAUDECODE"):
        execute_result = execute_queue({})
        return {
            "status": "success",
            "message": f"âœ… Task '{task_id}' assigned and execution started",
            "task_id": task_id,
            "execution": execute_result
        }

    return {
        "status": "success",
        "message": f"✅ Task '{task_id}' queued (engine will spawn execution)",
        "task_id": task_id,
        "note": "claude_execution_engine.py will spawn Claude session automatically"
    }



def assign_demo_task(params):
    """Assigns a task with guaranteed 'demo_' prefix for demo recordings."""
    task_id = params.get("task_id")

    if not task_id:
        return {"status": "error", "message": "âŒ Missing required field: task_id"}

    if not task_id.startswith("demo_"):
        task_id = f"demo_{task_id}"

    modified_params = params.copy()
    modified_params["task_id"] = task_id

    result = assign_task(modified_params)

    if result.get("status") == "success":
        result["message"] = f"âœ… Demo task '{task_id}' assigned and will execute autonomously"

    return result


def check_task_status(params):
    """Check status of a task."""
    task_id = params.get("task_id")

    if not task_id:
        return {"status": "error", "message": "âŒ Missing required field: task_id"}

    queue_file = os.path.join(os.getcwd(), "data/claude_task_queue.json")
    if os.path.exists(queue_file):
        with open(queue_file, 'r', encoding='utf-8') as f:
            queue = json.load(f)
            if task_id in queue.get("tasks", {}):
                task_data = queue["tasks"][task_id]
                return {
                    "status": "success",
                    "task_id": task_id,
                    "task_status": task_data["status"],
                    "created_at": task_data.get("created_at"),
                    "description": task_data.get("description")
                }

    results_file = os.path.join(os.getcwd(), "data/claude_task_results.json")
    if os.path.exists(results_file):
        try:
            with open(results_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
            if task_id in results.get("results", {}):
                result_data = results["results"][task_id]
                return {
                    "status": "success",
                    "task_id": task_id,
                    "task_status": "done",
                    "completed_at": result_data.get("completed_at"),
                    "execution_time_seconds": result_data.get("execution_time_seconds"),
                    "output": result_data.get("output")
                }
        except Exception as e:
            return {"status": "error", "message": f"âŒ Error reading results: {str(e)}"}

    return {
        "status": "error",
        "message": f"âŒ Task '{task_id}' not found in queue or results"
    }


def get_task_result(params):
    """Get full result data from a completed task."""
    task_id = params.get("task_id")

    if not task_id:
        return {"status": "error", "message": "âŒ Missing required field: task_id"}

    results_file = os.path.join(os.getcwd(), "data/claude_task_results.json")

    if not os.path.exists(results_file):
        return {
            "status": "error",
            "message": f"âŒ No results file found. Task '{task_id}' may not be complete yet."
        }

    try:
        with open(results_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
    except Exception as e:
        return {"status": "error", "message": f"âŒ Error reading results: {str(e)}"}

    if task_id not in results.get("results", {}):
        return {
            "status": "error",
            "message": f"âŒ No result found for task '{task_id}'. Check if task is complete with check_task_status."
        }

    return {
        "status": "success",
        "task_id": task_id,
        "result": results["results"][task_id]
    }


def get_all_results(params):
    """Get all task results without needing individual task IDs."""
    results_file = os.path.join(os.getcwd(), "data/claude_task_results.json")

    if not os.path.exists(results_file):
        return {
            "status": "success",
            "message": "âœ… No task results yet",
            "results": {},
            "task_count": 0
        }

    try:
        with open(results_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
    except Exception as e:
        return {"status": "error", "message": f"âŒ Error reading results: {str(e)}"}

    all_results = results.get("results", {})

    return {
        "status": "success",
        "message": f"Found {len(all_results)} completed task(s)",
        "results": all_results,
        "task_count": len(all_results)
    }


def ask_claude(params):
    """Quick Q&A - GPT asks Claude a simple question, Claude answers."""
    question = params.get("question")

    if not question:
        return {"status": "error", "message": "âŒ Missing required field: question"}

    return {
        "status": "ready",
        "message": "ðŸ“ Question received - Claude will respond in current session",
        "question": question,
        "note": "Claude sees this and will answer directly without task queue"
    }


def cancel_task(params):
    """Cancel a queued or in_progress task."""
    task_id = params.get("task_id")

    if not task_id:
        return {"status": "error", "message": "âŒ Missing required field: task_id"}

    queue_file = os.path.join(os.getcwd(), "data/claude_task_queue.json")

    if not os.path.exists(queue_file):
        return {"status": "error", "message": "âŒ No task queue found"}

    try:
        with open(queue_file, 'r', encoding='utf-8') as f:
            queue = json.load(f)
    except Exception as e:
        return {"status": "error", "message": f"âŒ Error reading queue: {str(e)}"}

    if task_id not in queue.get("tasks", {}):
        return {"status": "error", "message": f"âŒ Task '{task_id}' not found in queue"}

    task = queue["tasks"][task_id]
    current_status = task.get("status")

    if current_status in ["done", "error"]:
        return {"status": "error", "message": f"âŒ Cannot cancel task that is already {current_status}"}

    queue["tasks"][task_id]["status"] = "cancelled"
    queue["tasks"][task_id]["cancelled_at"] = datetime.now().isoformat()

    try:
        atomic_write_json(queue_file, queue)
    except Exception as e:
        return {"status": "error", "message": f"âŒ Error writing queue: {str(e)}"}

    return {
        "status": "success",
        "message": f"âœ… Task '{task_id}' cancelled",
        "task_id": task_id,
        "previous_status": current_status
    }


def delete_task(params):
    """Delete a task from the queue completely."""
    task_id = params.get("task_id")

    if not task_id:
        return {"status": "error", "message": "âŒ Missing required field: task_id"}

    queue_file = os.path.join(os.getcwd(), "data/claude_task_queue.json")

    if not os.path.exists(queue_file):
        return {"status": "error", "message": "âŒ No task queue found"}

    try:
        with open(queue_file, 'r', encoding='utf-8') as f:
            queue = json.load(f)
    except Exception as e:
        return {"status": "error", "message": f"âŒ Error reading queue: {str(e)}"}

    if task_id not in queue.get("tasks", {}):
        return {"status": "error", "message": f"âŒ Task '{task_id}' not found in queue"}

    del queue["tasks"][task_id]

    try:
        atomic_write_json(queue_file, queue)
    except Exception as e:
        return {"status": "error", "message": f"âŒ Error writing queue: {str(e)}"}

    return {
        "status": "success",
        "message": f"âœ… Task '{task_id}' deleted from queue",
        "task_id": task_id
    }


def delete_task_result(params):
    """Delete a task result from claude_task_results.json."""
    task_id = params.get("task_id")

    if not task_id:
        return {"status": "error", "message": "âŒ Missing required field: task_id"}

    results_file = os.path.join(os.getcwd(), "data/claude_task_results.json")

    if not os.path.exists(results_file):
        return {"status": "error", "message": "âŒ No task results file found"}

    try:
        with open(results_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
    except Exception as e:
        return {"status": "error", "message": f"âŒ Error reading results: {str(e)}"}

    if task_id not in results:
        return {"status": "error", "message": f"âŒ Task result '{task_id}' not found"}

    del results[task_id]

    try:
        atomic_write_json(results_file, results)
    except Exception as e:
        return {"status": "error", "message": f"âŒ Error writing results: {str(e)}"}

    return {
        "status": "success",
        "message": f"âœ… Task result '{task_id}' deleted",
        "task_id": task_id
    }


def reset_task(params):
    """Reset a stuck in_progress task back to queued."""
    task_id = params.get("task_id")

    if not task_id:
        return {"status": "error", "message": "âŒ Missing required field: task_id"}

    queue_file = os.path.join(os.getcwd(), "data/claude_task_queue.json")

    if not os.path.exists(queue_file):
        return {"status": "error", "message": "âŒ No task queue found"}

    try:
        with open(queue_file, 'r', encoding='utf-8') as f:
            queue = json.load(f)
    except Exception as e:
        return {"status": "error", "message": f"âŒ Error reading queue: {str(e)}"}

    if task_id not in queue.get("tasks", {}):
        return {"status": "error", "message": f"âŒ Task '{task_id}' not found in queue"}

    task = queue["tasks"][task_id]
    current_status = task.get("status")

    queue["tasks"][task_id]["status"] = "queued"

    if "started_at" in queue["tasks"][task_id]:
        del queue["tasks"][task_id]["started_at"]

    queue["tasks"][task_id]["reset_at"] = datetime.now().isoformat()

    try:
        atomic_write_json(queue_file, queue)
    except Exception as e:
        return {"status": "error", "message": f"âŒ Error writing queue: {str(e)}"}

    return {
        "status": "success",
        "message": f"âœ… Task '{task_id}' reset to queued",
        "task_id": task_id,
        "previous_status": current_status
    }


def update_task(params):
    """Update a queued task's description, priority, or context."""
    task_id = params.get("task_id")

    if not task_id:
        return {"status": "error", "message": "âŒ Missing required field: task_id"}

    new_description = params.get("description")
    new_priority = params.get("priority")
    new_context = params.get("context")

    if not any([new_description, new_priority, new_context]):
        return {"status": "error", "message": "âŒ Must provide at least one field to update (description, priority, or context)"}

    queue_file = os.path.join(os.getcwd(), "data/claude_task_queue.json")

    if not os.path.exists(queue_file):
        return {"status": "error", "message": "âŒ No task queue found"}

    try:
        with open(queue_file, 'r', encoding='utf-8') as f:
            queue = json.load(f)
    except Exception as e:
        return {"status": "error", "message": f"âŒ Error reading queue: {str(e)}"}

    if task_id not in queue.get("tasks", {}):
        return {"status": "error", "message": f"âŒ Task '{task_id}' not found in queue"}

    task = queue["tasks"][task_id]

    if task.get("status") != "queued":
        return {"status": "error", "message": f"âŒ Can only update tasks with status 'queued' (current: {task.get('status')})"}

    updated_fields = []

    if new_description:
        queue["tasks"][task_id]["description"] = new_description
        updated_fields.append("description")

    if new_priority:
        queue["tasks"][task_id]["priority"] = new_priority
        updated_fields.append("priority")

    if new_context:
        current_context = queue["tasks"][task_id].get("context", {})
        current_context.update(new_context)
        queue["tasks"][task_id]["context"] = current_context
        updated_fields.append("context")

    queue["tasks"][task_id]["updated_at"] = datetime.now().isoformat()

    try:
        atomic_write_json(queue_file, queue)
    except Exception as e:
        return {"status": "error", "message": f"âŒ Error writing queue: {str(e)}"}

    return {
        "status": "success",
        "message": f"âœ… Task '{task_id}' updated",
        "task_id": task_id,
        "updated_fields": updated_fields
    }


def estimate_execution_time(task_count):
    """Estimates completion time for queued tasks based on historical execution data."""
    results_file = os.path.join(os.getcwd(), "data/claude_task_results.json")

    default_avg = 300

    if not os.path.exists(results_file):
        total_est = (default_avg * task_count) / 60
        return {
            "estimated_minutes": total_est,
            "estimated_range_str": f"~{int(total_est)}-{int(total_est * 1.5)} minutes",
            "avg_time_per_task": default_avg,
            "based_on": "default (no history)"
        }

    try:
        with open(results_file, 'r', encoding='utf-8') as f:
            results = json.load(f)

        all_results = results.get("results", {})

        if not all_results:
            total_est = (default_avg * task_count) / 60
            return {
                "estimated_minutes": total_est,
                "estimated_range_str": f"~{int(total_est)}-{int(total_est * 1.5)} minutes",
                "avg_time_per_task": default_avg,
                "based_on": "default (no history)"
            }

        total_time = 0
        count = 0
        for task_data in all_results.values():
            exec_time = task_data.get("execution_time_seconds", 0)
            if exec_time > 0:
                total_time += exec_time
                count += 1

        if count > 0:
            avg_time = total_time / count
        else:
            avg_time = default_avg

        total_est = (avg_time * task_count * 1.2) / 60
        min_est = (avg_time * task_count) / 60
        max_est = (avg_time * task_count * 1.5) / 60

        return {
            "estimated_minutes": total_est,
            "estimated_range_str": f"~{int(min_est)}-{int(max_est)} minutes",
            "avg_time_per_task": avg_time,
            "based_on": f"{count} historical task(s)"
        }

    except Exception:
        total_est = (default_avg * task_count) / 60
        return {
            "estimated_minutes": total_est,
            "estimated_range_str": f"~{int(total_est)}-{int(total_est * 1.5)} minutes",
            "avg_time_per_task": default_avg,
            "based_on": "default (error reading history)"
        }


def process_queue(params):
    """
    FIXED: Claude calls this to get all queued tasks.
    
    CRITICAL CHANGE: Does NOT mark tasks as in_progress automatically.
    Claude must explicitly call mark_task_in_progress when starting work.
    
    Returns list of tasks for Claude to process.
    """
    queue_file = os.path.join(os.getcwd(), "data/claude_task_queue.json")

    if not os.path.exists(queue_file):
        return {
            "status": "success",
            "message": "âœ… No tasks in queue",
            "pending_tasks": [],
            "task_count": 0
        }

    try:
        with open(queue_file, 'r', encoding='utf-8') as f:
            queue = json.load(f)
    except Exception as e:
        return {"status": "error", "message": f"âŒ Error reading queue: {str(e)}"}

    # Get queued tasks ONLY - DO NOT MODIFY STATUS
    # Tasks are flat - no embedded context (working_memory loaded once at top level)
    pending = []
    blocked_tasks = []

    # Load precondition configs from task_context_triggers.json
    triggers_file = os.path.join(os.getcwd(), "data/task_context_triggers.json")
    trigger_configs = {}
    if os.path.exists(triggers_file):
        try:
            with open(triggers_file, 'r', encoding='utf-8') as f:
                triggers_data = json.load(f)
                trigger_configs = triggers_data.get("triggers", {})
        except Exception:
            pass

    for task_id, task_data in queue.get("tasks", {}).items():
        # Skip already blocked tasks
        if task_data.get("blocked"):
            blocked_tasks.append({
                "task_id": task_id,
                "blocked_reason": task_data.get("blocked_reason", "Unknown"),
                "description": task_data.get("description", "")[:100]
            })
            continue

        if task_data.get("status") == "queued":
            # Check for preconditions based on task triggers
            description = task_data.get("description", "")
            precondition_failed = False
            blocked_reason = None

            # Check if any trigger with preconditions matches
            for trigger_prefix, trigger_config in trigger_configs.items():
                if trigger_prefix in description:
                    preconditions = trigger_config.get("preconditions", [])
                    for precondition in preconditions:
                        check_result = run_precondition_check(precondition, description)
                        if not check_result.get("passed"):
                            precondition_failed = True
                            blocked_reason = check_result.get("error")
                            break
                    break  # Only match first trigger

            if precondition_failed:
                # Mark task as blocked in queue file
                queue["tasks"][task_id]["blocked"] = True
                queue["tasks"][task_id]["blocked_reason"] = blocked_reason
                queue["tasks"][task_id]["blocked_at"] = datetime.now().isoformat()
                blocked_tasks.append({
                    "task_id": task_id,
                    "blocked_reason": blocked_reason,
                    "description": description[:100]
                })
                print(f"🚫 Task '{task_id}' blocked: {blocked_reason}", file=sys.stderr)
                continue
            task_output = {
                "task_id": task_id,
                "description": task_data["description"],
                "priority": task_data.get("priority", "medium"),
                "created_at": task_data.get("created_at"),
                "WORKFLOW": [
                    f"1. Call mark_task_in_progress for '{task_id}' BEFORE starting work",
                    "2. Execute the task using execution_hub.py",
                    f"3. Call log_task_completion for '{task_id}' when done"
                ]
            }

            # Include injected context_file and steps if present
            if task_data.get("context_file"):
                task_output["context_file"] = task_data["context_file"]
                # Load and include the context content
                context_path = os.path.join(os.getcwd(), task_data["context_file"])
                if os.path.exists(context_path):
                    try:
                        with open(context_path, 'r', encoding='utf-8') as f:
                            task_output["context_content"] = json.load(f)
                    except Exception:
                        pass

            if task_data.get("inject_steps"):
                task_output["inject_steps"] = task_data["inject_steps"]

            pending.append(task_output)

    # Save queue if any tasks were blocked
    if blocked_tasks:
        try:
            atomic_write_json(queue_file, queue)
            print(f"💾 Saved {len(blocked_tasks)} blocked task(s) to queue", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Could not save blocked tasks: {e}", file=sys.stderr)

    if not pending:
        result = {
            "status": "success",
            "message": "✅ No pending tasks",
            "pending_tasks": [],
            "task_count": 0
        }
        if blocked_tasks:
            result["blocked_tasks"] = blocked_tasks
            result["blocked_count"] = len(blocked_tasks)
            result["message"] = f"✅ No pending tasks ({len(blocked_tasks)} task(s) blocked by preconditions)"
        return result

    # Load working memory ONCE here (not per-task)
    working_memory = None
    working_memory_file = os.path.join(os.getcwd(), "data/working_memory.json")
    if os.path.exists(working_memory_file):
        try:
            with open(working_memory_file, 'r', encoding='utf-8') as f:
                working_memory = json.load(f)
        except Exception:
            pass

    # Load contextual awareness ONCE here (not per-task)
    contextual_awareness = None
    contextual_awareness_file = os.path.join(os.getcwd(), "data/contextual_awareness.json")
    if os.path.exists(contextual_awareness_file):
        try:
            with open(contextual_awareness_file, 'r', encoding='utf-8') as f:
                contextual_awareness = json.load(f)
        except Exception:
            pass

    # Estimate completion time based on historical data
    time_estimate = estimate_execution_time(len(pending))

    result = {
        "status": "success",
        "message": f"Found {len(pending)} pending task(s) - YOU MUST mark each in_progress before starting",
        "pending_tasks": pending,
        "task_count": len(pending),
        "estimated_completion_time": time_estimate["estimated_range_str"],
        "time_estimate_details": {
            "avg_time_per_task_seconds": time_estimate["avg_time_per_task"],
            "total_estimated_minutes": time_estimate["estimated_minutes"],
            "based_on": time_estimate["based_on"]
        },
        "CRITICAL_WORKFLOW": [
            "ðŸš¨ BEFORE STARTING EACH TASK:",
            "   â†' Call mark_task_in_progress(task_id)",
            "ðŸš¨ AFTER COMPLETING EACH TASK:",
            "   â†' Call log_task_completion(task_id, status, ...)",
            "ðŸš¨ Skipping these steps = ORPHANED TASKS"
        ]
    }

    # Add context as separate top-level fields (loaded once, not per-task)
    if working_memory:
        result["working_memory"] = working_memory
    if contextual_awareness:
        result["contextual_awareness"] = contextual_awareness

    # Include blocked tasks info if any
    if blocked_tasks:
        result["blocked_tasks"] = blocked_tasks
        result["blocked_count"] = len(blocked_tasks)

    return result


def mark_task_in_progress(params):
    """
    FIXED: Claude explicitly calls this when starting work on a task.
    
    This is now the ONLY way tasks get marked in_progress.
    
    Required:
    - task_id: the task to mark as in_progress
    """
    task_id = params.get("task_id")

    if not task_id:
        return {"status": "error", "message": "âŒ Missing required field: task_id"}

    queue_file = os.path.join(os.getcwd(), "data/claude_task_queue.json")

    if not os.path.exists(queue_file):
        return {"status": "error", "message": "âŒ No task queue found"}

    try:
        with open(queue_file, 'r', encoding='utf-8') as f:
            queue = json.load(f)
    except Exception as e:
        return {"status": "error", "message": f"âŒ Error reading queue: {str(e)}"}

    if task_id not in queue.get("tasks", {}):
        return {"status": "error", "message": f"âŒ Task '{task_id}' not found in queue"}

    task = queue["tasks"][task_id]
    current_status = task.get("status")

    if current_status not in ["queued", "in_progress"]:
        return {
            "status": "error",
            "message": f"âŒ Task '{task_id}' cannot be marked in_progress (current status: {current_status})"
        }

    queue["tasks"][task_id]["status"] = "in_progress"
    if "started_at" not in queue["tasks"][task_id]:
        queue["tasks"][task_id]["started_at"] = datetime.now().isoformat()

    try:
        atomic_write_json(queue_file, queue)
    except Exception as e:
        return {"status": "error", "message": f"âŒ Error writing queue: {str(e)}"}

    return {
        "status": "success",
        "message": f"âœ… Task '{task_id}' marked as in_progress",
        "next_step": "Execute the task, then call log_task_completion when done"
    }


def execute_queue(params):
    """Spawns a Claude Code session to process all queued tasks."""
    
    if os.environ.get("CLAUDECODE"):
        return {
            "status": "error",
            "message": "âŒ Cannot spawn nested Claude Code session. You're already inside Claude Code. Process tasks directly in the current session instead.",
            "hint": "Read tasks from data/claude_task_queue.json and process them here"
        }

    lockfile = os.path.join(os.getcwd(), "data/execute_queue.lock")

    if os.path.exists(lockfile):
        should_remove = False
        try:
            with open(lockfile, 'r') as f:
                lock_data = json.load(f)
                pid = lock_data.get("pid")
                created_at = lock_data.get("created_at")

            if created_at:
                try:
                    lock_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    age_minutes = (datetime.now() - lock_time.replace(tzinfo=None)).total_seconds() / 60
                    if age_minutes > 30:
                        print(f"âš ï¸  Removing stale lockfile (created {age_minutes:.1f} minutes ago)", file=sys.stderr)
                        should_remove = True
                except:
                    pass

            if not should_remove and pid:
                try:
                    os.kill(pid, 0)
                    return {
                        "status": "already_running",
                        "message": f"â³ Queue execution already in progress (PID {pid})",
                        "hint": "Wait for current batch to complete"
                    }
                except OSError:
                    print(f"âš ï¸  Removing stale lockfile (PID {pid} not found)", file=sys.stderr)
                    should_remove = True

            if should_remove:
                os.remove(lockfile)

        except Exception as e:
            print(f"Warning: Could not read lockfile: {e}", file=sys.stderr)
            try:
                os.remove(lockfile)
                print("âš ï¸  Removed corrupted lockfile", file=sys.stderr)
            except:
                pass

    queue_file = os.path.join(os.getcwd(), "data/claude_task_queue.json")
    if not os.path.exists(queue_file):
        return {
            "status": "success",
            "message": "âœ… No tasks in queue",
            "task_count": 0
        }

    try:
        with open(queue_file, 'r', encoding='utf-8') as f:
            queue = json.load(f)
    except Exception as e:
        return {"status": "error", "message": f"âŒ Error reading queue: {str(e)}"}

    task_count = sum(1 for task_data in queue.get("tasks", {}).values()
                     if task_data.get("status") == "queued")

    if task_count == 0:
        return {
            "status": "success",
            "message": "âœ… No pending tasks",
            "task_count": 0
        }

    estimated_time_minutes = None
    try:
        results_file = os.path.join(os.getcwd(), "data/claude_task_results.json")
        if os.path.exists(results_file):
            with open(results_file, 'r', encoding='utf-8') as f:
                results_data = json.load(f)

            times = []
            for result in results_data.get("results", {}).values():
                exec_time = result.get("execution_time_seconds")
                if exec_time and exec_time > 0:
                    times.append(exec_time)

            if times:
                import statistics
                median_time = statistics.median(times)
                estimated_seconds = median_time * task_count
                estimated_time_minutes = round(estimated_seconds / 60, 1)
    except:
        pass

    try:
        env = os.environ.copy()
        env.pop('ANTHROPIC_API_KEY', None)
        env.pop('CLAUDECODE', None)

        prompt = """Process all tasks in data/claude_task_queue.json.

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
ðŸš¨ NEW WORKFLOW - READ CAREFULLY ðŸš¨
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

CRITICAL CHANGE: Tasks are NOT auto-marked as in_progress anymore.
YOU MUST explicitly mark each task before starting work.

EXECUTION FLOW:
1. Call process_queue to get tasks list
2. For EACH task:
   a. Call mark_task_in_progress(task_id) â† NEW MANDATORY STEP
   b. Execute the work
   c. Call log_task_completion(task_id, ...) â† STILL MANDATORY

EXAMPLE:
  # Get tasks
  python3 execution_hub.py execute_task --params '{"tool_name": "claude_assistant", "action": "process_queue", "params": {}}'
  
  # For task "example_task":
  
  # STEP 1: Mark in progress
  python3 execution_hub.py execute_task --params '{"tool_name": "claude_assistant", "action": "mark_task_in_progress", "params": {"task_id": "example_task"}}'
  
  # STEP 2: Do the work
  [execute task logic here]
  
  # STEP 3: Log completion
  python3 execution_hub.py execute_task --params '{"tool_name": "claude_assistant", "action": "log_task_completion", "params": {"task_id": "example_task", "status": "done", "actions_taken": [...], "output": {...}}}'

If you skip mark_task_in_progress, orphan detection will reset the task.
If you skip log_task_completion, the task stays in queue forever.

AFTER ALL TASKS: rm data/execute_queue.lock

Project context in .claude/CLAUDE.md (auto-loaded)."""

        log_file_path = os.path.join(os.getcwd(), "data", "claude_execution.log")
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        log_file = open(log_file_path, "w")

        process = subprocess.Popen([
            "claude",
            "-p", prompt,
            "--permission-mode", "acceptEdits",
            "--allowedTools", "Bash,Read,Write,Edit"
        ],
        env=env,
        cwd=os.getcwd(),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True
        )

        # FIXED: Create lockfile AFTER spawn with CLAUDE SESSION PID (not this process)
        # This way the PID check in engine actually works
        try:
            with open(lockfile, 'w') as f:
                json.dump({
                    "created_at": datetime.now().isoformat(),
                    "pid": process.pid,  # Claude session PID, not os.getpid()
                    "task_count": task_count
                }, f, indent=2)
            print(f"🔒 Created lockfile with Claude PID {process.pid} for {task_count} task(s)", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Could not create lockfile: {e}", file=sys.stderr)

        result = {
            "status": "task_started",
            "message": f"✅ Claude Code session started in background to process {task_count} task(s)",
            "task_count": task_count,
            "pid": process.pid,
            "note": "Process is running in background. Claude will write token telemetry to data/last_execution_telemetry.json after completion."
        }

        if estimated_time_minutes is not None:
            result["estimated_time_minutes"] = estimated_time_minutes
            result["message"] = f"âœ… Claude Code session started in background to process {task_count} task(s) (est. {estimated_time_minutes} min)"

        return result

    except Exception as e:
        return {
            "status": "error",
            "message": f"âŒ Failed to spawn Claude Code session: {str(e)}"
        }


def log_task_completion(params):
    """
    FIXED: Atomic task completion logging with per-task lock removal.
    
    Required:
    - task_id: the task that was completed
    - status: "done" or "error"
    - actions_taken: list of what Claude did

    Optional:
    - output: any data produced
    - output_summary: human-readable summary
    - errors: if status is "error", what went wrong
    - execution_time_seconds: how long it took
    """
    task_id = params.get("task_id")
    status = params.get("status")
    actions_taken = params.get("actions_taken", [])
    output = params.get("output", {})
    output_summary = params.get("output_summary")
    errors = params.get("errors")
    execution_time = params.get("execution_time_seconds", 0)

    if not task_id:
        return {"status": "error", "message": "âŒ Missing required field: task_id"}
    if not status:
        return {"status": "error", "message": "âŒ Missing required field: status"}

    # === VALIDATOR CHECK ===
    # Run validators on task output if status is "done" and task has validators configured
    if status == "done" and output:
        # Load task data to check for validators
        queue_file_check = os.path.join(os.getcwd(), "data/claude_task_queue.json")
        if os.path.exists(queue_file_check):
            try:
                with open(queue_file_check, 'r', encoding='utf-8') as f:
                    queue_check = json.load(f)

                task_data = queue_check.get("tasks", {}).get(task_id, {})
                task_desc = task_data.get("description", "")

                # Load validator configs from task_context_triggers.json
                triggers_file = os.path.join(os.getcwd(), "data/task_context_triggers.json")
                if os.path.exists(triggers_file):
                    with open(triggers_file, 'r', encoding='utf-8') as f:
                        triggers_data = json.load(f)
                        trigger_configs = triggers_data.get("triggers", {})

                    # Check if any trigger with validators matches
                    for trigger_prefix, trigger_config in trigger_configs.items():
                        if trigger_prefix in task_desc:
                            validators = trigger_config.get("validators", [])
                            for validator in validators:
                                check_result = run_validator(validator, output)
                                if not check_result.get("passed"):
                                    error_msg = check_result.get("error", "Validation failed")
                                    print(f"❌ Task '{task_id}' failed validation: {error_msg}", file=sys.stderr)
                                    return {
                                        "status": "error",
                                        "message": f"❌ Cannot mark task complete - validation failed: {error_msg}",
                                        "validation_error": error_msg,
                                        "hint": "Fix the output to pass validation before marking complete"
                                    }
                            break  # Only match first trigger

            except Exception as e:
                print(f"Warning: Could not run validators: {e}", file=sys.stderr)

    # Pre-completion validation (existing outline_editor check)
    if status == "done":
        execution_log_file = os.path.join(os.getcwd(), "data/execution_log.json")
        if os.path.exists(execution_log_file):
            try:
                with open(execution_log_file, 'r', encoding='utf-8') as f:
                    exec_log = json.load(f)

                recent_entries = list(exec_log.get("executions", []))[-50:]

                for entry in recent_entries:
                    if (entry.get("tool") == "outline_editor" and
                        entry.get("action") in ["import_doc_from_file", "create_doc", "create_child_doc"] and
                        entry.get("result_status") == "success"):
                        return {
                            "status": "error",
                            "message": "âŒ outline_editor action called directly. Queue system must be used.",
                            "violation": {
                                "tool": "outline_editor",
                                "action": entry.get("action"),
                                "timestamp": entry.get("timestamp"),
                                "required_workflow": "Write to outline_docs_queue/ + add to outline_queue.json"
                            },
                            "hint": "Tasks that create Outline docs MUST use the queue system to prevent duplicates."
                        }
            except Exception as e:
                print(f"Warning: Could not validate execution log: {e}", file=sys.stderr)

    # ATOMIC QUEUE UPDATE: Remove task from queue
    task_description = None
    task_batch_id = None
    task_started_at = None
    task_created_at = None
    queue_file = os.path.join(os.getcwd(), "data/claude_task_queue.json")
    
    if os.path.exists(queue_file):
        try:
            with open(queue_file, 'r', encoding='utf-8') as f:
                queue = json.load(f)

            if task_id in queue.get("tasks", {}):
                task_description = queue["tasks"][task_id].get("description", "")
                task_batch_id = queue["tasks"][task_id].get("batch_id")
                task_started_at = queue["tasks"][task_id].get("started_at")
                task_created_at = queue["tasks"][task_id].get("created_at")

                # ATOMIC: Remove task from queue
                del queue["tasks"][task_id]

                atomic_write_json(queue_file, queue)
                print(f"âœ… Removed '{task_id}' from queue (completed)", file=sys.stderr)
                
        except Exception as e:
            print(f"Warning: Could not update queue: {e}", file=sys.stderr)

    # Calculate execution_time if not provided
    if execution_time == 0 and (task_started_at or task_created_at):
        try:
            timestamp = task_started_at if task_started_at else task_created_at
            started_str = timestamp.replace('Z', '').replace('+00:00', '')
            started = datetime.fromisoformat(started_str)
            completed = datetime.now()
            execution_time = (completed - started).total_seconds()
            print(f"â±ï¸  Calculated execution time: {execution_time:.2f} seconds", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Could not calculate execution time: {e}", file=sys.stderr)

    # ATOMIC RESULTS UPDATE
    results_file = os.path.join(os.getcwd(), "data/claude_task_results.json")
    archive_dir = os.path.join(os.getcwd(), "data/task_archive")

    try:
        # Load existing results
        if os.path.exists(results_file):
            with open(results_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
        else:
            results = {"results": {}}

        # Archive old results if needed
        if len(results.get("results", {})) > 10:
            try:
                os.makedirs(archive_dir, exist_ok=True)

                sorted_results = sorted(
                    results["results"].items(),
                    key=lambda x: x[1].get("completed_at", ""),
                    reverse=False
                )

                to_archive = dict(sorted_results[:-10])
                to_keep = dict(sorted_results[-10:])

                if to_archive:
                    archive_file = os.path.join(archive_dir, f"results_{datetime.now().strftime('%Y-%m')}.jsonl")
                    with open(archive_file, 'a', encoding='utf-8') as f:
                        for archived_task_id, result_data in to_archive.items():
                            f.write(json.dumps({"task_id": archived_task_id, **result_data}) + '\n')

                    results["results"] = to_keep
                    print(f"ðŸ“¦ Archived {len(to_archive)} old results to {archive_file}", file=sys.stderr)
            except Exception as e:
                print(f"Warning: Could not archive old results: {e}", file=sys.stderr)

        if not output_summary:
            output_summary = "Task completed" if status == "done" else "Task failed"

        # Calculate batch position
        is_first_task_in_batch = False
        batch_position = 0

        if task_batch_id:
            completed_in_batch = 0
            for tid, result in results.get("results", {}).items():
                if result.get("batch_id") == task_batch_id:
                    completed_in_batch += 1

            is_first_task_in_batch = (completed_in_batch == 0)
            batch_position = completed_in_batch + 1

            print(f"ðŸ“Š Batch {task_batch_id}: task {batch_position} (first: {is_first_task_in_batch})", file=sys.stderr)

        # Add result
        results["results"][task_id] = {
            "status": status,
            "description": task_description if task_description else output_summary,
            "completed_at": datetime.now().isoformat(),
            "execution_time_seconds": execution_time,
            "actions_taken": actions_taken,
            "output": output,
            "output_summary": output_summary,
            "errors": errors
        }

        if task_batch_id:
            results["results"][task_id]["batch_id"] = task_batch_id
            results["results"][task_id]["batch_position"] = batch_position

        print(f"ðŸ“ Logged task '{task_id}' completion to results file", file=sys.stderr)

        atomic_write_json(results_file, results)
        
    except Exception as e:
        return {"status": "error", "message": f"âŒ Error writing results: {str(e)}"}

    # Merge token telemetry if available
    telemetry_file = os.path.join(os.getcwd(), "data", "last_execution_telemetry.json")
    telemetry_merged = False

    if os.path.exists(telemetry_file):
        try:
            with open(telemetry_file, 'r', encoding='utf-8') as f:
                telemetry_data = json.load(f)

            input_tokens = telemetry_data.get("tokens_input", 0)
            if task_batch_id and not is_first_task_in_batch:
                input_tokens = 0
                print(f"📊 Batch task {batch_position}: using shared input context (0 incremental tokens)", file=sys.stderr)

            output_tokens = telemetry_data.get("tokens_output", 0)
            if telemetry_data.get("tokens_input") or output_tokens:
                results["results"][task_id]["tokens"] = {
                    "input": input_tokens,
                    "output": output_tokens,
                    "total": input_tokens + output_tokens
                }
                results["results"][task_id]["token_cost"] = input_tokens + output_tokens

            if telemetry_data.get("tool"):
                results["results"][task_id]["tool"] = telemetry_data["tool"]
            if telemetry_data.get("action"):
                results["results"][task_id]["action"] = telemetry_data["action"]

            atomic_write_json(results_file, results)

            # === FIX: Aggregate into token_telemetry.json for historical tracking ===
            token_telemetry_file = os.path.join(os.getcwd(), "data", "token_telemetry.json")
            try:
                if os.path.exists(token_telemetry_file):
                    with open(token_telemetry_file, 'r', encoding='utf-8') as f:
                        token_history = json.load(f)
                else:
                    token_history = {"sessions": [], "task_patterns": {}, "weekly_resets": []}

                # Add session entry
                session_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "task_id": task_id,
                    "task_type": f"{telemetry_data.get('tool', 'unknown')}_{telemetry_data.get('action', 'unknown')}",
                    "tokens_input": input_tokens,
                    "tokens_output": output_tokens,
                    "tokens_total": input_tokens + output_tokens,
                    "tokens_cache_read": telemetry_data.get("tokens_cache_read", 0),
                    "tokens_cache_creation": telemetry_data.get("tokens_cache_creation", 0),
                    "tokens_raw_input": telemetry_data.get("tokens_raw_input", 0),
                    "duration_seconds": execution_time,
                    "success": status == "done"
                }
                token_history["sessions"].append(session_entry)

                # Keep only last 100 sessions
                if len(token_history["sessions"]) > 100:
                    token_history["sessions"] = token_history["sessions"][-100:]

                # Update task patterns
                task_type = session_entry["task_type"]
                if task_type not in token_history["task_patterns"]:
                    token_history["task_patterns"][task_type] = {
                        "total_executions": 0,
                        "total_tokens": 0,
                        "avg_tokens": 0.0,
                        "min_tokens": float('inf'),
                        "max_tokens": 0,
                        "success_rate": 1.0
                    }

                pattern = token_history["task_patterns"][task_type]
                pattern["total_executions"] += 1
                pattern["total_tokens"] += session_entry["tokens_total"]
                pattern["avg_tokens"] = pattern["total_tokens"] / pattern["total_executions"]
                if session_entry["tokens_total"] > 0:
                    pattern["min_tokens"] = min(pattern["min_tokens"], session_entry["tokens_total"])
                    pattern["max_tokens"] = max(pattern["max_tokens"], session_entry["tokens_total"])

                # Fix inf for JSON serialization
                if pattern["min_tokens"] == float('inf'):
                    pattern["min_tokens"] = 0

                atomic_write_json(token_telemetry_file, token_history)
                print(f"📈 Aggregated telemetry to token_telemetry.json ({len(token_history['sessions'])} sessions)", file=sys.stderr)

            except Exception as e:
                print(f"Warning: Could not aggregate to token_telemetry.json: {e}", file=sys.stderr)

            os.remove(telemetry_file)
            telemetry_merged = True

        except Exception as e:
            print(f"Warning: Could not merge telemetry data: {e}", file=sys.stderr)

    # Update working_memory.json
    working_memory_file = os.path.join(os.getcwd(), "data/working_memory.json")
    try:
        if os.path.exists(working_memory_file):
            with open(working_memory_file, 'r', encoding='utf-8') as f:
                working_memory = json.load(f)
                if not isinstance(working_memory, list):
                    working_memory = []
        else:
            working_memory = []

        stripped_entry = {
            "task_id": task_id,
            "description": (task_description[:100] + "...") if task_description and len(task_description) > 100 else task_description,
            "status": status,
            "output_summary": (output_summary[:200] + "...") if output_summary and len(output_summary) > 200 else output_summary,
            "timestamp": datetime.now().isoformat()
        }

        working_memory.append(stripped_entry)

        if len(working_memory) > 15:
            working_memory = working_memory[-15:]

        atomic_write_json(working_memory_file, working_memory)
        print(f"ðŸ’¾ Updated working_memory.json (now {len(working_memory)} entries)", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Could not update working_memory.json: {e}", file=sys.stderr)

    # === CRITICAL: Remove task lock ===
    # This tells the engine this task is complete
    lock_file = os.path.join(os.getcwd(), "data/task_locks", f"{task_id}.lock")
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
            print(f"ðŸ”“ Removed task lock for {task_id}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Failed to remove task lock for {task_id}: {e}", file=sys.stderr)
    else:
        print(f"âš ï¸  No lock file found for {task_id} (may have been cleaned up already)", file=sys.stderr)

    return {
        "status": "success",
        "message": f"âœ… Task '{task_id}' completion logged with status: {status}",
        "output_summary": output_summary
    }


def batch_assign_tasks(params):
    """Assign multiple tasks at once with hash-pattern validation."""
    import re

    tasks = params.get("tasks")

    if not tasks:
        return {"status": "error", "message": "âŒ Missing required field: tasks (must be a list)"}

    if not isinstance(tasks, list):
        return {"status": "error", "message": "âŒ tasks must be a list of task dictionaries"}

    if len(tasks) == 0:
        return {"status": "error", "message": "âŒ tasks list is empty"}

    # Validate task_id format - must be deterministic hash-based ID from task_parser
    # Format: {slug}_{12_char_hex_hash} e.g. "implement_hash_pattern_abc123def456"
    HASH_ID_PATTERN = re.compile(r'^[a-z0-9_]+_[a-f0-9]{12}$')

    invalid_ids = []
    for task in tasks:
        if isinstance(task, dict):
            task_id = task.get("task_id", "")
            if task_id and not HASH_ID_PATTERN.match(task_id):
                invalid_ids.append(task_id)

    if invalid_ids:
        return {
            "status": "error",
            "message": f"❌ Invalid task_id format. IDs must match pattern: {{slug}}_{{12-char-hex-hash}}",
            "invalid_ids": invalid_ids,
            "required_format": "^[a-z0-9_]+_[a-f0-9]{12}$",
            "example": "implement_feature_abc123def456",
            "explanation": "Task IDs must be deterministic hashes from task_parser.py, not timestamp-based. This prevents duplicates."
        }

    results = []
    success_count = 0
    failed_count = 0

    for i, task in enumerate(tasks):
        task_id = task.get("task_id")

        if not isinstance(task, dict):
            results.append({
                "index": i,
                "task_id": None,
                "status": "error",
                "message": "âŒ Task must be a dictionary"
            })
            failed_count += 1
            continue

        if not task_id:
            results.append({
                "index": i,
                "task_id": None,
                "status": "error",
                "message": "âŒ Task missing required field: task_id"
            })
            failed_count += 1
            continue

        task_params = task.copy()
        task_params["auto_execute"] = False

        try:
            result = assign_task(task_params)
            if result.get("status") == "success":
                success_count += 1
                results.append({
                    "index": i,
                    "task_id": task_id,
                    "status": "success",
                    "message": f"âœ… Task {task_id} queued"
                })
            else:
                failed_count += 1
                results.append({
                    "index": i,
                    "task_id": task_id,
                    "status": "error",
                    "message": result.get("message", "Unknown error")
                })
        except Exception as e:
            failed_count += 1
            results.append({
                "index": i,
                "task_id": task_id,
                "status": "error",
                "message": f"âŒ Exception: {str(e)}"
            })

    summary = f"Assigned {success_count}/{len(tasks)} tasks successfully"
    if failed_count > 0:
        summary += f" ({failed_count} failed)"

    return {
        "status": "success" if success_count > 0 else "error",
        "message": f"âœ… {summary}" if success_count > 0 else f"âŒ {summary}",
        "success_count": success_count,
        "failed_count": failed_count,
        "total_tasks": len(tasks),
        "details": results,
        "summary": summary
    }


def get_recent_tasks(params):
    """Get the most recent N completed tasks."""
    limit = params.get("limit", 10)

    results_file = os.path.join(os.getcwd(), "data/claude_task_results.json")

    if not os.path.exists(results_file):
        return {
            "status": "success",
            "message": "âœ… No task results yet",
            "tasks": [],
            "task_count": 0
        }

    try:
        with open(results_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
    except Exception as e:
        return {"status": "error", "message": f"âŒ Error reading results: {str(e)}"}

    all_results = results.get("results", {})

    completed_tasks = {
        task_id: task_data
        for task_id, task_data in all_results.items()
        if task_data.get("status") == "done"
    }

    if not completed_tasks:
        return {
            "status": "success",
            "message": "âœ… No completed tasks found",
            "tasks": [],
            "task_count": 0
        }

    sorted_tasks = sorted(
        completed_tasks.items(),
        key=lambda x: x[1].get("completed_at", ""),
        reverse=True
    )[:limit]

    task_list = []
    for task_id, task_data in sorted_tasks:
        task_list.append({
            "task_id": task_id,
            "status": task_data.get("status"),
            "completed_at": task_data.get("completed_at"),
            "execution_time_seconds": task_data.get("execution_time_seconds", 0),
            "output_summary": task_data.get("output_summary", "No summary"),
            "output": task_data.get("output", {})
        })

    return {
        "status": "success",
        "message": f"Found {len(task_list)} recent completed task(s)",
        "tasks": task_list,
        "task_count": len(task_list)
    }


def self_assign_from_doc(params):
    """
    One-command task import: Fetch doc, parse tasks, batch assign to queue.

    Params:
        doc_id: Optional - defaults to Claude Tasks doc
        test_mode: If true, writes to claude_test_task_queue.json (default: false)

    GPT just says "self-assign from claude tasks doc" - no params needed.
    Script does the heavy lifting. GPT is too dumb to remember doc IDs.

    ~0.6 seconds instead of ~3 minutes for 10 tasks.
    """
    import hashlib

    # Default to Claude Tasks doc - GPT doesn't need to remember this
    CLAUDE_TASKS_DOC_ID = "8398b552-a586-4c11-9821-cc85844e9156"

    doc_id = params.get("doc_id", CLAUDE_TASKS_DOC_ID)
    test_mode = params.get("test_mode", False)

    # --- Step 1: Fetch doc from Outline ---
    try:
        cmd = [
            "python3", "tools/outline_editor.py", "get_doc",
            "--params", json.dumps({"doc_id": doc_id})
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=os.getcwd())
        doc_result = json.loads(result.stdout)

        if doc_result.get("status") == "error":
            return {"status": "error", "message": f"Failed to fetch doc: {doc_result.get('message')}"}

        doc_data = doc_result.get("doc") or doc_result.get("data", {})
        doc_text = doc_data.get("text", "")
        doc_title = doc_data.get("title", "Unknown")

        if not doc_text:
            return {"status": "error", "message": "Doc has no text content"}

    except Exception as e:
        return {"status": "error", "message": f"Failed to fetch doc: {str(e)}"}

    # --- Step 2: Parse tasks from markdown ---
    def generate_task_id(description):
        """Generate deterministic task_id from content."""
        text = re.sub(r'#+\s*', '', description)
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^a-zA-Z0-9\s]', '', text)

        normalized = text.strip().lower()
        words = normalized.split()[:5]
        slug = '_'.join(words) if words else 'task'
        content_hash = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:12]

        return f"{slug}_{content_hash}"

    def parse_tasks(doc_text):
        """Extract tasks from markdown. Each # header = new task."""
        tasks = []
        lines = doc_text.split('\n')
        current_task_lines = []
        in_task = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#'):
                if in_task and current_task_lines:
                    full_text = '\n'.join(current_task_lines).strip()
                    if full_text:
                        tasks.append({
                            "task_id": generate_task_id(full_text),
                            "description": full_text,
                            "priority": "medium"
                        })
                current_task_lines = [line]
                in_task = True
            elif in_task:
                current_task_lines.append(line)

        if in_task and current_task_lines:
            full_text = '\n'.join(current_task_lines).strip()
            if full_text:
                tasks.append({
                    "task_id": generate_task_id(full_text),
                    "description": full_text,
                    "priority": "medium"
                })

        return tasks

    tasks = parse_tasks(doc_text)

    if not tasks:
        return {"status": "error", "message": "No tasks found in doc (tasks must start with # header)"}

    # --- Step 3: Write to queue (ONE read, ONE write) ---
    if test_mode:
        queue_file = os.path.join(os.getcwd(), "data/claude_test_task_queue.json")
    else:
        queue_file = os.path.join(os.getcwd(), "data/claude_task_queue.json")

    try:
        if os.path.exists(queue_file):
            with open(queue_file, 'r', encoding='utf-8') as f:
                queue = json.load(f)
        else:
            queue = {"tasks": {}}

        added_tasks = []
        skipped_tasks = []

        for task in tasks:
            task_id = task["task_id"]
            if task_id in queue.get("tasks", {}):
                skipped_tasks.append(task_id)
                continue

            queue["tasks"][task_id] = {
                "status": "queued",
                "created_at": datetime.now().isoformat(),
                "assigned_by": "self_assign_from_doc",
                "priority": task["priority"],
                "description": task["description"],
                "source_doc_id": doc_id
            }
            added_tasks.append(task_id)

        atomic_write_json(queue_file, queue)

    except Exception as e:
        return {"status": "error", "message": f"Failed to write queue: {str(e)}"}

    return {
        "status": "success",
        "message": f"✅ Added {len(added_tasks)} tasks from '{doc_title}'",
        "doc_id": doc_id,
        "doc_title": doc_title,
        "tasks_added": len(added_tasks),
        "tasks_skipped": len(skipped_tasks),
        "task_ids": added_tasks,
        "skipped_ids": skipped_tasks,
        "test_mode": test_mode,
        "queue_file": queue_file
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('action')
    parser.add_argument('--params')
    args = parser.parse_args()
    params = json.loads(args.params) if args.params else {}

    if args.action == 'assign_task':
        result = assign_task(params)
    elif args.action == 'assign_demo_task':
        result = assign_demo_task(params)
    elif args.action == 'batch_assign_tasks':
        result = batch_assign_tasks(params)
    elif args.action == 'check_task_status':
        result = check_task_status(params)
    elif args.action == 'get_task_result':
        result = get_task_result(params)
    elif args.action == 'get_all_results':
        result = get_all_results(params)
    elif args.action == 'get_recent_tasks':
        result = get_recent_tasks(params)
    elif args.action == 'ask_claude':
        result = ask_claude(params)
    elif args.action == 'cancel_task':
        result = cancel_task(params)
    elif args.action == 'delete_task':
        result = delete_task(params)
    elif args.action == 'delete_task_result':
        result = delete_task_result(params)
    elif args.action == 'reset_task':
        result = reset_task(params)
    elif args.action == 'update_task':
        result = update_task(params)
    elif args.action == 'process_queue':
        result = process_queue(params)
    elif args.action == 'execute_queue':
        result = execute_queue(params)
    elif args.action == 'mark_task_in_progress':
        result = mark_task_in_progress(params)
    elif args.action == 'log_task_completion':
        result = log_task_completion(params)
    elif args.action == 'self_assign_from_doc':
        result = self_assign_from_doc(params)
    else:
        result = {
            'status': 'error',
            'message': f'Unknown action: {args.action}',
            'available_actions': [
                'assign_task', 'assign_demo_task', 'batch_assign_tasks',
                'check_task_status', 'get_task_result', 'get_all_results',
                'get_recent_tasks', 'ask_claude', 'cancel_task', 'delete_task',
                'delete_task_result', 'reset_task', 'update_task', 'process_queue',
                'execute_queue', 'mark_task_in_progress', 'log_task_completion',
                'self_assign_from_doc'
            ]
        }

    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()