#!/usr/bin/env python3
"""
Token Telemetry System
Captures token usage from Claude Code execution logs to optimize budget allocation
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional

TELEMETRY_FILE = "data/token_telemetry.json"
WEEKLY_LIMIT = 200000  # Claude Code weekly token limit


class TokenTelemetry:
    """Track token usage across tasks and sessions"""

    def __init__(self):
        self.data = self._load_data()

    def _load_data(self) -> Dict:
        """Load existing telemetry data"""
        if os.path.exists(TELEMETRY_FILE):
            with open(TELEMETRY_FILE, 'r') as f:
                return json.load(f)
        return {
            "sessions": [],
            "task_patterns": {},
            "weekly_resets": []
        }

    def _save_data(self):
        """Save telemetry data"""
        os.makedirs(os.path.dirname(TELEMETRY_FILE), exist_ok=True)
        with open(TELEMETRY_FILE, 'w') as f:
            json.dump(self.data, f, indent=2)

    def log_token_usage(
        self,
        task_id: str,
        task_type: str,
        tokens_start: int,
        tokens_end: int,
        tools_used: List[str],
        duration_seconds: int,
        success: bool,
        execution_mode: str = "autonomous",
        batch_size: int = 1
    ):
        """Log token usage for a task execution"""
        tokens_used = tokens_start - tokens_end

        session_entry = {
            "timestamp": datetime.now().isoformat(),
            "task_id": task_id,
            "task_type": task_type,
            "tokens_start": tokens_start,
            "tokens_end": tokens_end,
            "tokens_used": tokens_used,
            "tools_used": tools_used,
            "duration_seconds": duration_seconds,
            "success": success,
            "execution_mode": execution_mode,
            "batch_size": batch_size,
            "tokens_per_second": tokens_used / duration_seconds if duration_seconds > 0 else 0
        }

        self.data["sessions"].append(session_entry)

        # Update pattern tracking
        if task_type not in self.data["task_patterns"]:
            self.data["task_patterns"][task_type] = {
                "total_executions": 0,
                "total_tokens": 0,
                "avg_tokens": 0,
                "min_tokens": float('inf'),
                "max_tokens": 0,
                "success_rate": 0.0
            }

        pattern = self.data["task_patterns"][task_type]
        pattern["total_executions"] += 1
        pattern["total_tokens"] += tokens_used
        pattern["avg_tokens"] = pattern["total_tokens"] / pattern["total_executions"]
        pattern["min_tokens"] = min(pattern["min_tokens"], tokens_used)
        pattern["max_tokens"] = max(pattern["max_tokens"], tokens_used)

        # Update success rate
        success_count = sum(
            1 for s in self.data["sessions"]
            if s["task_type"] == task_type and s["success"]
        )
        pattern["success_rate"] = success_count / pattern["total_executions"]

        self._save_data()

    def predict_token_cost(self, task_type: str, complexity: str = "medium") -> int:
        """Predict token cost for a task based on historical patterns"""
        if task_type not in self.data["task_patterns"]:
            # Default estimates if no data
            defaults = {
                "file_edit": 800,
                "file_read": 1500,
                "doc_creation": 1200,
                "code_generation": 3000,
                "autonomous_execution": 12000,
                "research": 5000
            }
            base = defaults.get(task_type, 2000)
        else:
            base = self.data["task_patterns"][task_type]["avg_tokens"]

        # Adjust for complexity
        multipliers = {
            "simple": 0.5,
            "medium": 1.0,
            "complex": 1.8
        }

        return int(base * multipliers.get(complexity, 1.0))

    def get_weekly_usage(self) -> Dict:
        """Calculate current weekly token usage"""
        # Find most recent Monday (weekly reset day)
        now = datetime.now()
        days_since_monday = now.weekday()  # Monday = 0
        week_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Get sessions from this week
        week_sessions = [
            s for s in self.data["sessions"]
            if datetime.fromisoformat(s["timestamp"]) >= week_start
        ]

        total_used = sum(s["tokens_used"] for s in week_sessions)
        remaining = WEEKLY_LIMIT - total_used

        return {
            "week_start": week_start.isoformat(),
            "total_used": total_used,
            "total_available": WEEKLY_LIMIT,
            "remaining": remaining,
            "percent_used": (total_used / WEEKLY_LIMIT) * 100,
            "sessions_this_week": len(week_sessions)
        }

    def can_afford_task(self, task_type: str, complexity: str = "medium") -> Dict:
        """Check if task can be executed within remaining budget"""
        weekly = self.get_weekly_usage()
        estimated_cost = self.predict_token_cost(task_type, complexity)

        can_afford = estimated_cost <= weekly["remaining"]
        percent_of_remaining = (estimated_cost / weekly["remaining"] * 100) if weekly["remaining"] > 0 else 0

        return {
            "can_afford": can_afford,
            "estimated_cost": estimated_cost,
            "remaining_budget": weekly["remaining"],
            "percent_of_remaining": percent_of_remaining,
            "recommendation": self._get_recommendation(estimated_cost, weekly)
        }

    def _get_recommendation(self, estimated_cost: int, weekly: Dict) -> str:
        """Get budget recommendation"""
        remaining = weekly["remaining"]
        percent_used = weekly["percent_used"]

        if estimated_cost > remaining:
            return "DEFER - Task exceeds remaining weekly budget"
        elif percent_used > 90:
            return "CAUTION - Less than 10% budget remaining"
        elif estimated_cost > remaining * 0.5:
            return "WARNING - Task will use 50%+ of remaining budget"
        elif percent_used > 75:
            return "MONITOR - Over 75% budget used this week"
        else:
            return "OK - Sufficient budget available"

    def get_optimization_insights(self) -> Dict:
        """Generate insights for token optimization"""
        if not self.data["sessions"]:
            return {"message": "No data yet - run some tasks first"}

        # Analyze token efficiency
        sessions = self.data["sessions"]

        # Most expensive task types
        expensive_tasks = sorted(
            self.data["task_patterns"].items(),
            key=lambda x: x[1]["avg_tokens"],
            reverse=True
        )[:5]

        # Tools that burn most tokens
        tool_costs = {}
        for s in sessions:
            for tool in s["tools_used"]:
                if tool not in tool_costs:
                    tool_costs[tool] = {"total": 0, "count": 0}
                tool_costs[tool]["total"] += s["tokens_used"]
                tool_costs[tool]["count"] += 1

        for tool in tool_costs:
            tool_costs[tool]["avg"] = tool_costs[tool]["total"] / tool_costs[tool]["count"]

        expensive_tools = sorted(
            tool_costs.items(),
            key=lambda x: x[1]["avg"],
            reverse=True
        )[:5]

        # Breakdown by execution mode
        mode_breakdown = {}
        for s in sessions:
            mode = s.get("execution_mode", "unknown")
            if mode not in mode_breakdown:
                mode_breakdown[mode] = {"total_tokens": 0, "count": 0}
            mode_breakdown[mode]["total_tokens"] += s["tokens_used"]
            mode_breakdown[mode]["count"] += 1

        for mode in mode_breakdown:
            mode_breakdown[mode]["avg_tokens"] = mode_breakdown[mode]["total_tokens"] / mode_breakdown[mode]["count"]

        # Breakdown by batch size
        batch_breakdown = {}
        for s in sessions:
            batch_size = s.get("batch_size", 1)
            if batch_size not in batch_breakdown:
                batch_breakdown[batch_size] = {"total_tokens": 0, "count": 0}
            batch_breakdown[batch_size]["total_tokens"] += s["tokens_used"]
            batch_breakdown[batch_size]["count"] += 1

        for batch_size in batch_breakdown:
            batch_breakdown[batch_size]["avg_tokens"] = batch_breakdown[batch_size]["total_tokens"] / batch_breakdown[batch_size]["count"]

        return {
            "most_expensive_tasks": [
                {
                    "type": t[0],
                    "avg_tokens": t[1]["avg_tokens"],
                    "executions": t[1]["total_executions"]
                }
                for t in expensive_tasks
            ],
            "most_expensive_tools": [
                {
                    "tool": t[0],
                    "avg_tokens": t[1]["avg"],
                    "uses": t[1]["count"]
                }
                for t in expensive_tools
            ],
            "execution_mode_breakdown": mode_breakdown,
            "batch_size_breakdown": batch_breakdown,
            "total_sessions": len(sessions),
            "total_tokens_tracked": sum(s["tokens_used"] for s in sessions)
        }


def extract_token_usage_from_log(log_content: str) -> Optional[Dict]:
    """Extract token usage from execution log content"""
    import re

    # Look for token usage pattern: "Token usage: 99792/200000; 100208 remaining"
    pattern = r"Token usage: (\d+)/(\d+); (\d+) remaining"
    matches = re.findall(pattern, log_content)

    if matches:
        # Get first and last occurrence
        first = matches[0]
        last = matches[-1]

        return {
            "tokens_start": int(first[2]),  # remaining at start
            "tokens_end": int(last[2]),     # remaining at end
            "tokens_used": int(first[2]) - int(last[2]),
            "total_limit": int(first[1])
        }

    return None


def get_usage_summary():
    """Get summary of token usage with execution mode and batch size breakdown"""
    telemetry = TokenTelemetry()

    if not telemetry.data["sessions"]:
        return {
            "message": "No token usage data captured yet",
            "total_sessions": 0,
            "total_tokens_used": 0
        }

    sessions = telemetry.data["sessions"]

    # Overall stats
    total_tokens = sum(s["tokens_used"] for s in sessions)
    avg_duration = sum(s["duration_seconds"] for s in sessions) / len(sessions)

    # Execution mode breakdown
    mode_stats = {}
    for s in sessions:
        mode = s.get("execution_mode", "unknown")
        if mode not in mode_stats:
            mode_stats[mode] = {
                "count": 0,
                "total_tokens": 0,
                "avg_tokens": 0
            }
        mode_stats[mode]["count"] += 1
        mode_stats[mode]["total_tokens"] += s["tokens_used"]

    for mode in mode_stats:
        mode_stats[mode]["avg_tokens"] = mode_stats[mode]["total_tokens"] / mode_stats[mode]["count"]

    # Batch size breakdown
    batch_stats = {}
    for s in sessions:
        batch_size = s.get("batch_size", 1)
        if batch_size not in batch_stats:
            batch_stats[batch_size] = {
                "count": 0,
                "total_tokens": 0,
                "avg_tokens": 0
            }
        batch_stats[batch_size]["count"] += 1
        batch_stats[batch_size]["total_tokens"] += s["tokens_used"]

    for batch_size in batch_stats:
        batch_stats[batch_size]["avg_tokens"] = batch_stats[batch_size]["total_tokens"] / batch_stats[batch_size]["count"]

    # Weekly usage
    weekly = telemetry.get_weekly_usage()

    return {
        "total_sessions": len(sessions),
        "total_tokens_used": total_tokens,
        "avg_tokens_per_session": total_tokens / len(sessions),
        "avg_duration_seconds": avg_duration,
        "execution_mode_breakdown": mode_stats,
        "batch_size_breakdown": batch_stats,
        "weekly_usage": weekly,
        "recent_sessions": sessions[-5:]  # Last 5 sessions
    }


if __name__ == "__main__":
    # CLI interface
    import sys

    telemetry = TokenTelemetry()

    if len(sys.argv) < 2:
        print("Token Telemetry CLI")
        print("Usage:")
        print("  python3 token_telemetry.py usage       - Show weekly usage")
        print("  python3 token_telemetry.py summary     - Show usage summary with mode/batch breakdown")
        print("  python3 token_telemetry.py predict <task_type> - Predict cost")
        print("  python3 token_telemetry.py insights    - Get optimization insights")
        print("  python3 token_telemetry.py check <task_type> - Check if affordable")
        sys.exit(1)

    command = sys.argv[1]

    if command == "usage":
        usage = telemetry.get_weekly_usage()
        print(json.dumps(usage, indent=2))

    elif command == "summary":
        summary = get_usage_summary()
        print(json.dumps(summary, indent=2))

    elif command == "predict":
        if len(sys.argv) < 3:
            print("Usage: python3 token_telemetry.py predict <task_type> [complexity]")
            sys.exit(1)
        task_type = sys.argv[2]
        complexity = sys.argv[3] if len(sys.argv) > 3 else "medium"
        cost = telemetry.predict_token_cost(task_type, complexity)
        print(f"Estimated cost: {cost} tokens")

    elif command == "check":
        if len(sys.argv) < 3:
            print("Usage: python3 token_telemetry.py check <task_type> [complexity]")
            sys.exit(1)
        task_type = sys.argv[2]
        complexity = sys.argv[3] if len(sys.argv) > 3 else "medium"
        result = telemetry.can_afford_task(task_type, complexity)
        print(json.dumps(result, indent=2))

    elif command == "insights":
        insights = telemetry.get_optimization_insights()
        print(json.dumps(insights, indent=2))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
