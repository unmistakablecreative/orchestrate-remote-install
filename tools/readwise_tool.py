import requests
import json
import os
import argparse

# Constants
BASE_URL = "https://readwise.io/api/v2"
CACHE_FILE = "readwise_books.json"

def get_supported_actions():
    return {
        "fetch_books": ["page_size"],
        "fetch_highlights": ["book_title"]
    }

def fetch_books(api_key, page_size=50):
    """Fetches books from Readwise and caches them locally."""
    headers = {"Authorization": f"Token {api_key}"}
    books = []
    next_url = f"{BASE_URL}/books/"

    while next_url:
        response = requests.get(next_url, headers=headers, params={"category": "books", "page_size": page_size})
        if response.status_code == 200:
            data = response.json()
            books.extend(data.get("results", []))
            next_url = data.get("next")
        else:
            return {"status": "error", "message": f"Failed to fetch books: {response.status_code}", "response": response.json()}

    # Only write to file after successful retrieval
    with open(CACHE_FILE, "w") as f:
        json.dump(books, f, indent=2)

    return {"status": "success", "message": "Books cached successfully."}

def fetch_highlights(api_key, book_title):
    """Fetches highlights for a specific book."""
    headers = {"Authorization": f"Token {api_key}"}

    # Auto-fetch books if cache is missing
    if not os.path.exists(CACHE_FILE):
        fetch_books(api_key)

    with open(CACHE_FILE, "r") as f:
        books = json.load(f)

    book_id = next((b["id"] for b in books if b["title"].lower() == book_title.lower()), None)
    if not book_id:
        return {"status": "error", "message": f"Book '{book_title}' not found in cache."}

    url = f"{BASE_URL}/highlights/"
    response = requests.get(url, headers=headers, params={"book_id": book_id})

    if response.status_code == 200:
        return {"status": "success", "highlights": response.json().get("results", [])}
    else:
        return {"status": "error", "message": f"Failed to fetch highlights: {response.status_code}", "response": response.json()}

def main():
    import argparse
    import json
    import os

    parser = argparse.ArgumentParser()
    parser.add_argument("action")
    parser.add_argument("--params", type=str)
    args = parser.parse_args()

    params = json.loads(args.params) if args.params else {}

    # Load API key from credentials.json
    credentials_path = os.path.join(os.path.dirname(__file__), "credentials.json")
    try:
        with open(credentials_path, "r") as f:
            credentials = json.load(f)
        api_key = credentials.get("readwise_api_key")
    except FileNotFoundError:
        api_key = None

    if not api_key:
        result = {"status": "error", "message": "Missing readwise_api_key in credentials.json"}

    elif args.action == "fetch_books":
        result = fetch_books(api_key, params.get("page_size", 50))

    elif args.action == "fetch_highlights":
        if "book_title" not in params:
            result = {"status": "error", "message": "❌ 'book_title' is required for fetch_highlights."}
        else:
            result = fetch_highlights(api_key, params["book_title"])

    elif args.action == "get_supported_actions":
        result = {"status": "success", "actions": get_supported_actions()}

    else:
        result = {"status": "error", "message": f"Unknown action: {args.action}"}

    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
