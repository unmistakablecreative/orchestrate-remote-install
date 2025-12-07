#!/usr/bin/env python3
"""
orchestrate_analyzer.py - Centralized system performance analysis tool

Consolidates execution analysis, token telemetry, and performance reporting.
Outputs JSON that can be transformed into human-readable Outline docs.

Actions:
- get_execution_stats: Success rates, timing, error patterns
- get_token_metrics: Token usage per task and session
- get_system_report: Comprehensive JSON for full performance report
- get_task_history: Recent task completion history
"""

import json
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import statistics
from pathlib import Path

# Data file paths
EXEC_LOG = "data/execution_log.json"
TASK_QUEUE = "data/claude_task_queue.json"
TASK_RESULTS = "data/claude_task_results.json"
THREAD_STATE = "data/thread_state.json"
WORKING_MEMORY = "data/working_memory.json"

ACTIONS = {
    "get_execution_stats": {
        "description": "Get execution statistics including success rates, timing, and error patterns",
        "params": {
            "days": {"type": "int", "required": False, "default": 7, "description": "Number of days to analyze"}
        }
    },
    "get_token_metrics": {
        "description": "Get token usage metrics per task and session",
        "params": {
            "days": {"type": "int", "required": False, "default": 7, "description": "Number of days to analyze"}
        }
    },
    "get_system_report": {
        "description": "Generate comprehensive system performance report as JSON",
        "params": {
            "days": {"type": "int", "required": False, "default": 7, "description": "Number of days to analyze"},
            "include_recommendations": {"type": "bool", "required": False, "default": True, "description": "Include improvement recommendations"}
        }
    },
    "get_task_history": {
        "description": "Get recent task completion history from working memory",
        "params": {
            "limit": {"type": "int", "required": False, "default": 20, "description": "Number of recent tasks to return"}
        }
    }
}


def _load_json(filepath, default=None):
    """Load JSON file safely"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def _filter_by_date(data, days, timestamp_key="timestamp"):
    """Filter data by date range"""
    if not data or days <= 0:
        return data

    cutoff = datetime.now() - timedelta(days=days)
    filtered = []

    for item in data:
        if isinstance(item, dict):
            ts = item.get(timestamp_key) or item.get("created_at")
            if ts:
                try:
                    item_date = datetime.fromisoformat(ts.replace("Z", "+00:00").replace("+00:00", ""))
                    if item_date >= cutoff:
                        filtered.append(item)
                except (ValueError, AttributeError):
                    filtered.append(item)  # Include if can't parse date
            else:
                filtered.append(item)  # Include if no timestamp

    return filtered if filtered else data


def _calculate_success_metrics(executions):
    """Calculate success rate metrics"""
    if not executions:
        return {"total_executions": 0, "successful_executions": 0, "success_rate": 0, "failure_rate": 0}

    total = len(executions)
    successes = len([e for e in executions if e.get("status") in ["success", "reconstruction_success"]])

    return {
        "total_executions": total,
        "successful_executions": successes,
        "success_rate": round((successes / total) * 100, 2) if total > 0 else 0,
        "failure_rate": round(((total - successes) / total) * 100, 2) if total > 0 else 0
    }


def _analyze_timing(executions):
    """Analyze execution timing"""
    times = []
    for e in executions:
        if isinstance(e, dict):
            details = e.get("execution_details", {})
            exec_time = details.get("execution_time_ms")
            if exec_time is not None:
                times.append(exec_time)

    if not times:
        return {"no_timing_data": True}

    return {
        "total_timed": len(times),
        "avg_ms": round(statistics.mean(times), 2),
        "median_ms": round(statistics.median(times), 2),
        "min_ms": min(times),
        "max_ms": max(times),
        "std_dev_ms": round(statistics.stdev(times), 2) if len(times) > 1 else 0
    }


def _analyze_tool_usage(executions):
    """Analyze which tools are used most"""
    tool_counts = Counter()
    tool_success = defaultdict(lambda: {"success": 0, "failure": 0})

    for e in executions:
        if isinstance(e, dict):
            tool = e.get("tool", "unknown")
            status = e.get("status", "unknown")
            tool_counts[tool] += 1

            if status in ["success", "reconstruction_success"]:
                tool_success[tool]["success"] += 1
            else:
                tool_success[tool]["failure"] += 1

    # Calculate per-tool success rates
    tool_rates = {}
    for tool, counts in tool_success.items():
        total = counts["success"] + counts["failure"]
        if total > 0:
            tool_rates[tool] = {
                "total": total,
                "success_rate": round((counts["success"] / total) * 100, 2)
            }

    return {
        "tool_usage_counts": dict(tool_counts.most_common(15)),
        "tool_success_rates": tool_rates
    }


def _analyze_errors(executions):
    """Analyze error patterns"""
    errors = [e for e in executions if e.get("status") not in ["success", "reconstruction_success"]]

    if not errors:
        return {"total_errors": 0, "error_types": {}}

    error_types = Counter(e.get("status", "unknown") for e in errors)
    tools_with_errors = Counter(e.get("tool", "unknown") for e in errors)

    return {
        "total_errors": len(errors),
        "error_types": dict(error_types.most_common()),
        "tools_with_errors": dict(tools_with_errors.most_common(10))
    }


def get_execution_stats(days=7):
    """Get execution statistics"""
    raw = _load_json(EXEC_LOG, [])
    # Handle both list format and {"executions": []} format
    executions = raw if isinstance(raw, list) else raw.get("executions", [])

    # Filter by date
    filtered = _filter_by_date(executions, days)

    return {
        "period_days": days,
        "analysis_date": datetime.now().isoformat(),
        "success_metrics": _calculate_success_metrics(filtered),
        "timing_metrics": _analyze_timing(filtered),
        "tool_usage": _analyze_tool_usage(filtered),
        "error_analysis": _analyze_errors(filtered)
    }


def get_token_metrics(days=7):
    """Get token usage metrics from task results"""
    # Primary source: claude_task_results.json
    task_results = _load_json(TASK_RESULTS, {})
    results_dict = task_results.get("results", {}) if isinstance(task_results, dict) else {}

    # Filter by date and collect token data
    cutoff = datetime.now() - timedelta(days=days)
    token_data = []

    for task_id, result in results_dict.items():
        # Check date
        completed_at = result.get("completed_at", "")
        if completed_at:
            try:
                task_date = datetime.fromisoformat(completed_at.replace("Z", "").split("+")[0])
                if task_date < cutoff:
                    continue
            except (ValueError, AttributeError):
                pass

        # Get token info
        tokens = result.get("tokens", {})
        token_cost = result.get("token_cost", 0)

        if tokens or token_cost:
            token_data.append({
                "task_id": task_id,
                "input": tokens.get("input", 0),
                "output": tokens.get("output", 0),
                "total": tokens.get("total", token_cost),
                "status": result.get("status"),
                "completed_at": completed_at
            })

    if not token_data:
        return {"period_days": days, "no_token_data": True, "message": "No tasks with token data in this period"}

    total_input = sum(t["input"] for t in token_data)
    total_output = sum(t["output"] for t in token_data)
    total_tokens = sum(t["total"] for t in token_data)

    # Load thread state for session info
    thread_state = _load_json(THREAD_STATE, {})

    return {
        "period_days": days,
        "analysis_date": datetime.now().isoformat(),
        "total_tasks_with_tokens": len(token_data),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_tokens,
        "avg_tokens_per_task": round(total_tokens / len(token_data), 0) if token_data else 0,
        "avg_input_per_task": round(total_input / len(token_data), 0) if token_data else 0,
        "avg_output_per_task": round(total_output / len(token_data), 0) if token_data else 0,
        "recent_tasks": token_data[-5:],
        "current_session": {
            "thread_score": thread_state.get("score", 100),
            "tokens_used": thread_state.get("tokens_used", 0),
            "token_budget": thread_state.get("token_budget", 100000)
        }
    }


def get_task_history(limit=20):
    """Get recent task completion history"""
    working_memory = _load_json(WORKING_MEMORY, [])
    # Handle both list format and {"recent_tasks": []} format
    recent_tasks = working_memory if isinstance(working_memory, list) else working_memory.get("recent_tasks", [])

    # Also check task results
    task_results = _load_json(TASK_RESULTS, {})
    # Handle {"results": {...}} format
    results_dict = task_results.get("results", {}) if isinstance(task_results, dict) else {}
    completed = [{"task_id": k, **v} for k, v in results_dict.items()]

    # Combine and dedupe
    all_tasks = []
    seen_ids = set()

    for task in recent_tasks + completed:
        task_id = task.get("task_id")
        if task_id and task_id not in seen_ids:
            seen_ids.add(task_id)
            all_tasks.append(task)

    # Sort by timestamp (most recent first)
    all_tasks.sort(key=lambda x: x.get("timestamp", x.get("completed_at", "")), reverse=True)

    return {
        "analysis_date": datetime.now().isoformat(),
        "total_in_history": len(all_tasks),
        "returned_count": min(limit, len(all_tasks)),
        "recent_tasks": all_tasks[:limit]
    }


def get_system_report(days=7, include_recommendations=True):
    """Generate comprehensive system performance report"""
    execution_stats = get_execution_stats(days)
    token_metrics = get_token_metrics(days)
    task_history = get_task_history(20)

    # Load additional context
    task_queue = _load_json(TASK_QUEUE, {"tasks": {}})
    tasks_data = task_queue.get("tasks", {})
    # Handle both dict and list formats
    if isinstance(tasks_data, dict):
        pending_tasks = [{"task_id": k, **v} for k, v in tasks_data.items() if v.get("status") == "pending"]
    else:
        pending_tasks = [t for t in tasks_data if t.get("status") == "pending"]

    report = {
        "report_metadata": {
            "generated_at": datetime.now().isoformat(),
            "period_days": days,
            "report_type": "system_performance"
        },
        "executive_summary": {
            "total_executions": execution_stats["success_metrics"]["total_executions"],
            "success_rate": execution_stats["success_metrics"]["success_rate"],
            "avg_execution_time_ms": execution_stats["timing_metrics"].get("avg_ms", "N/A"),
            "total_tokens_used": token_metrics.get("total_tokens_used", 0),
            "pending_tasks": len(pending_tasks),
            "recent_completions": task_history["returned_count"]
        },
        "execution_analysis": execution_stats,
        "token_analysis": token_metrics,
        "task_history": task_history,
        "queue_status": {
            "pending_count": len(pending_tasks),
            "pending_tasks": [{"id": t.get("task_id"), "description": t.get("description", "")[:100]} for t in pending_tasks[:10]]
        }
    }

    if include_recommendations:
        recommendations = []

        # Success rate recommendations
        success_rate = execution_stats["success_metrics"]["success_rate"]
        if success_rate < 90:
            recommendations.append({
                "area": "reliability",
                "priority": "high",
                "issue": f"Success rate is {success_rate}% - below 90% target",
                "recommendation": "Review error patterns and fix most common failure modes"
            })

        # Performance recommendations
        avg_time = execution_stats["timing_metrics"].get("avg_ms", 0)
        if avg_time > 5000:
            recommendations.append({
                "area": "performance",
                "priority": "medium",
                "issue": f"Average execution time is {avg_time}ms - consider optimization",
                "recommendation": "Identify slow tools and optimize or add caching"
            })

        # Error pattern recommendations
        error_analysis = execution_stats["error_analysis"]
        if error_analysis.get("total_errors", 0) > 10:
            top_error = list(error_analysis.get("error_types", {}).keys())[:1]
            if top_error:
                recommendations.append({
                    "area": "errors",
                    "priority": "high",
                    "issue": f"Most common error type: {top_error[0]}",
                    "recommendation": "Focus debugging on this error pattern"
                })

        report["recommendations"] = recommendations if recommendations else [{"area": "general", "priority": "low", "message": "System performing well, no urgent recommendations"}]

    return report


def main():
    parser = argparse.ArgumentParser(description="OrchestrateOS System Analyzer")
    parser.add_argument("action", choices=list(ACTIONS.keys()), help="Action to perform")
    parser.add_argument("--params", type=str, default="{}", help="JSON params")
    args = parser.parse_args()

    try:
        params = json.loads(args.params) if args.params else {}
    except json.JSONDecodeError:
        print(json.dumps({"status": "error", "message": "Invalid JSON params"}))
        return

    action_map = {
        "get_execution_stats": get_execution_stats,
        "get_token_metrics": get_token_metrics,
        "get_system_report": get_system_report,
        "get_task_history": get_task_history
    }

    action_func = action_map.get(args.action)
    if action_func:
        result = action_func(**params)
        print(json.dumps(result, indent=2, default=str))
    else:
        print(json.dumps({"status": "error", "message": f"Unknown action: {args.action}"}))


if __name__ == "__main__":
    main()
