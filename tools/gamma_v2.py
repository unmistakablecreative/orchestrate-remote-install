#!/usr/bin/env python3
import os
import json
import time
import re
import requests
from datetime import datetime

# === CONFIG ===
GAMMA_API_KEY = "sk-gamma-yypuhsTyv7LNHtcnn1wQdN49J5WMoX49a2IyWklpog"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
QUEUE_PATH = os.path.join(DATA_DIR, "gamma_queue.json")
PARAMS_PATH = os.path.join(DATA_DIR, "gamma_params.json")
EXPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "exports")
GAMMA_ENDPOINT = "https://public-api.gamma.app/v0.2/generations"
GAMMA_POLL_ENDPOINT = "https://public-api.gamma.app/v0.2/generations/{}"

# === HELPERS ===
def write_deck_input(params):
    """Create or update .txt file from input text"""
    text = params.get("text", "").strip()
    name = params.get("name", "untitled").strip().replace(" ", "_")
    if not text:
        return {"status": "error", "message": "No text provided."}
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, f"{name}.txt")
    
    # Check if file exists to determine if updating
    action = "updated" if os.path.exists(path) else "created"
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return {"status": "success", "action": action, "saved_to": path, "preview": text[:80]}

def read_deck_input(params):
    """Read existing .txt file"""
    name = params.get("name", "").strip().replace(" ", "_")
    if not name:
        return {"status": "error", "message": "No filename provided"}
    
    path = os.path.join(DATA_DIR, f"{name}.txt")
    if not os.path.exists(path):
        return {"status": "error", "message": f"File not found: {path}"}
    
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    
    return {"status": "success", "filename": f"{name}.txt", "text": text}

def list_deck_inputs(params=None):
    """List all .txt files in data directory"""
    if not os.path.exists(DATA_DIR):
        return {"status": "success", "files": []}
    
    files = [f for f in os.listdir(DATA_DIR) if f.endswith(".txt")]
    file_info = []
    for fname in files:
        path = os.path.join(DATA_DIR, fname)
        stat = os.stat(path)
        file_info.append({
            "name": fname,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })
    
    return {"status": "success", "files": file_info}

def clean_input_for_gamma(text):
    """
    Strip all garbage from input text before sending to Gamma.
    Removes: code blocks, JSON examples, API docs, curl commands, etc.
    Keeps: titles, bullets, slide separators (---)
    """
    lines = text.split('\n')
    cleaned_lines = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()

        # Toggle code block state
        if '```' in line:
            in_code_block = not in_code_block
            continue

        # Skip lines inside code blocks
        if in_code_block:
            continue

        # Skip empty lines (we'll add them back strategically)
        if not stripped:
            continue

        # Skip documentation/API junk
        skip_patterns = [
            r'^curl\s+',                # curl commands
            r'^\{',                      # JSON objects
            r'^\}',
            r'^"[a-zA-Z]+":',           # JSON keys
            r'^\|',                      # Tables
            r'^https?://',              # URLs on their own line
            r'^>',                       # Quote blocks
            r'^\d{3}\s',                # HTTP status codes
            r'^Updated\s+\d+\s+days',   # Doc timestamps
            r'^\*\*\*',                  # Separators
            r'^sk-gamma-',              # API keys
            r'^generationId',           # API response fields
            r'^statusCode',
            r'^Functionality,\s+rate',  # Warning text
        ]

        if any(re.match(pattern, stripped) for pattern in skip_patterns):
            continue

        # Keep slide separators (---)
        if re.match(r'^-{3,}$', stripped):
            cleaned_lines.append('\n---\n')
            continue

        # Keep titles (lines starting with # or bold **)
        if stripped.startswith('#') or stripped.startswith('**'):
            cleaned_lines.append(line)
            continue

        # Keep bullets
        if stripped.startswith('*') or stripped.startswith('-') or re.match(r'^\d+\.', stripped):
            cleaned_lines.append(line)
            continue

        # Keep regular text (but watch for junk)
        if len(stripped) > 10 and not stripped.startswith('[') and not stripped.endswith(']'):
            cleaned_lines.append(line)

    # Join and clean up extra whitespace
    result = '\n'.join(cleaned_lines)
    result = re.sub(r'\n{3,}', '\n\n', result)  # Max 2 consecutive newlines

    return result.strip()


def load_gamma_params(profile="default"):
    """Load Gamma API parameters from configuration file for specified profile"""
    if not os.path.exists(PARAMS_PATH):
        # Return default hardcoded params if config file doesn't exist
        return {
            "textMode": "condense",
            "cardSplit": "inputTextBreaks",
            "numCards": 10,
            "additionalInstructions": "Only use the provided content. Do not add code examples, API documentation, or technical implementation details. Each card should have a clear title and 2-5 bullet points maximum. Keep it clean and visual.",
            "textOptions": {
                "amount": "brief"
            },
            "imageOptions": {
                "source": "aiGenerated",
                "model": "flux-1-quick"
            }
        }

    with open(PARAMS_PATH, "r", encoding="utf-8") as f:
        all_profiles = json.load(f)

    # Get requested profile, fallback to default if not found
    gamma_params = all_profiles.get(profile, all_profiles.get("default"))

    if not gamma_params:
        raise ValueError(f"Profile '{profile}' not found and no default profile exists")

    return gamma_params


def create_deck(params):
    """Create a gamma deck with specified number of cards using profile-based configuration"""
    filename = params.get("filename")
    profile = params.get("param_profile", "default")  # Profile to use
    clean_input_flag = params.get("clean_input", True)  # Default to cleaning

    # Load base parameters from profile
    gamma_params = load_gamma_params(profile)

    # Allow parameter overrides (numCards, textMode, etc.)
    # User can pass specific params to override profile defaults
    if "num_cards" in params:
        gamma_params["numCards"] = params["num_cards"]
    if "text_mode" in params:
        gamma_params["textMode"] = params["text_mode"]
    if "additional_instructions" in params:
        gamma_params["additionalInstructions"] = params["additional_instructions"]

    if not filename:
        return {"status": "error", "message": "Missing filename param"}

    file_path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {file_path}"}

    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    # Clean input to remove garbage
    if clean_input_flag:
        text = clean_input_for_gamma(text)

    # Build payload using profile parameters and spreading
    payload = {
        "inputText": text,
        **gamma_params  # Spread all profile parameters
    }

    try:
        res = requests.post(
            GAMMA_ENDPOINT,
            headers={
                "X-API-KEY": GAMMA_API_KEY,
                "Content-Type": "application/json"
            },
            json=payload
        )
        data = res.json()

        if res.status_code not in (200, 201):
            return {"status": "error", "message": data.get("message", "Request failed")}

        _id = data.get("generationId")
        num_cards_used = gamma_params.get("numCards", 10)
        update_queue(_id, filename, num_cards_used)

        return {
            "status": "success",
            "id": _id,
            "filename": filename,
            "profile": profile,
            "num_cards": num_cards_used
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def create_deck_batch(params=None):
    """Create decks for all .txt files in data directory"""
    files = [f for f in os.listdir(DATA_DIR) if f.endswith(".txt")]
    num_cards = params.get("num_cards", 10) if params else 10
    
    results = []
    for fname in files:
        result = create_deck({"filename": fname, "num_cards": num_cards})
        results.append(result)
    
    return {"status": "success", "results": results}

def poll(id):
    """Poll gamma API for generation status"""
    try:
        res = requests.get(
            GAMMA_POLL_ENDPOINT.format(id),
            headers={"X-API-KEY": GAMMA_API_KEY}
        )
        return res.json()
    except:
        return {}

def poll_and_download(params):
    """Poll for completion and download PDF when ready"""
    id = params.get("id")
    if not id:
        return {"status": "error", "message": "Missing id parameter"}

    filename = params.get("filename", f"deck_{id}")
    max_attempts = params.get("max_attempts", 60)  # Default 5 minutes (60 * 5s)
    poll_interval = params.get("poll_interval", 5)  # Default 5 seconds

    for attempt in range(max_attempts):
        result = poll(id)
        status = result.get("status")

        if status in ("complete", "completed"):
            # Check for both downloadUrl (legacy) and gammaUrl (current API)
            download_url = result.get("downloadUrl")
            gamma_url = result.get("gammaUrl")

            if not download_url and not gamma_url:
                return {
                    "status": "error",
                    "message": "No download or viewing URL in completed response",
                    "result": result
                }

            # If there's a direct download URL, use it
            if download_url:
                os.makedirs(EXPORT_DIR, exist_ok=True)
                output_filename = filename.replace(".txt", f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
                output_path = os.path.join(EXPORT_DIR, output_filename)

                import subprocess
                curl_cmd = ["curl", "-o", output_path, download_url]
                try:
                    subprocess.run(curl_cmd, check=True, capture_output=True)
                    return {
                        "status": "success",
                        "message": f"PDF downloaded successfully after {attempt + 1} attempts",
                        "download_path": output_path,
                        "generation_id": id,
                        "gamma_url": gamma_url,
                        "attempts": attempt + 1
                    }
                except subprocess.CalledProcessError as e:
                    return {
                        "status": "error",
                        "message": f"Curl download failed: {e.stderr.decode()}",
                        "url": download_url
                    }
            else:
                # No direct download available - return viewing URL
                return {
                    "status": "success",
                    "message": f"Generation completed after {attempt + 1} attempts. No direct PDF download available from API.",
                    "generation_id": id,
                    "gamma_url": gamma_url,
                    "note": "View the presentation at gamma_url. PDF export may be available through the web interface.",
                    "attempts": attempt + 1,
                    "credits_deducted": result.get("credits", {}).get("deducted"),
                    "credits_remaining": result.get("credits", {}).get("remaining")
                }

        elif status == "error":
            return {
                "status": "error",
                "message": "Generation failed on Gamma side",
                "result": result
            }

        # Still processing, wait and retry
        time.sleep(poll_interval)

    return {
        "status": "error",
        "message": f"Timeout after {max_attempts} attempts",
        "last_status": result.get("status")
    }

def check_deck_status(params):
    """Check status of a specific deck generation"""
    id = params.get("id")
    if not id:
        return {"status": "error", "message": "Missing id"}
    result = poll(id)
    return {"status": "success", "result": result}

def check_all_decks(params=None):
    """Check status of all deck generations in queue"""
    queue = load_queue()
    results = []
    
    for id, meta in queue.items():
        result = poll(id)
        status = result.get("status")
        
        if status == "complete":
            url = result.get("downloadUrl")
            saved = download_result(url, meta.get("filename"))
            result.update({"downloaded": saved})
        
        results.append({
            "id": id, 
            "status": status, 
            "meta": meta, 
            "result": result
        })
    
    return {"status": "success", "results": results}

def download_result(url, original_name):
    """Download completed deck PDF"""
    if not url:
        return None
    
    os.makedirs(EXPORT_DIR, exist_ok=True)
    filename = original_name.replace(".txt", f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    path = os.path.join(EXPORT_DIR, filename)
    
    try:
        r = requests.get(url)
        with open(path, "wb") as f:
            f.write(r.content)
        return path
    except:
        return None

def update_queue(id, filename, num_cards=10):
    """Update queue with new generation"""
    queue = load_queue()
    queue[id] = {
        "filename": filename, 
        "num_cards": num_cards,
        "created": datetime.utcnow().isoformat()
    }
    with open(QUEUE_PATH, "w") as f:
        json.dump(queue, f, indent=2)

def load_queue():
    """Load generation queue from disk"""
    if not os.path.exists(QUEUE_PATH):
        return {}
    with open(QUEUE_PATH, "r") as f:
        return json.load(f)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Gamma Deck Manager")
    parser.add_argument("action", choices=[
        "write_deck_input",
        "read_deck_input",
        "list_deck_inputs",
        "create_deck",
        "create_deck_batch",
        "poll_and_download",
        "check_deck_status",
        "check_all_decks"
    ])
    parser.add_argument("--params", type=str, help="JSON params for action")
    args = parser.parse_args()

    params = json.loads(args.params) if args.params else {}

    if args.action == "write_deck_input":
        result = write_deck_input(params)
    elif args.action == "read_deck_input":
        result = read_deck_input(params)
    elif args.action == "list_deck_inputs":
        result = list_deck_inputs(params)
    elif args.action == "create_deck":
        result = create_deck(params)
    elif args.action == "create_deck_batch":
        result = create_deck_batch(params)
    elif args.action == "poll_and_download":
        result = poll_and_download(params)
    elif args.action == "check_deck_status":
        result = check_deck_status(params)
    elif args.action == "check_all_decks":
        result = check_all_decks(params)
    else:
        result = {"status": "error", "message": f"Unknown action: {args.action}"}

    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()