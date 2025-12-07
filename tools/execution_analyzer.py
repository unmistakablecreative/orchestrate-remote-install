import json
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import statistics

EXEC_LOG = "data/execution_log.json"


def _load_executions():
    """Load execution log with error handling (private helper)"""
    try:
        with open(EXEC_LOG, "r", encoding="utf-8") as f:
            raw = json.load(f)
            data = raw.get("executions", [])
            if not isinstance(data, list):
                raise ValueError("Malformed execution log: 'executions' is not a list")
            return data
    except Exception:
        return []


def _get_status_breakdown(data):
    """Get comprehensive status breakdown with all new status types (private helper)"""
    status_counts = Counter()
    for e in data:
        if isinstance(e, dict):
            status = e.get("status", "unknown")
            status_counts[status] += 1
    return dict(status_counts)


def _calculate_success_metrics(data):
    """Calculate various success metrics (private helper)"""
    if not data:
        return {"total": 0, "success_rate": 0, "reconstruction_rate": 0, "failure_rate": 0}

    total = len(data)
    successes = len([e for e in data if e.get("status") in ["success", "reconstruction_success"]])
    reconstructions = len([e for e in data if e.get("status") == "reconstruction_success"])

    return {
        "total_executions": total,
        "success_rate": round((successes / total) * 100, 2),
        "reconstruction_rate": round((reconstructions / total) * 100, 2),
        "clean_success_rate": round(((successes - reconstructions) / total) * 100, 2),
        "failure_rate": round(((total - successes) / total) * 100, 2)
    }


def _analyze_reconstruction_patterns(data):
    """Analyze auto-reconstruction success/failure patterns (private helper)"""
    reconstruction_data = [e for e in data if e.get("reconstruction")]

    if not reconstruction_data:
        return {"total_attempts": 0, "patterns": []}

    patterns = Counter()
    common_fixes = Counter()
    common_failures = Counter()

    for e in reconstruction_data:
        recon = e.get("reconstruction", {})
        corrections = recon.get("corrections_applied", [])
        still_missing = recon.get("still_missing", [])

        if corrections:
            for correction in corrections:
                common_fixes[correction] += 1

        if still_missing:
            for missing in still_missing:
                common_failures[missing] += 1

        # Pattern analysis
        if e.get("status") == "reconstruction_success":
            patterns["successful_reconstruction"] += 1
        elif e.get("status") == "reconstruction_failed":
            patterns["failed_reconstruction"] += 1

    return {
        "total_attempts": len(reconstruction_data),
        "success_patterns": dict(patterns),
        "common_fixes": dict(common_fixes.most_common(10)),
        "common_missing_params": dict(common_failures.most_common(10))
    }


def _analyze_schema_errors(data):
    """Deep dive into schema validation failures (private helper)"""
    schema_errors = [e for e in data if e.get("status") == "reconstruction_failed" and e.get("schema_errors")]

    if not schema_errors:
        return {"total_schema_errors": 0}

    missing_params = Counter()
    tool_param_issues = defaultdict(lambda: Counter())

    for e in schema_errors:
        schema = e.get("schema_errors", {})
        tool = e.get("tool", "unknown")
        action = e.get("action", "unknown")

        for param in schema.get("missing_params", []):
            missing_params[param] += 1
            tool_param_issues[f"{tool}.{action}"][param] += 1

    return {
        "total_schema_errors": len(schema_errors),
        "most_common_missing_params": dict(missing_params.most_common(15)),
        "problematic_tool_actions": {
            combo: dict(params.most_common(5))
            for combo, params in tool_param_issues.items()
            if sum(params.values()) >= 2
        }
    }


def _analyze_performance_metrics(data):
    """Analyze execution performance and timing (private helper)"""
    performance_data = []
    timeout_data = []

    for e in data:
        if not isinstance(e, dict):
            continue

        exec_details = e.get("execution_details", {})
        exec_time = exec_details.get("execution_time_ms")

        if exec_time is not None:
            performance_data.append({
                "tool": e.get("tool"),
                "action": e.get("action"),
                "time_ms": exec_time,
                "status": e.get("status")
            })

        if exec_details.get("timeout"):
            timeout_data.append({
                "tool": e.get("tool"),
                "action": e.get("action"),
                "timeout_seconds": exec_details.get("timeout_seconds", 200)
            })

    if not performance_data:
        return {"no_performance_data": True}

    times = [p["time_ms"] for p in performance_data]

    # Tool performance ranking
    tool_times = defaultdict(list)
    for p in performance_data:
        if p["tool"]:
            tool_times[p["tool"]].append(p["time_ms"])

    tool_avg_times = {
        tool: round(statistics.mean(times), 2)
        for tool, times in tool_times.items()
        if len(times) >= 3
    }

    return {
        "total_timed_executions": len(performance_data),
        "avg_execution_time_ms": round(statistics.mean(times), 2),
        "median_execution_time_ms": round(statistics.median(times), 2),
        "slowest_execution_ms": max(times),
        "fastest_execution_ms": min(times),
        "timeout_count": len(timeout_data),
        "tool_avg_performance": dict(sorted(tool_avg_times.items(), key=lambda x: x[1], reverse=True)),
        "slowest_calls": sorted(performance_data, key=lambda x: x["time_ms"], reverse=True)[:10]
    }


def _analyze_error_patterns(data):
    """Comprehensive error pattern analysis (private helper)"""
    error_data = [e for e in data if e.get("status") not in ["success", "reconstruction_success"]]

    if not error_data:
        return {"no_errors": True}

    # Error type breakdown
    error_types = Counter(e.get("status") for e in error_data)
    violation_types = Counter(e.get("violation_type") for e in error_data if e.get("violation_type"))

    # Tool-specific error patterns
    tool_errors = defaultdict(lambda: Counter())
    action_errors = defaultdict(lambda: Counter())

    for e in error_data:
        tool = e.get("tool", "unknown")
        action = e.get("action", "unknown")
        status = e.get("status", "unknown")

        tool_errors[tool][status] += 1
        action_errors[action][status] += 1

    # Validation errors
    validation_errors = [e for e in error_data if e.get("validation_errors")]
    json_parse_errors = [e for e in error_data if e.get("status") == "json_parse_error"]

    return {
        "total_errors": len(error_data),
        "error_types": dict(error_types.most_common()),
        "violation_types": dict(violation_types.most_common()),
        "validation_errors": len(validation_errors),
        "json_parse_errors": len(json_parse_errors),
        "tools_with_most_errors": dict(Counter({
            tool: sum(errors.values())
            for tool, errors in tool_errors.items()
        }).most_common(10)),
        "actions_with_most_errors": dict(Counter({
            action: sum(errors.values())
            for action, errors in action_errors.items()
        }).most_common(10)),
        "tool_error_breakdown": {
            tool: dict(errors) for tool, errors in tool_errors.items()
            if sum(errors.values()) >= 3
        }
    }


def _analyze_thread_health(data):
    """Analyze thread scoring and penalty patterns (private helper)"""
    penalties = [e.get("penalty", 0) for e in data if e.get("penalty", 0) != 0]
    score_changes = []

    for e in data:
        before = e.get("thread_score_before", 100)
        after = e.get("thread_score_after", 100)
        if before is not None and after is not None:
            score_changes.append(after - before)

    penalty_by_violation = defaultdict(list)
    for e in data:
        if e.get("penalty", 0) > 0:
            violation = e.get("violation_type", "unknown")
            penalty_by_violation[violation].append(e.get("penalty"))

    return {
        "total_penalties_applied": len(penalties),
        "total_penalty_points": sum(penalties),
        "avg_penalty": round(statistics.mean(penalties), 2) if penalties else 0,
        "max_penalty": max(penalties) if penalties else 0,
        "penalty_by_violation": {
            violation: {
                "count": len(penalties),
                "avg_penalty": round(statistics.mean(penalties), 2),
                "total_penalty": sum(penalties)
            }
            for violation, penalties in penalty_by_violation.items()
        },
        "avg_score_change": round(statistics.mean(score_changes), 2) if score_changes else 0
    }


def _generate_reconstruction_recommendations(failures, successes):
    """Generate actionable recommendations for improving reconstruction (private helper)"""
    recommendations = []

    # Analyze failure patterns
    common_failures = Counter(failures).most_common(5)
    for param, count in common_failures:
        if count >= 3:
            recommendations.append(f"Add default value logic for '{param}' parameter (fails {count} times)")

    # Analyze success patterns
    common_successes = Counter(successes).most_common(5)
    for fix, count in common_successes:
        if "mapped" in fix.lower() and count >= 5:
            recommendations.append(f"Consider making '{fix}' a permanent mapping rule")

    return recommendations


def _deep_dive_tool_analysis(data, tool_name):
    """Deep analysis of a specific tool (private helper)"""
    tool_data = [e for e in data if isinstance(e, dict) and e.get("tool", "").lower() == tool_name.lower()]

    if not tool_data:
        return {"message": "No data found for this tool"}

    # Action breakdown
    action_stats = defaultdict(lambda: {"total": 0, "success": 0, "errors": defaultdict(int)})

    for e in tool_data:
        action = e.get("action", "unknown")
        status = e.get("status", "unknown")

        action_stats[action]["total"] += 1
        if status in ["success", "reconstruction_success"]:
            action_stats[action]["success"] += 1
        else:
            action_stats[action]["errors"][status] += 1

    # Calculate success rates per action
    action_summary = {}
    for action, stats in action_stats.items():
        total = stats["total"]
        success = stats["success"]
        action_summary[action] = {
            "total_calls": total,
            "success_count": success,
            "success_rate": round((success / total) * 100, 2),
            "error_breakdown": dict(stats["errors"])
        }

    # Performance analysis for this tool
    tool_performance = [
        e.get("execution_details", {}).get("execution_time_ms")
        for e in tool_data
        if e.get("execution_details", {}).get("execution_time_ms") is not None
    ]

    performance_stats = {}
    if tool_performance:
        performance_stats = {
            "avg_execution_time_ms": round(statistics.mean(tool_performance), 2),
            "median_execution_time_ms": round(statistics.median(tool_performance), 2),
            "slowest_execution_ms": max(tool_performance),
            "fastest_execution_ms": min(tool_performance)
        }

    return {
        "tool_name": tool_name,
        "total_calls": len(tool_data),
        "action_breakdown": action_summary,
        "performance": performance_stats,
        "overall_success_rate": round(
            (sum(s["success"] for s in action_stats.values()) / len(tool_data)) * 100, 2
        )
    }


def _analyze_route_reliability(data, min_calls):
    """Enhanced route suggestion with reliability scoring (private helper)"""
    route_stats = defaultdict(lambda: {"total": 0, "success": 0, "avg_time": 0, "times": []})

    for e in data:
        if not isinstance(e, dict):
            continue

        tool = e.get("tool")
        action = e.get("action")
        status = e.get("status")

        if not (tool and action):
            continue

        route_key = (tool, action)
        route_stats[route_key]["total"] += 1

        if status in ["success", "reconstruction_success"]:
            route_stats[route_key]["success"] += 1

        exec_time = e.get("execution_details", {}).get("execution_time_ms")
        if exec_time:
            route_stats[route_key]["times"].append(exec_time)

    # Calculate reliability scores and average times
    reliable_routes = []
    for (tool, action), stats in route_stats.items():
        if stats["total"] >= min_calls:
            success_rate = (stats["success"] / stats["total"]) * 100
            avg_time = statistics.mean(stats["times"]) if stats["times"] else 0

            reliable_routes.append({
                "tool": tool,
                "action": action,
                "total_calls": stats["total"],
                "success_rate": round(success_rate, 2),
                "avg_execution_time_ms": round(avg_time, 2),
                "reliability_score": round(success_rate - (avg_time / 1000), 2)  # Higher is better
            })

    # Sort by reliability score
    reliable_routes.sort(key=lambda x: x["reliability_score"], reverse=True)

    return {
        "min_calls_threshold": min_calls,
        "reliable_routes": reliable_routes[:20]
    }


def _analyze_timeline(data):
    """Show error patterns over time (private helper)"""
    # Group by hour and status
    hourly_stats = defaultdict(lambda: defaultdict(int))

    for e in data:
        if not isinstance(e, dict):
            continue
        timestamp_str = e.get("timestamp")
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
                hour_key = timestamp.strftime("%Y-%m-%d %H:00")
                status = e.get("status", "unknown")
                hourly_stats[hour_key][status] += 1
            except:
                continue

    return {
        "total_executions": len(data),
        "hourly_breakdown": {hour: dict(stats) for hour, stats in hourly_stats.items()}
    }


def analyze(params):
    """
    Unified analysis function with aspect parameter.

    Consolidates 7 specialized analyzers into one parameterized function.

    params:
      - aspect: str (required) - What to analyze:
          * "errors" - error patterns
          * "performance" - execution timing
          * "reconstruction" - auto-fix patterns
          * "schema" - schema validation failures
          * "thread" - thread health/penalties
          * "success" - success metrics
          * "status" - status breakdown
          * "all" - comprehensive summary (default)
      - tool: str (optional) - Filter by specific tool
      - hours: int (optional) - Time window for analysis
    """
    aspect = params.get("aspect", "all").lower()
    tool_filter = params.get("tool", "").strip().lower()
    hours_back = params.get("hours")

    # Load data once
    data = _load_executions()

    if not data:
        return {
            "tool_name": "execution_analyzer",
            "action": "analyze",
            "aspect": aspect,
            "message": "No execution data available"
        }

    # Apply time filter if specified
    if hours_back:
        try:
            cutoff = datetime.now() - timedelta(hours=hours_back)
            filtered_data = []
            for e in data:
                if isinstance(e, dict) and e.get("timestamp"):
                    try:
                        timestamp = datetime.fromisoformat(e.get("timestamp"))
                        if timestamp >= cutoff:
                            filtered_data.append(e)
                    except:
                        continue
            data = filtered_data
        except:
            pass

    # Apply tool filter if specified
    if tool_filter:
        data = [e for e in data if isinstance(e, dict) and e.get("tool", "").lower() == tool_filter]

        if not data:
            return {
                "tool_name": "execution_analyzer",
                "action": "analyze",
                "aspect": aspect,
                "tool_filter": tool_filter,
                "message": f"No data found for tool '{tool_filter}'"
            }

    # Dispatch to appropriate analysis based on aspect
    result = {
        "tool_name": "execution_analyzer",
        "action": "analyze",
        "aspect": aspect,
        "timestamp": datetime.now().isoformat(),
        "data_points_analyzed": len(data)
    }

    if tool_filter:
        result["tool_filter"] = tool_filter
    if hours_back:
        result["hours_back"] = hours_back

    if aspect == "errors":
        result["analysis"] = _analyze_error_patterns(data)
    elif aspect == "performance":
        result["analysis"] = _analyze_performance_metrics(data)
    elif aspect == "reconstruction":
        result["analysis"] = _analyze_reconstruction_patterns(data)
    elif aspect == "schema":
        result["analysis"] = _analyze_schema_errors(data)
    elif aspect == "thread":
        result["analysis"] = _analyze_thread_health(data)
    elif aspect == "success":
        result["analysis"] = _calculate_success_metrics(data)
    elif aspect == "status":
        result["analysis"] = _get_status_breakdown(data)
    elif aspect == "tool":
        # Deep dive into specific tool
        tool_name = params.get("tool_name", tool_filter)
        if not tool_name:
            return {
                "tool_name": "execution_analyzer",
                "action": "analyze",
                "error": "Tool name required for aspect='tool'"
            }
        result["analysis"] = _deep_dive_tool_analysis(data, tool_name)
    elif aspect == "routes":
        # Route reliability analysis
        min_calls = params.get("min_calls", 3)
        result["analysis"] = _analyze_route_reliability(data, min_calls)
    elif aspect == "timeline":
        # Temporal error analysis
        result["analysis"] = _analyze_timeline(data)
    elif aspect == "all":
        # Comprehensive summary
        tool_usage = Counter(e.get("tool", "unknown") for e in data if isinstance(e, dict))
        result["overview"] = _calculate_success_metrics(data)
        result["status_breakdown"] = _get_status_breakdown(data)
        result["top_tools"] = dict(tool_usage.most_common(10))
        result["reconstruction_patterns"] = _analyze_reconstruction_patterns(data)
        result["schema_validation"] = _analyze_schema_errors(data)
        result["performance_metrics"] = _analyze_performance_metrics(data)
        result["error_patterns"] = _analyze_error_patterns(data)
        result["thread_health"] = _analyze_thread_health(data)
    else:
        return {
            "tool_name": "execution_analyzer",
            "action": "analyze",
            "error": f"Unknown aspect '{aspect}'. Valid: errors, performance, reconstruction, schema, thread, success, status, tool, routes, timeline, all"
        }

    return result


def deep_dive_tool(params):
    """Deep analysis of a specific tool"""
    tool_name = params.get("tool", "").strip()
    if not tool_name:
        return {"error": "Tool name required"}

    data = _load_executions()
    tool_data = [e for e in data if isinstance(e, dict) and e.get("tool", "").lower() == tool_name.lower()]

    if not tool_data:
        return {
            "tool_name": "execution_analyzer",
            "action": "deep_dive_tool",
            "target_tool": tool_name,
            "message": "No data found for this tool"
        }

    # Action breakdown
    action_stats = defaultdict(lambda: {"total": 0, "success": 0, "errors": defaultdict(int)})

    for e in tool_data:
        action = e.get("action", "unknown")
        status = e.get("status", "unknown")

        action_stats[action]["total"] += 1
        if status in ["success", "reconstruction_success"]:
            action_stats[action]["success"] += 1
        else:
            action_stats[action]["errors"][status] += 1

    # Calculate success rates per action
    action_summary = {}
    for action, stats in action_stats.items():
        total = stats["total"]
        success = stats["success"]
        action_summary[action] = {
            "total_calls": total,
            "success_count": success,
            "success_rate": round((success / total) * 100, 2),
            "error_breakdown": dict(stats["errors"])
        }

    # Performance analysis for this tool
    tool_performance = [
        e.get("execution_details", {}).get("execution_time_ms")
        for e in tool_data
        if e.get("execution_details", {}).get("execution_time_ms") is not None
    ]

    performance_stats = {}
    if tool_performance:
        performance_stats = {
            "avg_execution_time_ms": round(statistics.mean(tool_performance), 2),
            "median_execution_time_ms": round(statistics.median(tool_performance), 2),
            "slowest_execution_ms": max(tool_performance),
            "fastest_execution_ms": min(tool_performance)
        }

    return {
        "tool_name": "execution_analyzer",
        "action": "deep_dive_tool",
        "target_tool": tool_name,
        "total_executions": len(tool_data),
        "action_breakdown": action_summary,
        "performance_stats": performance_stats,
        "recent_errors": [
            {
                "action": e.get("action"),
                "status": e.get("status"),
                "timestamp": e.get("timestamp"),
                "error_details": e.get("output", {}).get("error", "No details")
            }
            for e in tool_data[-10:]
            if e.get("status") not in ["success", "reconstruction_success"]
        ]
    }


def error_timeline(params):
    """Show error patterns over time"""
    data = _load_executions()
    hours_back = params.get("hours", 24)

    try:
        cutoff = datetime.now() - timedelta(hours=hours_back)
        recent_data = []

        for e in data:
            if not isinstance(e, dict):
                continue
            timestamp_str = e.get("timestamp")
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    if timestamp >= cutoff:
                        recent_data.append(e)
                except:
                    continue

        # Group by hour and status
        hourly_stats = defaultdict(lambda: defaultdict(int))

        for e in recent_data:
            timestamp_str = e.get("timestamp")
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    hour_key = timestamp.strftime("%Y-%m-%d %H:00")
                    status = e.get("status", "unknown")
                    hourly_stats[hour_key][status] += 1
                except:
                    continue

        return {
            "tool_name": "execution_analyzer",
            "action": "error_timeline",
            "hours_analyzed": hours_back,
            "total_executions": len(recent_data),
            "hourly_breakdown": {hour: dict(stats) for hour, stats in hourly_stats.items()}
        }

    except Exception as e:
        return {"error": f"Timeline analysis failed: {str(e)}"}


def suggest_routes(params):
    """Enhanced route suggestion with reliability scoring"""
    min_calls = params.get("min_calls", 3)
    data = _load_executions()

    route_stats = defaultdict(lambda: {"total": 0, "success": 0, "avg_time": 0, "times": []})

    for e in data:
        if not isinstance(e, dict):
            continue

        tool = e.get("tool")
        action = e.get("action")
        status = e.get("status")

        if not (tool and action):
            continue

        route_key = (tool, action)
        route_stats[route_key]["total"] += 1

        if status in ["success", "reconstruction_success"]:
            route_stats[route_key]["success"] += 1

        exec_time = e.get("execution_details", {}).get("execution_time_ms")
        if exec_time:
            route_stats[route_key]["times"].append(exec_time)

    # Calculate reliability scores and average times
    reliable_routes = []
    for (tool, action), stats in route_stats.items():
        if stats["total"] >= min_calls:
            success_rate = (stats["success"] / stats["total"]) * 100
            avg_time = statistics.mean(stats["times"]) if stats["times"] else 0

            reliable_routes.append({
                "tool": tool,
                "action": action,
                "total_calls": stats["total"],
                "success_rate": round(success_rate, 2),
                "avg_execution_time_ms": round(avg_time, 2),
                "reliability_score": round(success_rate - (avg_time / 1000), 2)  # Higher is better
            })

    # Sort by reliability score
    reliable_routes.sort(key=lambda x: x["reliability_score"], reverse=True)

    return {
        "tool_name": "execution_analyzer",
        "action": "suggest_routes",
        "min_calls_threshold": min_calls,
        "reliable_routes": reliable_routes[:20]
    }


def main():
    import argparse, json
    parser = argparse.ArgumentParser()
    parser.add_argument('action')
    parser.add_argument('--params')
    args = parser.parse_args()
    params = json.loads(args.params) if args.params else {}

    if args.action == 'analyze':
        result = analyze(params)
    # Backward compatibility wrappers for refactored actions
    elif args.action == 'summary':
        result = analyze({"aspect": "all", **params})
    elif args.action == 'suggest_routes':
        result = analyze({"aspect": "routes", **params})
    elif args.action == 'deep_dive_tool':
        # Map old param name to new
        if "tool" in params:
            params["tool_name"] = params.pop("tool")
        result = analyze({"aspect": "tool", **params})
    elif args.action == 'error_timeline':
        result = analyze({"aspect": "timeline", **params})
    elif args.action == 'reconstruction_diagnostics':
        result = analyze({"aspect": "reconstruction", **params})
    # Backward compatibility wrappers for deprecated actions
    elif args.action == 'analyze_error_patterns':
        result = analyze({"aspect": "errors", **params})
    elif args.action == 'analyze_performance_metrics':
        result = analyze({"aspect": "performance", **params})
    elif args.action == 'analyze_reconstruction_patterns':
        result = analyze({"aspect": "reconstruction", **params})
    elif args.action == 'analyze_schema_errors':
        result = analyze({"aspect": "schema", **params})
    elif args.action == 'analyze_thread_health':
        result = analyze({"aspect": "thread", **params})
    elif args.action == 'calculate_success_metrics':
        result = analyze({"aspect": "success", **params})
    elif args.action == 'get_status_breakdown':
        result = analyze({"aspect": "status", **params})
    # Deprecated action redirects
    elif args.action == 'slow_calls':
        result = {"error": "Deprecated. Use: analyze({'aspect': 'performance'}) or summary()"}
    elif args.action == 'penalized_calls':
        result = {"error": "Deprecated. Use: analyze({'aspect': 'thread'}) or summary()"}
    elif args.action == 'frequent_failures':
        result = {"error": "Deprecated. Use: analyze({'aspect': 'errors'}) or deep_dive_tool()"}
    elif args.action == 'calls_by_tool':
        result = {"error": "Deprecated. Use: summary() for tool usage data"}
    elif args.action == 'failures_by_tool':
        result = {"error": "Deprecated. Use: analyze({'aspect': 'errors'}) or summary()"}
    elif args.action == 'action_failures_for_tool':
        result = {"error": "Deprecated. Use: deep_dive_tool({'tool': 'tool_name'})"}
    elif args.action == 'all_statuses_for_tool':
        result = {"error": "Deprecated. Use: deep_dive_tool({'tool': 'tool_name'})"}
    elif args.action == 'action_status_summary':
        result = {"error": "Deprecated. Use: deep_dive_tool({'tool': 'tool_name'})"}
    elif args.action == 'log_trace_summary':
        result = {"error": "Deprecated. Use: summary() or error_timeline()"}
    else:
        result = {'status': 'error', 'message': f'Unknown action {args.action}'}

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
