#!/usr/bin/env python3
"""
Brave Search API Tool
Enables Claude Code to perform web searches and retrieve live content.
API Docs: https://api.search.brave.com/app/documentation/web-search/get-started
"""

import requests
import argparse
import json
import sys
import os
from datetime import datetime

# Configuration
API_KEY = "BSATsQ3ZqkTjYxxDpfW0zsF4E4riRPM"
BASE_URL = "https://api.search.brave.com/res/v1/web/search"
TIMEOUT = 10

def search(query, count=10, freshness=None, safe_search="moderate"):
    """
    Execute a search query and return results.

    Args:
        query: Search query string
        count: Number of results (default: 10, max: 20)
        freshness: Time filter ("day", "week", "month", "year")
        safe_search: Filter inappropriate content (default: "moderate")

    Returns:
        dict with status, query, results, result_count
    """
    try:
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": API_KEY
        }

        params = {
            "q": query,
            "count": min(count, 20)  # Cap at 20
        }

        if freshness:
            params["freshness"] = freshness

        if safe_search:
            params["safesearch"] = safe_search

        response = requests.get(BASE_URL, headers=headers, params=params, timeout=TIMEOUT)
        response.raise_for_status()

        data = response.json()

        # Extract web results
        results = []
        if "web" in data and "results" in data["web"]:
            for item in data["web"]["results"]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "description": item.get("description", ""),
                    "age": item.get("age", "")
                })

        return {
            "status": "success",
            "query": query,
            "results": results,
            "result_count": len(results)
        }

    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": f"Request timed out after {TIMEOUT} seconds",
            "query": query
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "message": f"API request failed: {str(e)}",
            "query": query
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
            "query": query
        }


def fetch_url(url, format="text"):
    """
    Retrieve content from a specific URL.

    Args:
        url: URL to fetch
        format: "html" | "text" | "markdown" (default: "text")

    Returns:
        dict with status, url, content, format, content_length
    """
    try:
        headers = {
            "User-Agent": "OrchestrateOS/1.0 (Brave Search Integration)"
        }

        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()

        content = response.text

        # Basic content cleaning for text format
        if format == "text":
            # Remove script and style tags
            import re
            content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
            content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)
            content = re.sub(r'<[^>]+>', ' ', content)  # Remove HTML tags
            content = re.sub(r'\s+', ' ', content)  # Normalize whitespace
            content = content.strip()

        return {
            "status": "success",
            "url": url,
            "content": content,
            "format": format,
            "content_length": len(content)
        }

    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": f"Request timed out after {TIMEOUT} seconds",
            "url": url
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "message": f"Failed to fetch URL: {str(e)}",
            "url": url
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
            "url": url
        }


def search_and_fetch(query, url_filter=None, selection_criteria="top_result"):
    """
    Search for a query and automatically fetch content from the top result.

    Args:
        query: Search query string
        url_filter: Only return results matching this domain pattern
        selection_criteria: "top_result" | "official_docs" | "recent"

    Returns:
        dict with status, selected_url, content, title, extracted_at
    """
    # First, perform the search
    search_result = search(query, count=10)

    if search_result["status"] != "success" or not search_result["results"]:
        return {
            "status": "error",
            "message": "No search results found",
            "query": query
        }

    results = search_result["results"]

    # Filter by domain if specified
    if url_filter:
        results = [r for r in results if url_filter in r["url"]]
        if not results:
            return {
                "status": "error",
                "message": f"No results found matching domain filter: {url_filter}",
                "query": query
            }

    # Select result based on criteria
    if selection_criteria == "top_result":
        selected = results[0]
    elif selection_criteria == "official_docs":
        # Prefer results with "docs", "documentation", "api" in URL
        docs_results = [r for r in results if any(term in r["url"].lower() for term in ["docs", "documentation", "api"])]
        selected = docs_results[0] if docs_results else results[0]
    elif selection_criteria == "recent":
        # Prefer results with recent age
        recent_results = [r for r in results if r.get("age")]
        selected = recent_results[0] if recent_results else results[0]
    else:
        selected = results[0]

    # Fetch the content
    fetch_result = fetch_url(selected["url"], format="text")

    if fetch_result["status"] != "success":
        return {
            "status": "error",
            "message": f"Failed to fetch content: {fetch_result.get('message')}",
            "selected_url": selected["url"]
        }

    return {
        "status": "success",
        "selected_url": selected["url"],
        "content": fetch_result["content"][:10000],  # Limit to first 10k chars
        "title": selected["title"],
        "extracted_at": datetime.utcnow().isoformat() + "Z"
    }


def generate_daily_briefing():
    """
    Generate a daily industry briefing using config-driven query strategy.

    Returns:
        dict with status, results, categorized_results, output_path
    """
    try:
        # Load config
        config_path = os.path.join(os.path.dirname(__file__), "..", "data", "brave_query_params.json")
        with open(config_path, 'r') as f:
            config = json.load(f)

        query_strategy = config["query_strategy"]
        category_map = config["category_map"]
        output_format = config["output_format"]
        relevance_keywords = config.get("relevance_filters", {}).get("keywords", [])

        # Execute search with config parameters
        search_result = search(
            query=query_strategy["base_query"],
            count=query_strategy["parameters"]["count"],
            freshness=query_strategy["parameters"]["freshness"],
            safe_search="moderate"
        )

        if search_result["status"] != "success":
            return search_result

        # Score and filter results
        scored_results = []
        for result in search_result["results"]:
            score = 0
            text = f"{result['title']} {result['description']}".lower()

            # Score based on relevance keywords
            for keyword in relevance_keywords:
                if keyword.lower() in text:
                    score += 1

            # Categorize
            categories = []
            for category, keywords in category_map.items():
                if any(kw.lower() in text for kw in keywords):
                    categories.append(category)

            if score > 0:  # Only include if has some relevance
                scored_results.append({
                    "title": result["title"],
                    "url": result["url"],
                    "description": result["description"],
                    "score": score,
                    "categories": categories or ["general"]
                })

        # Sort by score and take top N
        scored_results.sort(key=lambda x: x["score"], reverse=True)
        top_results = scored_results[:output_format["max_results"]]

        # Categorize top results
        categorized = {
            "competitive": [],
            "technical": [],
            "market": [],
            "cultural": [],
            "general": []
        }

        for result in top_results:
            for category in result["categories"]:
                if category in categorized:
                    categorized[category].append(result)

        # Write to output file
        output_path = os.path.join(os.path.dirname(__file__), "..", output_format["destination"])
        output_data = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "query": query_strategy["base_query"],
            "total_results": len(search_result["results"]),
            "top_results_count": len(top_results),
            "results": top_results,
            "categorized": categorized
        }

        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)

        return {
            "status": "success",
            "results_count": len(top_results),
            "categorized_counts": {k: len(v) for k, v in categorized.items() if v},
            "output_path": output_path,
            "preview": top_results[:3]
        }

    except FileNotFoundError:
        return {
            "status": "error",
            "message": "Config file not found: data/brave_query_params.json"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to generate briefing: {str(e)}"
        }


def main():
    parser = argparse.ArgumentParser(description="Brave Search API Tool")
    parser.add_argument("--action", required=True, choices=["search", "fetch_url", "search_and_fetch", "generate_daily_briefing"],
                      help="Action to perform")
    parser.add_argument("--params", required=True, help="JSON parameters for the action")

    args = parser.parse_args()

    try:
        params = json.loads(args.params)
    except json.JSONDecodeError as e:
        print(json.dumps({
            "status": "error",
            "message": f"Invalid JSON parameters: {str(e)}"
        }))
        sys.exit(1)

    # Execute the action
    if args.action == "search":
        result = search(
            query=params.get("query"),
            count=params.get("count", 10),
            freshness=params.get("freshness"),
            safe_search=params.get("safe_search", "moderate")
        )
    elif args.action == "fetch_url":
        result = fetch_url(
            url=params.get("url"),
            format=params.get("format", "text")
        )
    elif args.action == "search_and_fetch":
        result = search_and_fetch(
            query=params.get("query"),
            url_filter=params.get("url_filter"),
            selection_criteria=params.get("selection_criteria", "top_result")
        )
    elif args.action == "generate_daily_briefing":
        result = generate_daily_briefing()
    else:
        result = {
            "status": "error",
            "message": f"Unknown action: {args.action}"
        }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
