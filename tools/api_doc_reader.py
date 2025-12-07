import os, json, requests
import time
import re

# Postman API key - load from credentials.json
POSTMAN_API_KEY = ""  # Set in credentials.json
POSTMAN_BASE_URL = "https://api.getpostman.com"

def load_tool_construction_prompt():
    """Load tool construction prompt from JSON file"""
    prompt_path = os.path.expanduser("~/Orchestrate Github/orchestrate-jarvis/")
    
    if not os.path.exists(prompt_path):
        raise FileNotFoundError(f"Could not find tool_construction_prompt.json at {prompt_path}")
    
    with open(prompt_path, "r") as f:
        return json.load(f)

def load_rtff_protocol():
    """Load RTFF protocol from JSON file"""
    rtff_path = os.path.expanduser("~/Orchestrate Github/orchestrate-jarvis/")
    
    if not os.path.exists(rtff_path):
        raise FileNotFoundError(f"Could not find rtff_protocol.json at {rtff_path}")
    
    with open(rtff_path, "r") as f:
        return json.load(f)

def load_postman_mappings():
    """Load or create postman_collections.json mapping file"""
    mappings_dir = os.path.expanduser("~/Orchestrate Github/orchestrate-jarvis/")
    os.makedirs(mappings_dir, exist_ok=True)
    mappings_file = f"{mappings_dir}/postman_collections.json"
    
    if os.path.exists(mappings_file):
        with open(mappings_file, "r") as f:
            return json.load(f)
    else:
        # Create initial mappings file with examples
        initial_mappings = {
            "_readme": "Add API collection mappings here. Format: 'company_name': 'postman_collection_id'",
            "_example": "stripe: 'abc123-def456-collection-id'",
            "_instructions": "Use refresh_api_collections action to automatically discover and add new collections"
        }
        save_postman_mappings(initial_mappings)
        return initial_mappings

def save_postman_mappings(mappings):
    """Save updated mapping file"""
    mappings_dir = os.path.expanduser("~/Orchestrate Github/orchestrate-jarvis/")
    os.makedirs(mappings_dir, exist_ok=True)
    with open(f"{mappings_dir}/postman_collections.json", "w") as f:
        json.dump(mappings, f, indent=2)

def clean_collection_name(name):
    """Clean collection name to use as company key"""
    # Convert to lowercase and replace spaces/special chars with underscores
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', name.lower())
    cleaned = re.sub(r'\s+', '_', cleaned)
    # Remove trailing underscores and ensure it's not empty
    cleaned = cleaned.strip('_')
    return cleaned if cleaned else 'unknown_collection'

def get_workspace_collections():
    """Fetch all collections from the workspace using Postman API"""
    headers = {
        "X-Api-Key": POSTMAN_API_KEY
    }
    
    try:
        response = requests.get(f"{POSTMAN_BASE_URL}/collections", headers=headers)
        response.raise_for_status()
        
        collections_data = response.json()
        return collections_data.get("collections", [])
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to fetch workspace collections: {str(e)}")

def refresh_api_collections(params):
    """Auto-discover and add all workspace collections to mappings"""
    try:
        print("Fetching workspace collections from Postman API...")
        
        # Get all collections from workspace
        collections = get_workspace_collections()
        
        if not collections:
            return {
                "status": "success",
                "message": "No collections found in workspace",
                "collections_found": 0,
                "collections_added": 0
            }
        
        # Load existing mappings
        mappings = load_postman_mappings()
        
        # Track what we're adding
        added_collections = []
        skipped_collections = []
        
        for collection in collections:
            collection_name = collection.get("name", "unknown")
            collection_uid = collection.get("uid") or collection.get("id")
            
            if not collection_uid:
                continue
                
            # Clean the name for use as key
            company_key = clean_collection_name(collection_name)
            
            # Skip if already exists (don't overwrite existing mappings)
            if company_key in mappings and not company_key.startswith('_'):
                skipped_collections.append({
                    "name": collection_name,
                    "key": company_key,
                    "uid": collection_uid,
                    "reason": "already_exists"
                })
                continue
            
            # Add new mapping
            mappings[company_key] = collection_uid
            added_collections.append({
                "name": collection_name,
                "key": company_key, 
                "uid": collection_uid
            })
        
        # Save updated mappings
        save_postman_mappings(mappings)
        
        return {
            "status": "success",
            "message": f"Discovered {len(collections)} collections, added {len(added_collections)} new mappings",
            "collections_found": len(collections),
            "collections_added": len(added_collections),
            "collections_skipped": len(skipped_collections),
            "added": added_collections,
            "skipped": skipped_collections,
            "total_mapped": len([k for k in mappings.keys() if not k.startswith('_')])
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

def export_postman_collection(collection_uid):
    """Export Postman collection data from YOUR workspace"""
    headers = {
        "X-Api-Key": POSTMAN_API_KEY
    }
    
    export_url = f"{POSTMAN_BASE_URL}/collections/{collection_uid}"
    
    try:
        response = requests.get(export_url, headers=headers)
        response.raise_for_status()
        
        return response.json()
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to export collection {collection_uid}: {str(e)}")

def parse_postman_collection(collection_data, company_name):
    """Parse Postman collection JSON into enriched tool spec format"""
    collection = collection_data.get("collection", {})
    
    def extract_requests_from_items(items, path=""):
        """Recursively extract requests from Postman collection items with enhanced parsing"""
        requests = []
        
        for item in items:
            if "request" in item:
                # This is a request item
                request = item["request"]
                method = request.get("method", "GET").upper()
                
                # Extract endpoint from URL
                url_obj = request.get("url", {})
                endpoint = ""
                path_params = []
                query_params = []
                
                if isinstance(url_obj, str):
                    endpoint = url_obj
                elif isinstance(url_obj, dict):
                    # Build endpoint from path array
                    path_parts = url_obj.get("path", [])
                    if path_parts:
                        endpoint = "/" + "/".join(str(p) for p in path_parts)
                    
                    # Extract path variables with types
                    variables = url_obj.get("variable", [])
                    for var in variables:
                        if var.get("key"):
                            path_params.append({
                                "name": var["key"],
                                "type": var.get("type", "string"),
                                "required": True,
                                "description": var.get("description", f"Path parameter: {var['key']}")
                            })
                    
                    # Extract query parameters with enhanced info
                    query_params_raw = url_obj.get("query", [])
                    for param in query_params_raw:
                        if param.get("key"):
                            query_params.append({
                                "name": param["key"],
                                "type": "string",  # Default, could be enhanced
                                "required": not param.get("disabled", False),
                                "description": param.get("description", f"Query parameter: {param['key']}"),
                                "example": param.get("value", "")
                            })
                    
                    # Add query string to endpoint
                    if query_params:
                        query_string = "&".join([f"{q['name']}={{value}}" for q in query_params])
                        endpoint += "?" + query_string
                
                # Extract body parameters with structure
                body_params = []
                request_examples = {}
                body = request.get("body", {})
                
                if body.get("mode") == "raw":
                    try:
                        raw_body = body.get("raw", "{}")
                        body_json = json.loads(raw_body)
                        if isinstance(body_json, dict):
                            for key, value in body_json.items():
                                param_type = "string"
                                if isinstance(value, bool):
                                    param_type = "boolean"
                                elif isinstance(value, int):
                                    param_type = "integer"
                                elif isinstance(value, list):
                                    param_type = "array"
                                elif isinstance(value, dict):
                                    param_type = "object"
                                
                                body_params.append({
                                    "name": key,
                                    "type": param_type,
                                    "required": True,  # Assume required if in example
                                    "description": f"Body parameter: {key}",
                                    "example": value
                                })
                        
                        request_examples["body"] = body_json
                    except:
                        # If JSON parsing fails, treat as raw text
                        request_examples["raw_body"] = body.get("raw", "")
                
                elif body.get("mode") == "formdata":
                    formdata = body.get("formdata", [])
                    for field in formdata:
                        if field.get("key"):
                            field_type = field.get("type", "text")
                            body_params.append({
                                "name": field["key"],
                                "type": "file" if field_type == "file" else "string",
                                "required": not field.get("disabled", False),
                                "description": field.get("description", f"Form field: {field['key']}"),
                                "example": field.get("value", "")
                            })
                
                # Extract response examples if available
                response_examples = []
                if "response" in item:
                    responses = item["response"] if isinstance(item["response"], list) else [item["response"]]
                    for resp in responses:
                        try:
                            response_body = json.loads(resp.get("body", "{}"))
                            response_examples.append({
                                "status": resp.get("code", 200),
                                "name": resp.get("name", "Example response"),
                                "body": response_body
                            })
                        except:
                            pass
                
                # Create clean action name
                item_name = item.get("name", "").lower().replace(" ", "_").replace("-", "_")
                item_name = re.sub(r'[^a-zA-Z0-9_]', '', item_name)
                action_name = f"{method.lower()}_{item_name}" if item_name else f"{method.lower()}_operation"
                
                # Combine all parameters
                all_params = path_params + query_params + body_params
                
                requests.append({
                    "action": action_name,
                    "method": method,
                    "endpoint": endpoint,
                    "description": item.get("name", f"{method} {endpoint}"),
                    "parameters": all_params,
                    "request_examples": request_examples,
                    "response_examples": response_examples,
                    "source": "postman_collection_enhanced"
                })
            
            # Process nested items (folders)
            if "item" in item:
                requests.extend(extract_requests_from_items(item["item"], path))
        
        return requests
    
    # Extract all requests from collection
    all_requests = extract_requests_from_items(collection.get("item", []))
    
    # Create enhanced spec data
    spec_data = {
        "company_name": company_name,
        "collection_name": collection.get("info", {}).get("name", "Unknown"),
        "description": collection.get("info", {}).get("description", ""),
        "base_url": "https://api.airtable.com",  # Could be extracted from examples
        "authentication": {
            "type": "bearer_token",
            "header": "Authorization",
            "format": "Bearer {token}"
        },
        "actions": all_requests,
        "extracted_at": time.time(),
        "source": "postman_export_enhanced"
    }
    
    return spec_data

def extract_api(params):
    """Main function - export from YOUR forked collections"""
    company_name = params.get("company_name")

    if not company_name:
        return {"status": "error", "message": "company_name parameter required"}

    try:
        # Load collection mappings
        mappings = load_postman_mappings()

        # Filter out metadata keys
        actual_mappings = {k: v for k, v in mappings.items() if not k.startswith('_')}

        if company_name not in actual_mappings:
            return {
                "status": "error",
                "message": f"No collection UID found for {company_name}. Run refresh_api_collections first.",
                "suggestion": f"1. Manually fork the {company_name} collection in Postman UI\n2. Run: refresh_api_collections to auto-discover it\n3. Then run extract_api again",
                "available_collections": list(actual_mappings.keys())
            }

        collection_uid = actual_mappings[company_name]

        # Export from YOUR workspace - this will definitely work
        collection_data = export_postman_collection(collection_uid)

        # Parse the clean Postman JSON
        spec_data = parse_postman_collection(collection_data, company_name)

        # Save spec file
        output_dir = os.path.expanduser("~/Orchestrate Github/orchestrate-jarvis/")
        os.makedirs(output_dir, exist_ok=True)
        output_file = f"{output_dir}/{company_name}.json"

        with open(output_file, "w", encoding='utf-8') as f:
            json.dump(spec_data, f, indent=2, ensure_ascii=False)

        return {
            "status": "success",
            "company": company_name,
            "actions_extracted": len(spec_data["actions"]),
            "saved_to": output_file,
            "collection_uid": collection_uid,
            "summary": f"Successfully exported {len(spec_data['actions'])} API actions for {company_name}"
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

def filter_to_core_crud_only(actions):
    """Aggressively filter to only core CRUD operations people actually use - generic for any API"""
    
    # Core CRUD operation patterns - generic across all APIs
    crud_patterns = {
        'create': ['create', 'post', 'add', 'new', 'insert'],
        'read': ['get', 'list', 'fetch', 'read', 'retrieve', 'show', 'find'],
        'update': ['update', 'patch', 'put', 'edit', 'modify', 'set'],
        'delete': ['delete', 'remove', 'del', 'destroy', 'cancel']
    }
    
    # Skip enterprise/admin/complex operations - generic patterns
    skip_keywords = [
        'enterprise', 'admin', 'collaborator', 'permission', 'invite', 'share', 
        'audit', 'webhook', 'scim', 'group', 'export', 'redact', 'move', 
        'descendant', 'block', 'installation', 'workspace', 'batch', 'bulk',
        'ediscovery', 'logout', 'grant', 'revoke', 'claim', 'membership',
        'restriction', 'sync', 'history', 'payload', 'refresh', 'migrate',
        'transfer', 'backup', 'restore', 'archive', 'import', 'clone',
        'duplicate', 'analytics', 'report', 'log', 'event', 'notification'
    ]
    
    filtered_actions = []
    
    for action in actions:
        action_name = action['action'].lower()
        description = action['description'].lower()
        endpoint = action.get('endpoint', '').lower()
        method = action.get('method', '').upper()
        
        # Skip if contains enterprise/admin keywords
        should_skip = any(keyword in action_name or keyword in description or keyword in endpoint
                         for keyword in skip_keywords)
        
        if should_skip:
            continue
            
        # Keep if it's a basic CRUD operation
        is_crud = any(keyword in action_name or keyword in description 
                     for crud_list in crud_patterns.values() 
                     for keyword in crud_list)
        
        # Also keep basic REST operations by method
        is_basic_rest = method in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
        
        if is_crud and is_basic_rest:
            filtered_actions.append(action)
    
    return filtered_actions

def generate_tool_spec(params):
    """Generate tool specification from extracted API data and construction prompt"""
    tool_name = params.get("tool_name", "api_tool")

    try:
        # Load the tool construction prompt from the JSON file
        construction_prompt = load_tool_construction_prompt()
        rtff_protocol = load_rtff_protocol()
    except FileNotFoundError as e:
        return {"status": "error", "message": str(e)}

    # Load the API data file
    api_dir = os.path.expanduser("~/Orchestrate Github/orchestrate-jarvis/")
    api_file = f"{api_dir}/{tool_name}.json"

    if not os.path.exists(api_file):
        return {"status": "error", "message": f"API data file not found: {api_file}"}

    try:
        with open(api_file, "r", encoding='utf-8') as f:
            api_data = json.load(f)
    except Exception as e:
        return {"status": "error", "message": f"Error reading {api_file}: {str(e)}"}

    # Extract and filter actions
    all_actions = api_data.get("actions", [])
    if not all_actions:
        return {"status": "error", "message": "No actions found in API file"}

    actions = filter_to_core_crud_only(all_actions)
    if not actions:
        return {"status": "error", "message": "No CRUD operations found after filtering"}

    # Remove duplicates and normalize action names
    seen_endpoints = set()
    unique_actions = []

    for action in actions:
        endpoint_key = f"{action['method']}:{action['endpoint']}"
        if endpoint_key not in seen_endpoints:
            seen_endpoints.add(endpoint_key)

            # Normalize action name by removing method prefix
            raw = action.get("action", "").lower()
            method = action.get("method", "").lower()
            if raw.startswith(f"{method}_"):
                action["action"] = raw[len(method)+1:]

            unique_actions.append(action)

    # Build the tool specification
    tool_spec = {
        "tool_name": tool_name,
        "description": f"Tool for {tool_name} API - CRUD operations only",
        "script_path": f"tools/{tool_name}.py",
        "company_name": api_data.get("company_name", tool_name),
        "base_url": api_data.get("base_url", ""),
        "authentication": api_data.get("authentication", {}),
        "actions": unique_actions,
        "actions_count": len(unique_actions),
        "filtered_from": len(all_actions),
        "generated_at": time.time()
    }

    # Return both the tool spec AND the construction prompt
    return {
        "status": "success",
        "tool_spec": tool_spec,
        "construction_prompt": construction_prompt,
        "summary": f"Generated tool spec with {len(unique_actions)} CRUD actions (filtered from {len(all_actions)} total)",
        "next_steps": "Use the construction_prompt to generate the Python tool implementation"
    }

def list_api_collections(params):
    """List all APIs in the collection mappings"""
    try:
        mappings = load_postman_mappings()
        actual_mappings = {k: v for k, v in mappings.items() if not k.startswith('_')}
        
        return {
            "status": "success", 
            "collections": actual_mappings,
            "total_apis": len(actual_mappings)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('action')
    parser.add_argument('--params')
    args = parser.parse_args()

    # Parse params
    params = {}
    if args.params:
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError as e:
            result = {'status': 'error', 'message': f'Invalid JSON in params: {str(e)}'}
            print(json.dumps(result, indent=2))
            return

    try:
        if args.action == 'extract_api':
            result = extract_api(params)
        elif args.action == 'refresh_api_collections':
            result = refresh_api_collections(params)
        elif args.action == 'generate_tool_spec':
            result = generate_tool_spec(params)
        elif args.action == 'list_api_collections':
            result = list_api_collections(params)
        else:
            result = {'status': 'error', 'message': f'Unknown action {args.action}'}

    except Exception as e:
        result = {'status': 'error', 'message': str(e)}

    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()