#!/usr/bin/env python3
"""
Telemetry Observer - Automatic token usage anomaly detection and reporting
Generates daily reports of execution patterns and inefficiencies.
"""

import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any
from pathlib import Path
import subprocess

# File paths
BASE_DIR = Path(__file__).parent.parent
TOKEN_TELEMETRY = BASE_DIR / "data" / "token_telemetry.json"
TASK_RESULTS = BASE_DIR / "data" / "claude_task_results.json"
EXECUTION_LOG = BASE_DIR / "data" / "execution_log.json"
QUEUE_FILE = BASE_DIR / "data" / "claude_task_queue.json"


def read_json(filepath: Path) -> Dict:
    """Read JSON file with error handling."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def filter_by_date(items: List[Dict], date_str: str, timestamp_key: str = "timestamp") -> List[Dict]:
    """Filter items by date string (YYYY-MM-DD or 'today')."""
    if date_str == "today":
        target_date = datetime.now().strftime("%Y-%m-%d")
    else:
        target_date = date_str

    return [
        item for item in items
        if item.get(timestamp_key, "").startswith(target_date)
    ]


def detect_anomalies(task_results: Dict, execution_log: Dict, date: str) -> List[Dict]:
    """
    Detect token usage anomalies across multiple data sources.

    Anomaly rules:
    1. Input/output ratio > 15:1 (context bloat)
    2. Total tokens > 10K for single task (expensive)
    3. Same task executed multiple times within 1 hour (duplicate work)
    4. Task marked 'completed' but has errors (false completion)
    5. Execution time < 5 seconds but tokens > 5K (inefficient)
    """
    anomalies = []

    # Process task results
    for task_id, result in task_results.get("results", {}).items():
        tokens = result.get("tokens", {})
        input_tokens = tokens.get("input", 0)
        output_tokens = tokens.get("output", 0)
        total_tokens = tokens.get("total", 0)
        exec_time = result.get("execution_time_seconds", 0)
        status = result.get("status", "")
        errors = result.get("errors")

        # Rule 1: High input/output ratio
        if output_tokens > 0:
            ratio = input_tokens / output_tokens
            if ratio > 15:
                anomalies.append({
                    "task_id": task_id,
                    "type": "context_bloat",
                    "severity": "high",
                    "tokens_wasted": input_tokens - (output_tokens * 10),  # Assume 10:1 is acceptable
                    "details": f"Input/output ratio {ratio:.1f}:1 (expected <15:1)",
                    "suggestion": "Check for unnecessary context in task description or reduce JSON file sizes",
                    "tokens_input": input_tokens,
                    "tokens_output": output_tokens,
                    "total_tokens": total_tokens
                })

        # Rule 2: Expensive task
        if total_tokens > 10000:
            anomalies.append({
                "task_id": task_id,
                "type": "expensive_task",
                "severity": "medium",
                "tokens_wasted": total_tokens - 10000,
                "details": f"Task used {total_tokens:,} tokens (threshold: 10K)",
                "suggestion": "Break task into smaller subtasks or optimize context loading",
                "total_tokens": total_tokens
            })

        # Rule 3: False completion (has errors but marked complete)
        if status in ["completed", "done"] and errors:
            anomalies.append({
                "task_id": task_id,
                "type": "false_completion",
                "severity": "high",
                "tokens_wasted": total_tokens,
                "details": f"Task marked '{status}' but has errors: {errors}",
                "suggestion": "Review completion logic and error handling",
                "total_tokens": total_tokens
            })

        # Rule 4: Inefficient execution (quick but expensive)
        if exec_time > 0 and exec_time < 5 and total_tokens > 5000:
            anomalies.append({
                "task_id": task_id,
                "type": "inefficient_execution",
                "severity": "low",
                "tokens_wasted": total_tokens - 2000,
                "details": f"Execution took {exec_time:.1f}s but used {total_tokens:,} tokens",
                "suggestion": "Likely loading unnecessary context for simple operation",
                "total_tokens": total_tokens
            })

    # Rule 5: Duplicate executions (check execution log)
    # Read execution log in chunks to avoid memory issues
    try:
        with open(EXECUTION_LOG, 'r') as f:
            exec_data = json.load(f)

        executions = filter_by_date(exec_data.get("executions", []), date)

        # Group by tool+action and check for duplicates within 1 hour
        exec_by_signature = {}
        for exec_item in executions:
            tool = exec_item.get("tool", "")
            action = exec_item.get("action", "")
            timestamp = exec_item.get("timestamp", "")
            signature = f"{tool}.{action}"

            if signature not in exec_by_signature:
                exec_by_signature[signature] = []
            exec_by_signature[signature].append({
                "timestamp": timestamp,
                "token_cost": exec_item.get("token_cost", 0)
            })

        # Find duplicates within 1 hour window
        for signature, execs in exec_by_signature.items():
            if len(execs) > 1:
                execs_sorted = sorted(execs, key=lambda x: x["timestamp"])
                for i in range(len(execs_sorted) - 1):
                    t1 = datetime.fromisoformat(execs_sorted[i]["timestamp"].replace("Z", ""))
                    t2 = datetime.fromisoformat(execs_sorted[i+1]["timestamp"].replace("Z", ""))
                    if (t2 - t1).total_seconds() < 3600:  # 1 hour
                        total_wasted = sum(e["token_cost"] for e in execs_sorted[i:])
                        anomalies.append({
                            "task_id": signature,
                            "type": "duplicate_execution",
                            "severity": "medium",
                            "tokens_wasted": total_wasted,
                            "details": f"Executed {len(execs_sorted) - i} times within 1 hour",
                            "suggestion": "Check for retry logic or duplicate task assignments",
                            "total_tokens": total_wasted
                        })
                        break  # Only report once per signature
    except Exception as e:
        # Execution log parsing failed, skip duplicate detection
        pass

    return anomalies


def calculate_trends(task_results: Dict, prev_date: str) -> Dict:
    """Calculate trends compared to previous day."""
    # For now, just return summary stats
    # In future, could compare to historical data
    results = task_results.get("results", {})

    total_tokens = sum(
        r.get("tokens", {}).get("total", 0)
        for r in results.values()
    )

    total_tasks = len(results)

    avg_tokens = total_tokens / total_tasks if total_tasks > 0 else 0

    return {
        "total_tokens": total_tokens,
        "total_tasks": total_tasks,
        "avg_tokens_per_task": avg_tokens,
        "note": "Historical comparison not yet implemented"
    }


def generate_report(date: str) -> str:
    """Generate markdown report of token telemetry anomalies."""

    # Load data
    task_results = read_json(TASK_RESULTS)

    # Detect anomalies
    anomalies = detect_anomalies(task_results, {}, date)

    # Calculate summary stats
    results = task_results.get("results", {})
    total_tokens = sum(r.get("tokens", {}).get("total", 0) for r in results.values())
    total_tasks = len(results)
    avg_tokens = total_tokens / total_tasks if total_tasks > 0 else 0

    # Calculate average ratio
    ratios = []
    for result in results.values():
        tokens = result.get("tokens", {})
        input_t = tokens.get("input", 0)
        output_t = tokens.get("output", 0)
        if output_t > 0:
            ratios.append(input_t / output_t)
    avg_ratio = sum(ratios) / len(ratios) if ratios else 0

    # Calculate total tokens wasted
    total_wasted = sum(a.get("tokens_wasted", 0) for a in anomalies)

    # Group anomalies by severity
    high_severity = [a for a in anomalies if a.get("severity") == "high"]
    medium_severity = [a for a in anomalies if a.get("severity") == "medium"]
    low_severity = [a for a in anomalies if a.get("severity") == "low"]

    # Build markdown report
    report = f"""# Token Telemetry Report - {date}

## Executive Summary

- **Total Tasks:** {total_tasks}
- **Total Tokens Used:** {total_tokens:,}
- **Average Tokens per Task:** {avg_tokens:.0f}
- **Average Input/Output Ratio:** {avg_ratio:.1f}:1
- **Anomalies Detected:** {len(anomalies)}
- **Estimated Tokens Wasted:** {total_wasted:,}

## Anomalies Detected

### High Severity ({len(high_severity)})
"""

    for anomaly in high_severity:
        report += f"""
**{anomaly['task_id']}** - {anomaly['type']}
- **Issue:** {anomaly['details']}
- **Tokens Wasted:** {anomaly.get('tokens_wasted', 0):,}
- **Suggestion:** {anomaly['suggestion']}
"""

    report += f"\n### Medium Severity ({len(medium_severity)})\n"

    for anomaly in medium_severity:
        report += f"""
**{anomaly['task_id']}** - {anomaly['type']}
- **Issue:** {anomaly['details']}
- **Tokens Wasted:** {anomaly.get('tokens_wasted', 0):,}
- **Suggestion:** {anomaly['suggestion']}
"""

    report += f"\n### Low Severity ({len(low_severity)})\n"

    for anomaly in low_severity:
        report += f"""
**{anomaly['task_id']}** - {anomaly['type']}
- **Issue:** {anomaly['details']}
- **Tokens Wasted:** {anomaly.get('tokens_wasted', 0):,}
- **Suggestion:** {anomaly['suggestion']}
"""

    # Trends section
    trends = calculate_trends(task_results, "")
    report += f"""
## Trends

- **Today's Total:** {trends['total_tokens']:,} tokens
- **Tasks Completed:** {trends['total_tasks']}
- **Average per Task:** {trends['avg_tokens_per_task']:.0f} tokens

{trends['note']}

## Recommendations

"""

    # Generate prioritized recommendations
    if high_severity:
        report += "1. **URGENT:** Address high-severity anomalies first (false completions, context bloat)\n"
    if total_wasted > 50000:
        report += f"2. **HIGH PRIORITY:** Reduce token waste ({total_wasted:,} tokens wasted today)\n"
    if avg_ratio > 10:
        report += f"3. **OPTIMIZE CONTEXT:** Average input/output ratio is {avg_ratio:.1f}:1 (target: <10:1)\n"
    if total_tasks > 20:
        report += "4. **BATCH PROCESSING:** Consider batching similar tasks to reduce context loading\n"

    if not anomalies:
        report += "✅ No significant anomalies detected. System running efficiently.\n"

    return report


def analyze_telemetry(date: str = "today") -> Dict:
    """Analyze telemetry data and return structured results."""
    task_results = read_json(TASK_RESULTS)
    anomalies = detect_anomalies(task_results, {}, date)
    trends = calculate_trends(task_results, "")

    return {
        "date": date,
        "anomalies": anomalies,
        "trends": trends,
        "summary": {
            "total_anomalies": len(anomalies),
            "total_tokens_wasted": sum(a.get("tokens_wasted", 0) for a in anomalies)
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze token telemetry and detect anomalies")
    parser.add_argument("command", choices=["analyze"], help="Command to execute")
    parser.add_argument("--date", default="today", help="Date to analyze (YYYY-MM-DD or 'today')")
    parser.add_argument("--output", choices=["outline", "console", "json"], default="console",
                       help="Output format")

    args = parser.parse_args()

    if args.command == "analyze":
        report_md = generate_report(args.date)

        if args.output == "console":
            print(report_md)

        elif args.output == "json":
            result = analyze_telemetry(args.date)
            print(json.dumps(result, indent=2))

        elif args.output == "outline":
            # Write to outline_docs_queue for processing
            date_str = args.date if args.date != "today" else datetime.now().strftime("%Y-%m-%d")
            filename = f"token-telemetry-report-{date_str}.md"
            filepath = BASE_DIR / "outline_docs_queue" / filename

            with open(filepath, 'w') as f:
                f.write(report_md)

            print(f"✅ Report written to {filepath}")
            print(f"📤 Importing to Outline...")

            # Import to Outline
            import_cmd = [
                "python3",
                str(BASE_DIR / "tools" / "outline_editor.py"),
                "import_doc_from_file",
                "--params",
                json.dumps({
                    "file_path": str(filepath),
                    "publish": True
                })
            ]

            result = subprocess.run(import_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ Successfully imported to Outline")
                try:
                    import_result = json.loads(result.stdout)
                    if "doc_id" in import_result:
                        print(f"📄 Document ID: {import_result['doc_id']}")
                except:
                    pass
            else:
                print(f"❌ Import failed: {result.stderr}")


if __name__ == "__main__":
    main()
