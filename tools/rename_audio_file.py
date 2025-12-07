import os
import sys
import json
import re

AUDIO_DIR = "audio"
INDEX_FILE = "data/podcast_index.json"

# Helper to slugify a string
def slugify(value):
    return re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')

def rename_audio_file(params):
    key = params.get("entry_key")
    if not key:
        return {"status": "error", "message": "Missing entry_key param"}

    index_path = params.get("index_file", "data/podcast_index.json")

    try:
        with open(index_path, "r") as f:
            index = json.load(f)["entries"]
    except Exception as e:
        return {"status": "error", "message": f"Failed to load podcast index: {str(e)}"}

    if key not in index:
        return {"status": "error", "message": f"Entry '{key}' not found in podcast index."}

    slug = slugify(key)

    for filename in os.listdir(AUDIO_DIR):
        if not filename.lower().endswith(".mp3"):
            continue

        name_only = os.path.splitext(filename)[0]
        if slugify(name_only) == slug:
            src_path = os.path.join(AUDIO_DIR, filename)
            dst_path = os.path.join(AUDIO_DIR, f"{slug}.mp3")

            if src_path == dst_path:
                return {"status": "noop", "message": "Filename already correct."}

            try:
                os.rename(src_path, dst_path)
                return {"status": "success", "message": f"Renamed {filename} → {slug}.mp3"}
            except Exception as e:
                return {"status": "error", "message": f"Rename failed: {str(e)}"}

    # No audio file found - this is expected for podcasts not recorded yet
    return {"status": "noop", "message": f"No audio file for: {key}"}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("action")
    parser.add_argument("--params")
    args = parser.parse_args()

    if args.action == "rename_audio_file":
        params = json.loads(args.params or "{}")
        result = rename_audio_file(params)
        print(json.dumps(result, indent=2))