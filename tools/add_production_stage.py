#!/usr/bin/env python3
"""
Script to add production_stage field to all podcast index entries
Run this from the /tools directory
"""
import json
import os
from datetime import datetime

# Get the parent directory (root of project)
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
index_path = os.path.join(project_root, 'data', 'podcast_index.json')

# Load the podcast index
with open(index_path, 'r') as f:
    index = json.load(f)

entries = index.get('entries', {})
updated_count = 0

print("🚀 Adding production_stage field to all entries...\n")

for key, entry in entries.items():
    status = entry.get('status', '')
    scheduled_date = entry.get('scheduled_publish_date', '')
    title = entry.get('title', '')
    summary = entry.get('summary', '')
    
    # Rule 1: If uploaded → mark as published
    if status == 'uploaded':
        entry['production_stage'] = 'published'
    
    # Rule 2: If has title AND summary, but scheduled_date is TBD or missing → needs-scheduling
    elif title and summary and (scheduled_date == 'TBD' or not scheduled_date):
        entry['production_stage'] = 'needs-scheduling'
    
    # Rule 3: If title or summary is empty → needs-metadata
    elif not title or not summary:
        entry['production_stage'] = 'needs-metadata'
    
    # Default fallback (shouldn't hit this, but just in case)
    else:
        entry['production_stage'] = 'needs-scheduling'
    
    updated_count += 1

# Save the updated index
with open(index_path, 'w') as f:
    json.dump(index, f, indent=2)

print(f"✅ Added production_stage field to {updated_count} entries\n")

# Show distribution of production_stage values
print("📊 Production Stage Distribution:")
print("=" * 50)
stage_counts = {}
for key, entry in entries.items():
    stage = entry.get('production_stage', 'unknown')
    stage_counts[stage] = stage_counts.get(stage, 0) + 1

for stage, count in sorted(stage_counts.items()):
    print(f"  {stage:25} {count:3} episodes")

print("\n🎯 Now you can search by production_stage like:")
print('  {"filters": {"production_stage": "nov-2025"}}')
print('  {"filters": {"production_stage": "needs-metadata"}}')
print("\n💾 Updated podcast index saved!")