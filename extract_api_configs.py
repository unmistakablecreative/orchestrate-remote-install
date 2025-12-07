#!/usr/bin/env python3
"""
extract_api_configs.py - Auto-generate orchestrate_configs.json from API tools only

Only extracts tools with actual API calls (api_base defined and endpoint usage).
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, Any


TOOLS_DIR = Path(os.path.expanduser("~/Orchestrate Github/orchestrate-jarvis/"))
OUTPUT_FILE = Path(os.path.expanduser("~/Orchestrate Github/orchestrate-jarvis/"))


def has_api_calls(content: str) -> bool:
    """Check if tool makes actual API calls"""
    # Must have api_base AND make requests
    has_api_base = 'api_base' in content and '=' in content
    has_requests = 'requests.post' in content or 'requests.get' in content or 'requests.put' in content or 'requests.delete' in content
    return has_api_base and has_requests


def extract_api_config_from_tool(file_path: Path) -> Dict[str, Any]:
    """Extract API configuration from a tool file"""
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Skip if no API calls
    if not has_api_calls(content):
        return None
    
    config = {
        "functions": {}
    }
    
    # Extract api_base
    api_base_match = re.search(r'api_base\s*=\s*[\'"]([^\'"]+)[\'"]', content)
    if api_base_match:
        config["api_base"] = api_base_match.group(1)
    else:
        return None  # Must have api_base
    
    # Extract auth patterns
    if 'Authorization' in content:
        config["auth_header"] = "Authorization"
        
        if "Bearer {token}" in content or "Bearer {" in content or 'f"Bearer {token}"' in content:
            config["auth_format"] = "Bearer {token}"
        elif "Token {token}" in content or "Token {" in content or 'f"Token {token}"' in content:
            config["auth_format"] = "Token {token}"
        elif "token {token}" in content or 'f"token {token}"' in content:
            config["auth_format"] = "token {token}"
    
    # Extract credential key
    cred_matches = re.findall(r'load_credential\([\'"]([^\'"]+)[\'"]\)', content)
    if cred_matches:
        config["credential_key"] = cred_matches[0]
    
    # Extract function definitions that make API calls
    function_pattern = r'def\s+(\w+)\s*\([^)]*\):(.*?)(?=\ndef\s|\Z)'
    functions = re.findall(function_pattern, content, re.DOTALL)
    
    for func_name, func_body in functions:
        # Skip private functions and main
        if func_name.startswith('_') or func_name == 'main':
            continue
        
        # Only include if function makes API request
        if not ('requests.post' in func_body or 'requests.get' in func_body or 
                'requests.put' in func_body or 'requests.delete' in func_body):
            continue
        
        # Extract endpoint
        endpoint_patterns = [
            r'f[\'"]?{api_base}([^{}\'"]+)[\'"]?',
            r'f[\'"]([^{}\'"]+)[\'"].*?requests\.',
            r'[\'"]([^{}\'"]*(?:/\w+){2,})[\'"]'
        ]
        
        endpoint = None
        method = "POST"  # default
        
        for pattern in endpoint_patterns:
            match = re.search(pattern, func_body)
            if match:
                endpoint = match.group(1)
                if not endpoint.startswith('/'):
                    endpoint = '/' + endpoint
                break
        
        # Detect method
        if 'requests.get' in func_body or 'GET' in func_body:
            method = "GET"
        elif 'requests.put' in func_body:
            method = "PUT"
        elif 'requests.delete' in func_body:
            method = "DELETE"
        
        if endpoint:
            config["functions"][func_name] = {
                "endpoint": endpoint,
                "method": method
            }
    
    # Only return if has functions
    if config["functions"]:
        return config
    return None


def main():
    if not TOOLS_DIR.exists():
        print(f"Error: {TOOLS_DIR} not found")
        return
    
    configs = {"tools": {}}
    
    # Process each tool file
    for tool_file in sorted(TOOLS_DIR.glob("*.py")):
        if tool_file.name.startswith('_'):
            continue
        
        tool_name = tool_file.stem
        
        try:
            config = extract_api_config_from_tool(tool_file)
            
            if config:
                configs["tools"][tool_name] = config
                print(f"✓ {tool_name}: {len(config['functions'])} API functions")
        except Exception as e:
            print(f"✗ {tool_name}: {e}")
    
    # Write output
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(configs, f, indent=2)
    
    print(f"\n✅ Generated {OUTPUT_FILE}")
    print(f"✅ Found {len(configs['tools'])} API-based tools")
    print(f"\nAPI Tools: {', '.join(sorted(configs['tools'].keys()))}")


if __name__ == '__main__':
    main()