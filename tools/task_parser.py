#!/usr/bin/env python3
"""
Task Parser - Clean Version

Parses tasks from markdown documents.
Each task starts with a header (# or ##).
Everything until the next header is the task content.

FULL CONTENT PRESERVED. STABLE TASK IDS.
"""

import re
import hashlib
from typing import List, Dict, Optional


def extract_doc_id_from_links(text: str) -> Optional[str]:
    """Extract doc_id from [text](/doc/id) patterns."""
    matches = re.findall(r'\[([^\]]+)\]\(/doc/([a-f0-9-]+)\)', text)
    if matches:
        return matches[0][1]
    return None


def generate_task_id(description: str) -> str:
    """
    Generate deterministic task_id from CORE CONTENT ONLY.
    
    Strips ALL formatting/whitespace variations.
    Same semantic content = same ID ALWAYS.
    
    Format: {slug}_{hash}
    """
    # Remove ALL markdown syntax
    text = re.sub(r'#+\s*', '', description)  # Headers
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Bold
    text = re.sub(r'\*([^*]+)\*', r'\1', text)  # Italic  
    text = re.sub(r'`([^`]+)`', r'\1', text)  # Inline code
    text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)  # Code blocks
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # Links
    
    # Collapse ALL whitespace to single spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Remove special chars
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    
    # Normalize
    normalized = text.strip().lower()
    
    # Generate slug from first 5 words
    words = normalized.split()[:5]
    slug = '_'.join(words) if words else 'task'
    
    # Hash the fully normalized content
    content_hash = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:12]
    
    return f"{slug}_{content_hash}"


def extract_tasks_from_doc(doc_text: str) -> List[Dict]:
    """
    Extract tasks from markdown document.
    
    Rules:
    1. Lines starting with # (any level) = new task header
    2. Everything after header until next header = task content
    3. Full content preserved - NO FILTERING
    
    Returns:
        List of task dicts with:
        {
            "task_id": "deterministic_id_based_on_content",
            "description": "FULL task text including header and all content",
            "context": {"doc_id": "..." if found}
        }
    """
    if not doc_text or not doc_text.strip():
        return []
    
    tasks = []
    lines = doc_text.split('\n')
    
    current_task_lines = []
    in_task = False
    
    for line in lines:
        stripped = line.strip()
        
        # Check if this is a header (starts with #)
        if stripped.startswith('#'):
            # Save previous task if exists
            if in_task and current_task_lines:
                full_text = '\n'.join(current_task_lines)
                if full_text.strip():
                    # Extract doc_id if present
                    doc_id = extract_doc_id_from_links(full_text)
                    
                    # Generate stable task_id from content
                    task_id = generate_task_id(full_text)
                    
                    task = {
                        "task_id": task_id,
                        "description": full_text,  # FULL CONTENT
                        "context": {}
                    }
                    
                    if doc_id:
                        task["context"]["doc_id"] = doc_id
                    
                    tasks.append(task)
            
            # Start new task
            current_task_lines = [line]
            in_task = True
        else:
            # Add to current task (preserving original formatting)
            if in_task:
                current_task_lines.append(line)
    
    # Don't forget last task
    if in_task and current_task_lines:
        full_text = '\n'.join(current_task_lines)
        if full_text.strip():
            doc_id = extract_doc_id_from_links(full_text)
            task_id = generate_task_id(full_text)
            
            task = {
                "task_id": task_id,
                "description": full_text,  # FULL CONTENT
                "context": {}
            }
            
            if doc_id:
                task["context"]["doc_id"] = doc_id
            
            tasks.append(task)
    
    return tasks


if __name__ == "__main__":
    # Quick test
    test_doc = """# Task 1
Do something.

Some details.

# Task 2  
Do something else."""
    
    result = extract_tasks_from_doc(test_doc)
    print(f"Parsed {len(result)} tasks")
    for task in result:
        print(f"  - {task['task_id']}")
        print(f"    Content length: {len(task['description'])} chars")