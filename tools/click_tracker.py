#!/usr/bin/env python3
import json
import os
import time
from datetime import datetime
from pynput import mouse

# Output file in /data
OUTPUT_FILE = os.path.expanduser("~/Orchestrate Github/orchestrate-jarvis/")

click_count = 0
click_events = []

def on_click(x, y, button, pressed):
    global click_count, click_events
    if pressed:  # Count only press, not release
        click_count += 1
        click_events.append({
            "count": click_count,
            "timestamp": datetime.now().isoformat(),
            "button": str(button),
            "position": (x, y)
        })
        print(f"🖱️ Click #{click_count} at {x},{y} ({button})")

def main():
    print("🟢 Canvas Click Tracker running.")
    print("Press Ctrl+C to stop and save JSON.")
    listener = mouse.Listener(on_click=on_click)
    listener.start()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n🔚 Stopping tracker...")
        data = {
            "total_clicks": click_count,
            "events": click_events,
            "ended_at": datetime.now().isoformat()
        }
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"✅ Saved click log to {OUTPUT_FILE}")
        listener.stop()

if __name__ == "__main__":
    main()