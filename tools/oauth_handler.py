#!/usr/bin/env python3
"""
OAuth Handler for YouTube Data API v3 and Google Drive API

CLI-only tool that manages OAuth2 authentication flow and token refresh.
Eliminates need for manual Google Dev Console interaction.

Configuration loaded from: data/oauth_config.json
Behavior in data, logic in code.

Usage:
    # Initial authentication
    python3 tools/oauth_handler.py auth --scopes youtube drive

    # Refresh tokens
    python3 tools/oauth_handler.py refresh

    # Get valid access token for use
    python3 tools/oauth_handler.py get_token --scope youtube

    # Check token status
    python3 tools/oauth_handler.py status

Configuration:
    - Client credentials: /data/google_oauth.json
    - Stored tokens: /data/oauth_credentials.json
    - OAuth config: /data/oauth_config.json

Scopes:
    - youtube: YouTube Data API v3 (full access)
    - drive: Google Drive API (full access)
"""

import json
import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import webbrowser
from urllib.parse import urlencode, parse_qs, urlparse
import http.server
import socketserver
from threading import Thread
import requests

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
OAUTH_CONFIG_PATH = PROJECT_ROOT / "data" / "google_oauth.json"
TOKEN_STORAGE_PATH = PROJECT_ROOT / "data" / "oauth_credentials.json"
OAUTH_SETTINGS_PATH = PROJECT_ROOT / "data" / "oauth_config.json"


class OAuthHandler:
    """Handles OAuth2 authentication and token management"""

    def __init__(self):
        self.client_id = None
        self.client_secret = None
        self.tokens = {}
        self.oauth_settings = {}
        self._load_oauth_settings()
        self._load_config()
        self._load_tokens()

    def _load_oauth_settings(self):
        """Load OAuth endpoints and scope mappings from config file"""
        if not OAUTH_SETTINGS_PATH.exists():
            print(f"❌ OAuth settings file not found: {OAUTH_SETTINGS_PATH}")
            sys.exit(1)

        with open(OAUTH_SETTINGS_PATH) as f:
            config = json.load(f)
            self.oauth_settings = config.get('google', {})

        # Set OAuth URLs from config
        self.auth_url = self.oauth_settings.get('auth_url')
        self.token_url = self.oauth_settings.get('token_url')
        self.scope_map = self.oauth_settings.get('scopes', {})
        redirect_config = self.oauth_settings.get('redirect_server', {})
        self.redirect_port = redirect_config.get('port', 8080)
        self.redirect_host = redirect_config.get('host', 'localhost')
        self.redirect_uri = f"http://{self.redirect_host}:{self.redirect_port}"

    def _load_config(self):
        """Load OAuth client configuration"""
        if not OAUTH_CONFIG_PATH.exists():
            print(f"❌ Config file not found: {OAUTH_CONFIG_PATH}")
            sys.exit(1)

        with open(OAUTH_CONFIG_PATH) as f:
            config = json.load(f)
            installed = config.get("installed", {})
            self.client_id = installed.get("client_id")
            self.client_secret = installed.get("client_secret")

        if not self.client_id or not self.client_secret:
            print("❌ Invalid OAuth config: missing client_id or client_secret")
            sys.exit(1)

    def _load_tokens(self):
        """Load stored tokens if they exist"""
        if TOKEN_STORAGE_PATH.exists():
            with open(TOKEN_STORAGE_PATH) as f:
                self.tokens = json.load(f)

    def _save_tokens(self):
        """Save tokens to storage"""
        TOKEN_STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_STORAGE_PATH, 'w') as f:
            json.dump(self.tokens, f, indent=2)
        print(f"✅ Tokens saved to {TOKEN_STORAGE_PATH}")

    def authenticate(self, scope_names):
        """
        Perform OAuth2 authentication flow

        Args:
            scope_names: List of scope names (e.g., ['youtube', 'drive'])
        """
        # Build scope list
        scopes = []
        for name in scope_names:
            if name not in self.scope_map:
                print(f"❌ Unknown scope: {name}")
                print(f"   Valid scopes: {', '.join(self.scope_map.keys())}")
                sys.exit(1)
            scopes.append(self.scope_map[name])

        scope_string = " ".join(scopes)

        # Build authorization URL
        auth_params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": scope_string,
            "response_type": "code",
            "access_type": "offline",  # Request refresh token
            "prompt": "consent"  # Force consent screen for refresh token
        }

        auth_url = f"{self.auth_url}?{urlencode(auth_params)}"

        print("\n🔐 Starting OAuth2 authentication flow...")
        print(f"📋 Scopes: {', '.join(scope_names)}")
        print(f"\n🌐 Opening browser for authorization...")
        print(f"   If browser doesn't open, visit: {auth_url}\n")

        # Start callback server
        auth_code = self._start_callback_server()

        if not auth_code:
            print("❌ Authentication failed: no authorization code received")
            sys.exit(1)

        # Exchange code for tokens
        print("\n🔄 Exchanging authorization code for tokens...")
        token_data = self._exchange_code_for_tokens(auth_code)

        if not token_data:
            print("❌ Failed to exchange code for tokens")
            sys.exit(1)

        # Store tokens with metadata
        for scope_name in scope_names:
            self.tokens[scope_name] = {
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token"),
                "expires_at": (datetime.now() + timedelta(seconds=token_data.get("expires_in", 3600))).isoformat(),
                "scope": self.scope_map[scope_name],
                "token_type": token_data.get("token_type", "Bearer")
            }

        self._save_tokens()
        print("✅ Authentication successful!")
        print(f"✅ Tokens stored for: {', '.join(scope_names)}")

    def _start_callback_server(self):
        """Start local server to receive OAuth callback"""
        auth_code = None

        class CallbackHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                nonlocal auth_code

                # Parse query parameters
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)

                if "code" in params:
                    auth_code = params["code"][0]

                    # Send success response
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"""
                        <html>
                        <body style="font-family: Arial; text-align: center; padding: 50px;">
                            <h1>&#x2705; Authentication Successful!</h1>
                            <p>You can close this window and return to the terminal.</p>
                        </body>
                        </html>
                    """)
                else:
                    # Send error response
                    self.send_response(400)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"""
                        <html>
                        <body style="font-family: Arial; text-align: center; padding: 50px;">
                            <h1>&#x274C; Authentication Failed</h1>
                            <p>No authorization code received.</p>
                        </body>
                        </html>
                    """)

            def log_message(self, format, *args):
                # Suppress server logs
                pass

        # Start server in thread
        server = socketserver.TCPServer(("", self.redirect_port), CallbackHandler)
        server_thread = Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        # Open browser
        webbrowser.open(self._build_auth_url())

        # Wait for callback
        print(f"⏳ Waiting for authorization (listening on port {self.redirect_port})...")
        print("   Complete the authorization in your browser")

        import time
        timeout = 120  # 2 minutes
        start_time = time.time()

        while auth_code is None and (time.time() - start_time) < timeout:
            time.sleep(0.5)

        server.shutdown()

        return auth_code

    def _build_auth_url(self):
        """Build authorization URL (helper for callback server)"""
        # Get all scopes from current tokens or default to all
        all_scopes = list(self.scope_map.values())

        auth_params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(all_scopes),
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent"
        }

        return f"{self.auth_url}?{urlencode(auth_params)}"

    def _exchange_code_for_tokens(self, auth_code):
        """Exchange authorization code for access and refresh tokens"""
        token_params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": auth_code,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code"
        }

        try:
            response = requests.post(self.token_url, data=token_params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ Token exchange failed: {e}")
            return None

    def refresh_tokens(self, scope_name=None):
        """
        Refresh access tokens using refresh token

        Args:
            scope_name: Specific scope to refresh, or None for all
        """
        if not self.tokens:
            print("❌ No tokens found. Run 'auth' first.")
            return False

        scopes_to_refresh = [scope_name] if scope_name else list(self.tokens.keys())
        refreshed = []

        for scope in scopes_to_refresh:
            if scope not in self.tokens:
                print(f"⚠️  No tokens found for scope: {scope}")
                continue

            token_data = self.tokens[scope]
            refresh_token = token_data.get("refresh_token")

            if not refresh_token:
                print(f"❌ No refresh token for scope: {scope}")
                print("   Re-run authentication to get new refresh token")
                continue

            print(f"🔄 Refreshing token for: {scope}")

            refresh_params = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            }

            try:
                response = requests.post(self.token_url, data=refresh_params)
                response.raise_for_status()
                new_token_data = response.json()

                # Update stored tokens
                self.tokens[scope]["access_token"] = new_token_data.get("access_token")
                self.tokens[scope]["expires_at"] = (
                    datetime.now() + timedelta(seconds=new_token_data.get("expires_in", 3600))
                ).isoformat()

                # Update refresh token if new one provided
                if "refresh_token" in new_token_data:
                    self.tokens[scope]["refresh_token"] = new_token_data["refresh_token"]

                refreshed.append(scope)
                print(f"✅ Token refreshed: {scope}")

            except Exception as e:
                print(f"❌ Failed to refresh {scope}: {e}")

        if refreshed:
            self._save_tokens()
            print(f"\n✅ Refreshed tokens: {', '.join(refreshed)}")
            return True

        return False

    def get_valid_token(self, scope_name):
        """
        Get a valid access token for a scope, refreshing if needed

        Args:
            scope_name: Scope name (e.g., 'youtube', 'drive')

        Returns:
            Access token string or None
        """
        if scope_name not in self.tokens:
            print(f"❌ No tokens for scope: {scope_name}")
            print("   Run authentication first")
            return None

        token_data = self.tokens[scope_name]
        expires_at = datetime.fromisoformat(token_data["expires_at"])

        # Check if token needs refresh (refresh 5 minutes before expiry)
        if datetime.now() >= expires_at - timedelta(minutes=5):
            print(f"🔄 Token expired or expiring soon, refreshing...")
            self.refresh_tokens(scope_name)

        return self.tokens[scope_name]["access_token"]

    def check_status(self):
        """Display status of all stored tokens"""
        if not self.tokens:
            print("❌ No tokens stored. Run 'auth' first.")
            return

        print("\n🔐 OAuth Token Status\n")
        print("=" * 60)

        for scope_name, token_data in self.tokens.items():
            expires_at = datetime.fromisoformat(token_data["expires_at"])
            time_remaining = expires_at - datetime.now()

            status = "✅ Valid" if time_remaining.total_seconds() > 0 else "❌ Expired"

            print(f"\n📋 Scope: {scope_name}")
            print(f"   Status: {status}")
            print(f"   Expires: {expires_at.strftime('%Y-%m-%d %H:%M:%S')}")

            if time_remaining.total_seconds() > 0:
                hours = int(time_remaining.total_seconds() / 3600)
                minutes = int((time_remaining.total_seconds() % 3600) / 60)
                print(f"   Time remaining: {hours}h {minutes}m")

            print(f"   Has refresh token: {'✅' if token_data.get('refresh_token') else '❌'}")

        print("\n" + "=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="OAuth2 Handler for YouTube and Google Drive APIs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Authenticate with YouTube and Drive
  python3 tools/oauth_handler.py auth --scopes youtube drive

  # Refresh all tokens
  python3 tools/oauth_handler.py refresh

  # Get valid access token for YouTube
  python3 tools/oauth_handler.py get_token --scope youtube

  # Check token status
  python3 tools/oauth_handler.py status
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Auth command
    auth_parser = subparsers.add_parser("auth", help="Authenticate and get tokens")
    auth_parser.add_argument(
        "--scopes",
        nargs="+",
        choices=list(self.scope_map.keys()),
        default=list(self.scope_map.keys()),
        help="Scopes to authenticate (default: all)"
    )

    # Refresh command
    refresh_parser = subparsers.add_parser("refresh", help="Refresh access tokens")
    refresh_parser.add_argument(
        "--scope",
        choices=list(self.scope_map.keys()),
        help="Specific scope to refresh (default: all)"
    )

    # Get token command
    get_token_parser = subparsers.add_parser("get_token", help="Get valid access token")
    get_token_parser.add_argument(
        "--scope",
        required=True,
        choices=list(self.scope_map.keys()),
        help="Scope to get token for"
    )

    # Status command
    subparsers.add_parser("status", help="Check token status")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    handler = OAuthHandler()

    if args.command == "auth":
        handler.authenticate(args.scopes)

    elif args.command == "refresh":
        handler.refresh_tokens(args.scope)

    elif args.command == "get_token":
        token = handler.get_valid_token(args.scope)
        if token:
            print(token)

    elif args.command == "status":
        handler.check_status()


if __name__ == "__main__":
    main()
