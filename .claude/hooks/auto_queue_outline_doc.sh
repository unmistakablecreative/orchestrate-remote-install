#!/usr/bin/env bash
# Auto-queue outline docs written to outline_docs_queue/
# Runs after Write tool completes

# Get file path from stdin
file_path=$(jq -r '.tool_input.file_path // empty')

# Only process files in outline_docs_queue/
if [[ ! "$file_path" =~ outline_docs_queue/ ]]; then
    exit 0
fi

# Extract filename
filename=$(basename "$file_path")

# Extract title from markdown (first # heading)
title=$(grep -m 1 '^# ' "$file_path" 2>/dev/null | sed 's/^# //' || echo "$filename")

# Queue the document (fire-and-forget)
python3 execution_hub.py execute_task --params "{
  \"tool_name\": \"outline_editor\",
  \"action\": \"queue_doc\",
  \"params\": {
    \"file\": \"$filename\",
    \"title\": \"$title\",
    \"collection\": \"inbox\"
  }
}" > /dev/null 2>&1 &

# Print confirmation
echo "✓ Auto-queued: $filename → Outline inbox"

exit 0
