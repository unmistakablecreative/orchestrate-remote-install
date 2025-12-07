#!/usr/bin/env python3
"""
Engine Launcher - Manages all OrchestrateOS background engines

Spawns and monitors engines as subprocesses, restarting them on crash.
Launchd manages this single launcher process instead of individual engines.
"""

import os
import sys
import json
import subprocess
import time
import signal
from pathlib import Path


BASE_DIR = Path(__file__).parent.parent
REGISTRY_PATH = BASE_DIR / "data" / "engine_registry.json"


class EngineManager:
    def __init__(self):
        self.engines = {}  # name -> subprocess.Popen
        self.running = True

        # Handle shutdown signals
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)

    def load_registry(self):
        """Load engine registry from JSON"""
        if not REGISTRY_PATH.exists():
            print(f"ERROR: Registry not found at {REGISTRY_PATH}")
            return []

        with open(REGISTRY_PATH, 'r') as f:
            registry = json.load(f)

        return registry.get('engines', [])

    def start_engine(self, engine_file):
        """Start a single engine as subprocess"""
        engine_path = BASE_DIR / "tools" / engine_file

        if not engine_path.exists():
            print(f"ERROR: Engine not found: {engine_path}")
            return None

        try:
            # Start engine with run_engine action
            process = subprocess.Popen(
                [sys.executable, str(engine_path), "run_engine"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(BASE_DIR)
            )
            print(f"Started {engine_file} (PID: {process.pid})")
            return process
        except Exception as e:
            print(f"ERROR starting {engine_file}: {e}")
            return None

    def monitor_engines(self):
        """Monitor all engines and restart if crashed"""
        engine_files = self.load_registry()

        # Initial launch
        for engine_file in engine_files:
            process = self.start_engine(engine_file)
            if process:
                self.engines[engine_file] = process

        print(f"Engine Manager running with {len(self.engines)} engines")

        # Monitor loop
        while self.running:
            time.sleep(5)  # Check every 5 seconds

            for engine_file, process in list(self.engines.items()):
                # Check if process died
                if process.poll() is not None:
                    print(f"CRASH DETECTED: {engine_file} (exit code: {process.returncode})")
                    print(f"Restarting {engine_file}...")

                    # Restart
                    new_process = self.start_engine(engine_file)
                    if new_process:
                        self.engines[engine_file] = new_process
                    else:
                        print(f"FAILED to restart {engine_file}")

    def shutdown(self, signum, frame):
        """Handle shutdown gracefully"""
        print("\nShutting down Engine Manager...")
        self.running = False

        # Kill all child engines
        for engine_file, process in self.engines.items():
            print(f"Stopping {engine_file}...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

        sys.exit(0)


def main():
    print("="*60)
    print("OrchestrateOS Engine Manager")
    print("="*60)

    manager = EngineManager()
    manager.monitor_engines()


if __name__ == "__main__":
    main()