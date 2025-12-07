#!/usr/bin/env python3
import json
import requests
import re
import os
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# State machine for tracking docs in progress
DOC_STATE_FILE = os.path.join(PROJECT_ROOT, 'data/outline_doc_state.json')

def _load_doc_state():
    if not os.path.exists(DOC_STATE_FILE):
        return {'doc_in_progress': None, 'slug_history': []}
    try:
        with open(DOC_STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'doc_in_progress': None, 'slug_history': []}

def _save_doc_state(state):
    try:
        with open(DOC_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"⚠️ Warning: Could not save doc state: {e}", file=sys.stderr)

def _mark_doc_in_progress(slug):
    state = _load_doc_state()
    if state['doc_in_progress'] and state['doc_in_progress'] != slug:
        return {'status': 'error', 'message': f'❌ Another doc already in progress: {state["doc_in_progress"]}. Complete or abandon it first.'}
    state['doc_in_progress'] = slug
    if slug not in state['slug_history']:
        state['slug_history'].append(slug)
    _save_doc_state(state)
    return {'status': 'success'}

def _clear_doc_in_progress():
    state = _load_doc_state()
    state['doc_in_progress'] = None
    _save_doc_state(state)

def _check_slug_violation(slug):
    """
    Check for slug duplication in:
    1. Current session (slug_history)
    2. Outline queue (same slug + date)
    """
    state = _load_doc_state()

    # Check current session
    if slug in state['slug_history'] and state['doc_in_progress'] != slug:
        return {'status': 'error', 'message': f'❌ Slug "{slug}" already used in this session. Use Edit tool to modify existing file, not Write tool to create new versions.'}

    # Check outline_queue.json for slug+date conflicts
    queue_file = os.path.join(PROJECT_ROOT, 'data/outline_queue.json')
    if os.path.exists(queue_file):
        try:
            with open(queue_file, 'r', encoding='utf-8') as f:
                queue_data = json.load(f)

            # Extract base slug and date from filename (format: slug_YYYYMMDD or just slug)
            import re
            slug_parts = slug.rsplit('_', 1)
            if len(slug_parts) == 2 and re.match(r'\d{8}', slug_parts[1]):
                base_slug = slug_parts[0]
                slug_date = slug_parts[1]
            else:
                base_slug = slug
                slug_date = None

            # Check if same slug+date combo already exists in queue
            for entry_key, entry_data in queue_data.get('entries', {}).items():
                # Compare with entry keys in queue
                entry_parts = entry_key.rsplit('_', 1)
                if len(entry_parts) == 2 and re.match(r'\d{8}', entry_parts[1]):
                    entry_base_slug = entry_parts[0]
                    entry_date = entry_parts[1]
                else:
                    entry_base_slug = entry_key
                    entry_date = None

                # Match if same base slug and same date (or both have no date)
                if entry_base_slug == base_slug:
                    if slug_date == entry_date:
                        return {
                            'status': 'error',
                            'message': f'❌ Duplicate slug+date detected: "{slug}" already in outline_queue.json as "{entry_key}". Use Edit tool to update existing file instead of creating new version.'
                        }
        except Exception as e:
            # Don't fail on queue read error, just log warning
            print(f"Warning: Could not check outline_queue.json: {e}", file=sys.stderr)

    return {'status': 'ok'}


def _update_working_context(result):
    try:
        if not isinstance(result, dict) or 'data' not in result:
            return
        data = result['data']
        if not isinstance(data, dict) or 'id' not in data:
            return
        doc_id = data.get('id')
        title = data.get('title', 'Untitled')
        collection_id = data.get('collectionId')
        context_file = os.path.join(PROJECT_ROOT, 'data/working_context.json')
        if not os.path.exists(context_file):
            return
        with open(context_file, 'r', encoding='utf-8') as f:
            context = json.load(f)
        collection_name = None
        for name, info in context.get('collections', {}).items():
            if info.get('id') == collection_id:
                collection_name = name
                break
        if not collection_name:
            return
        if 'docs' not in context['collections'][collection_name]:
            context['collections'][collection_name]['docs'] = []
        existing = [d for d in context['collections'][collection_name]['docs'] if d.get('id') == doc_id]
        if not existing:
            context['collections'][collection_name]['docs'].append({'id': doc_id, 'title': title})
        with open(context_file, 'w', encoding='utf-8') as f:
            json.dump(context, f, indent=2)
    except Exception:
        pass


def _create_share_link(doc_id):
    try:
        from system_settings import load_credential
        api_base = 'https://app.getoutline.com/api'
        token = load_credential('outline_api_key')
        if not token:
            return None
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        payload = {'documentId': doc_id}
        res = requests.post(f'{api_base}/shares.create', json=payload, headers=headers, verify=False)
        res.raise_for_status()
        result = res.json()
        if 'data' in result and 'url' in result['data']:
            return result['data']['url']
        return None
    except Exception:
        return None


def _load_outline_aliases():
    aliases_file = os.path.join(PROJECT_ROOT, 'data/outline_aliases.json')
    default_aliases = {"collections": {"inbox": "d5e76f6d-a87f-44f4-8897-ca15f98fa01a"}, "parent_docs": {}, "templates": {}}
    if not os.path.exists(aliases_file):
        return default_aliases
    try:
        with open(aliases_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default_aliases


def _resolve_collection_id(content_or_alias):
    aliases = _load_outline_aliases()
    COLLECTIONS = aliases.get('collections', {})
    collections_lookup = {alias.lower(): cid for alias, cid in COLLECTIONS.items()}
    default_collection_id = COLLECTIONS.get("inbox", "d5e76f6d-a87f-44f4-8897-ca15f98fa01a")
    if content_or_alias in COLLECTIONS.values():
        return content_or_alias, content_or_alias
    if str(content_or_alias).lower() in collections_lookup:
        return collections_lookup[str(content_or_alias).lower()], content_or_alias
    tag_pattern = r'#(\w+)'
    match = re.search(tag_pattern, str(content_or_alias))
    if match:
        collection_name = match.group(1).lower()
        if collection_name in collections_lookup:
            return collections_lookup[collection_name], str(content_or_alias)
    return default_collection_id, str(content_or_alias)


def _resolve_parent_doc_id(parent_alias_or_id):
    if not parent_alias_or_id:
        return None
    aliases = _load_outline_aliases()
    PARENT_DOCS = aliases.get('parent_docs', {})
    if len(str(parent_alias_or_id)) == 36 and '-' in str(parent_alias_or_id):
        return parent_alias_or_id
    for alias, doc_id in PARENT_DOCS.items():
        if alias.lower() == str(parent_alias_or_id).lower():
            return doc_id
    return parent_alias_or_id


def _find_doc_by_title(title, collection_id=None):
    try:
        from system_settings import load_credential
        api_base = 'https://app.getoutline.com/api'
        token = load_credential('outline_api_key')
        if not token:
            return None
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        payload = {'query': title, 'limit': 10}
        if collection_id:
            payload['collectionId'] = collection_id
        res = requests.post(f'{api_base}/documents.search', json=payload, headers=headers, verify=False)
        if res.status_code == 200:
            results = res.json().get('data', [])
            for result in results:
                doc = result.get('document', {})
                if doc.get('title', '').strip().lower() == title.strip().lower():
                    return doc
        return None
    except Exception:
        return None


def create_doc(params):
    title = params.get('title')
    content_file = params.get('content_file')
    content = params.get('content') or params.get('text')
    parent_doc_id = params.get('parent_doc_id')
    if content_file:
        if os.path.exists(content_file):
            with open(content_file, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            return {'status': 'error', 'message': f'Content file not found: {content_file}'}
    collection_id, cleaned_content = _resolve_collection_id(content)
    if content != cleaned_content:
        cleaned_content = re.sub(r'#(\w+)', '', cleaned_content).strip()
    else:
        cleaned_content = content
    existing_doc = _find_doc_by_title(title, collection_id)
    if existing_doc:
        return {'status': 'skipped', 'message': f'Document "{title}" already exists', 'data': existing_doc, 'duplicate_prevented': True}
    from system_settings import load_credential
    api_base = 'https://app.getoutline.com/api'
    token = load_credential('outline_api_key')
    if not token:
        return {'status': 'error', 'message': 'Missing Outline API token'}
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    payload = {'title': title, 'text': cleaned_content, 'collectionId': collection_id, 'publish': True}
    if parent_doc_id:
        payload['parentDocumentId'] = parent_doc_id
    res = requests.post(f'{api_base}/documents.create', json=payload, headers=headers, verify=False)
    res.raise_for_status()
    result = res.json()
    _update_working_context(result)
    if 'data' in result and 'id' in result['data']:
        doc_id = result['data']['id']
        share_url = _create_share_link(doc_id)
        if share_url:
            result['data']['share_url'] = share_url
    return result


def create_child_doc(params):
    title = params.get('title')
    content = params.get('content') or params.get('text')
    parent_doc_id = params.get('parent_doc_id')
    if not parent_doc_id:
        return {'status': 'error', 'message': 'parent_doc_id is required'}
    collection_id, cleaned_content = _resolve_collection_id(content)
    if content != cleaned_content:
        cleaned_content = re.sub(r'#(\w+)', '', cleaned_content).strip()
    else:
        cleaned_content = content
    from system_settings import load_credential
    api_base = 'https://app.getoutline.com/api'
    token = load_credential('outline_api_key')
    if not token:
        return {'status': 'error', 'message': 'Missing Outline API token'}
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    payload = {'title': title, 'text': cleaned_content, 'collectionId': collection_id, 'parentDocumentId': parent_doc_id, 'publish': True}
    res = requests.post(f'{api_base}/documents.create', json=payload, headers=headers, verify=False)
    res.raise_for_status()
    result = res.json()
    _update_working_context(result)
    if 'data' in result and 'id' in result['data']:
        doc_id = result['data']['id']
        share_url = _create_share_link(doc_id)
        if share_url:
            result['data']['share_url'] = share_url
    return result


def get_doc(doc_id):
    from system_settings import load_credential
    api_base = 'https://app.getoutline.com/api'
    token = load_credential('outline_api_key')
    if not token:
        return {'status': 'error', 'message': 'Missing Outline API token'}
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    res = requests.post(f'{api_base}/documents.info', json={'id': doc_id}, headers=headers, verify=False)
    res.raise_for_status()
    return res.json()


def reply_claude_inbox(params):
    """
    Reply to Claude Inbox. Hardcoded doc_id, always append.
    Impossible to misuse - no way to queue files or hit wrong doc.

    Params:
        text: The reply text (required)

    Returns:
        update_doc response
    """
    CLAUDE_INBOX_DOC_ID = "27ac62a2-8fdc-482c-926a-f0f974ef28c8"

    text = params.get('text')
    if not text:
        return {'status': 'error', 'message': 'Missing reply text'}

    # Format the reply with separator
    formatted_reply = f"\n\n---\n\n**Claude Response:**\n\n{text}"

    # Call update_doc with hardcoded values
    return update_doc({
        'doc_id': CLAUDE_INBOX_DOC_ID,
        'text': formatted_reply,
        'append': True
    })


def update_doc(params):
    doc_id = params.get('doc_id')
    title = params.get('title')
    text = params.get('text') or params.get('content')
    file_path = params.get('file_path')
    append = params.get('append', False)
    publish = params.get('publish', True)

    if not doc_id:
        return {'status': 'error', 'message': 'doc_id is required'}

    if file_path and os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()

    from system_settings import load_credential
    api_base = 'https://app.getoutline.com/api'
    token = load_credential('outline_api_key')
    if not token:
        return {'status': 'error', 'message': 'Missing Outline API token'}
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

    payload = {'id': doc_id, 'publish': publish, 'done': True}
    if title is not None:
        payload['title'] = title
    if text is not None:
        payload['text'] = text
        # Always explicitly set append parameter to avoid ambiguity
        payload['append'] = bool(append)

    res = requests.post(f'{api_base}/documents.update', json=payload, headers=headers, verify=False)
    res.raise_for_status()
    return res.json()


def update_doc_by_title(params):
    title = params.get('title')
    content = params.get('content') or params.get('text')
    append = params.get('append', False)
    collection = params.get('collection')
    if not title:
        return {'status': 'error', 'message': 'title parameter required'}
    if not content:
        return {'status': 'error', 'message': 'content parameter required'}
    collection_id = None
    if collection:
        collection_id, _ = _resolve_collection_id(collection)
    search_result = search_docs({'query': title, 'limit': 10})
    if not search_result.get('data'):
        return {'status': 'error', 'message': f'Document not found: {title}'}
    doc_id = None
    for doc in search_result['data']:
        doc_info = doc if isinstance(doc, dict) and 'title' in doc else doc.get('document', {})
        if doc_info.get('title') == title:
            if collection_id and doc_info.get('collectionId') != collection_id:
                continue
            doc_id = doc_info.get('id')
            break
    if not doc_id:
        return {'status': 'error', 'message': f'No exact match found for title: {title}'}
    return update_doc({'doc_id': doc_id, 'title': title, 'text': content, 'append': append})


def update_doc_section(params):
    title = params.get('title')
    section_heading = params.get('section_heading')
    section_content = params.get('section_content')
    collection = params.get('collection')
    if not title or not section_heading or not section_content:
        return {'status': 'error', 'message': 'title, section_heading, and section_content required'}
    collection_id = None
    if collection:
        collection_id, _ = _resolve_collection_id(collection)
    search_result = search_docs({'query': title, 'limit': 10})
    if not search_result.get('data'):
        return {'status': 'error', 'message': f'Document not found: {title}'}
    doc_id = None
    for doc in search_result['data']:
        doc_info = doc if isinstance(doc, dict) and 'title' in doc else doc.get('document', {})
        if doc_info.get('title') == title:
            if collection_id and doc_info.get('collectionId') != collection_id:
                continue
            doc_id = doc_info.get('id')
            break
    if not doc_id:
        return {'status': 'error', 'message': f'No exact match found for title: {title}'}
    doc_result = get_doc(doc_id)
    if not doc_result.get('data'):
        return {'status': 'error', 'message': f'Could not fetch document: {doc_id}'}
    existing_text = doc_result['data'].get('text', '')
    if not section_heading.startswith('#'):
        section_heading = f"## {section_heading}"
    heading_level = len(re.match(r'^#+', section_heading).group())
    pattern = re.escape(section_heading) + r'(.*?)(?=^#{1,' + str(heading_level) + r'}[^#]|\Z)'
    match = re.search(pattern, existing_text, re.MULTILINE | re.DOTALL)
    if match:
        new_text = re.sub(pattern, f"{section_heading}\n{section_content}\n\n", existing_text, count=1, flags=re.MULTILINE | re.DOTALL)
    else:
        new_text = f"{existing_text}\n\n{section_heading}\n{section_content}\n"
    return update_doc({'doc_id': doc_id, 'title': title, 'text': new_text, 'append': False})


def delete_doc(doc_id):
    from system_settings import load_credential
    api_base = 'https://app.getoutline.com/api'
    token = load_credential('outline_api_key')
    if not token:
        return {'status': 'error', 'message': 'Missing Outline API token'}
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    res = requests.post(f'{api_base}/documents.delete', json={'id': doc_id, 'permanent': False}, headers=headers, verify=False)
    res.raise_for_status()
    return res.json()


def restore_doc(doc_id, revision_id=''):
    from system_settings import load_credential
    api_base = 'https://app.getoutline.com/api'
    token = load_credential('outline_api_key')
    if not token:
        return {'status': 'error', 'message': 'Missing Outline API token'}
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    res = requests.post(f'{api_base}/documents.restore', json={'id': doc_id, 'revisionId': revision_id}, headers=headers, verify=False)
    res.raise_for_status()
    return res.json()


def list_docs(params):
    limit = params.get('limit', 25)
    offset = params.get('offset', 0)
    sort = params.get('sort', 'updatedAt')
    direction = params.get('direction', 'DESC')
    collection = params.get('collection')
    collection_id = None
    if collection:
        collection_id, _ = _resolve_collection_id(collection)
    from system_settings import load_credential
    api_base = 'https://app.getoutline.com/api'
    token = load_credential('outline_api_key')
    if not token:
        return {'status': 'error', 'message': 'Missing Outline API token'}
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    payload = {'limit': limit, 'offset': offset, 'sort': sort, 'direction': direction}
    if collection_id:
        payload['collectionId'] = collection_id
    res = requests.post(f'{api_base}/documents.list', headers=headers, json=payload, verify=False)
    res.raise_for_status()
    return res.json()


def search_docs(params):
    query = params.get('query')
    limit = params.get('limit', 10)
    offset = params.get('offset', 0)
    from system_settings import load_credential
    api_base = 'https://app.getoutline.com/api'
    token = load_credential('outline_api_key')
    if not token:
        return {'status': 'error', 'message': 'Missing Outline API token'}
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    payload = {'query': query, 'limit': limit, 'offset': offset}
    res = requests.post(f'{api_base}/documents.search', json=payload, headers=headers, verify=False)
    res.raise_for_status()
    return res.json()


def export_doc(params):
    doc_id = params.get('doc_id')
    filename = params.get('filename')
    from system_settings import load_credential
    if not filename:
        doc = get_doc(doc_id)
        title = doc.get('title', f'doc_{doc_id}')
        filename = f"{title.replace(' ', '_').lower()}.md"
    api_base = 'https://app.getoutline.com/api'
    token = load_credential('outline_api_key')
    if not token:
        return {'status': 'error', 'message': 'Missing Outline API token'}
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    payload = {'id': doc_id, 'exportType': 'markdown'}
    res = requests.post(f'{api_base}/documents.export', json=payload, headers=headers, verify=False)
    res.raise_for_status()
    try:
        raw = json.loads(res.text)
        markdown = raw.get('data', '')
    except json.JSONDecodeError:
        markdown = res.text
    output_dir = os.path.join('/orchestrate_user/orchestrate_exports', 'markdown')
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(markdown)
    return {'status': 'success', 'message': f'Exported to {filepath}'}


def import_doc_from_file(params):
    file_path = params.get('file_path')
    collection = params.get('collection')
    parent_doc_id = params.get('parent_doc_id') or params.get('parentDocumentId')
    template = params.get('template', False)
    publish = params.get('publish', True)
    if parent_doc_id:
        parent_doc_id = _resolve_parent_doc_id(parent_doc_id)
    file_content = ""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
    else:
        return {'status': 'error', 'message': f'File not found: {file_path}'}
    # Collection resolution: parent's collection > explicit param > hashtag
    if parent_doc_id:
        parent_doc = get_doc(parent_doc_id)
        if parent_doc.get('data') and parent_doc['data'].get('collectionId'):
            collection_id = parent_doc['data']['collectionId']
        else:
            # Parent exists but no collection - fall back to explicit or hashtag
            if collection:
                collection_id, _ = _resolve_collection_id(collection)
            else:
                collection_id, _ = _resolve_collection_id(file_content)
    elif collection:
        collection_id, _ = _resolve_collection_id(collection)
    else:
        collection_id, _ = _resolve_collection_id(file_content)
    # Title resolution: explicit param > file parsing
    title = params.get('title')
    if not title and file_content:
        title_match = re.match(r'^#\s+(.+)$', file_content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
    if title:
        search_result = search_docs({'query': title, 'limit': 10})
        if search_result.get('data'):
            for result in search_result['data']:
                doc = result.get('document', {})
                if doc.get('title', '').strip().lower() == title.strip().lower():
                    return {'status': 'skipped', 'message': f'Document "{title}" already exists', 'data': doc, 'duplicate_prevented': True}
    from system_settings import load_credential
    api_base = 'https://app.getoutline.com/api'
    token = load_credential('outline_api_key')
    if not token:
        return {'status': 'error', 'message': 'Missing Outline API token'}
    headers = {'Authorization': f'Bearer {token}'}
    filename = os.path.basename(file_path)
    with open(file_path, 'rb') as f:
        files = {'file': (filename, f, 'text/markdown')}
        data = {'collectionId': collection_id, 'template': str(template).lower(), 'publish': str(publish).lower()}
        if parent_doc_id:
            data['parentDocumentId'] = parent_doc_id
        res = requests.post(f'{api_base}/documents.import', headers=headers, files=files, data=data, verify=False)
    res.raise_for_status()
    result = res.json()

    # If title parameter was provided, update the doc title (import uses filename as title)
    if title and result.get('data', {}).get('id'):
        doc_id = result['data']['id']
        update_payload = {'id': doc_id, 'title': title, 'done': True}
        update_headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        update_res = requests.post(f'{api_base}/documents.update', json=update_payload, headers=update_headers, verify=False)
        update_res.raise_for_status()
        result = update_res.json()

    return result


def move_doc(params):
    doc_id = params.get('doc_id')
    collection = params.get('collection')
    parent_document_id = params.get('parentDocumentId')
    if not collection:
        return {'status': 'error', 'message': 'collection is required'}
    collection_id, _ = _resolve_collection_id(collection)
    from system_settings import load_credential
    api_base = 'https://app.getoutline.com/api'
    token = load_credential('outline_api_key')
    if not token:
        return {'status': 'error', 'message': 'Missing Outline API token'}
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    payload = {'id': doc_id, 'collectionId': collection_id}
    if parent_document_id:
        payload['parentDocumentId'] = parent_document_id
    res = requests.post(f'{api_base}/documents.move', json=payload, headers=headers, verify=False)
    res.raise_for_status()
    return res.json()


def get_url(doc_id):
    return {'status': 'success', 'url': f'https://getoutline.com/doc/{doc_id}'}


def create_share_link(params):
    doc_id = params.get('doc_id')
    if not doc_id:
        return {'status': 'error', 'message': 'doc_id is required'}
    from system_settings import load_credential
    api_base = 'https://app.getoutline.com/api'
    token = load_credential('outline_api_key')
    if not token:
        return {'status': 'error', 'message': 'Missing Outline API token'}
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    try:
        payload = {'documentId': doc_id}
        res = requests.post(f'{api_base}/shares.create', json=payload, headers=headers, verify=False)
        res.raise_for_status()
        result = res.json()
        if 'data' in result and 'url' in result['data']:
            return {'status': 'success', 'share_url': result['data']['url'], 'doc_id': doc_id, 'message': f'Share link created: {result["data"]["url"]}'}
        else:
            return {'status': 'error', 'message': 'Share link creation failed - no URL in response'}
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            return {'status': 'error', 'message': f'Share link may already exist for doc {doc_id}'}
        return {'status': 'error', 'message': f'HTTP error: {str(e)}'}
    except Exception as e:
        return {'status': 'error', 'message': f'Failed to create share link: {str(e)}'}


def create_collection(params):
    name = params.get('name')
    description = params.get('description', '')
    permission = params.get('permission', 'read_write')
    icon = params.get('icon', 'collection')
    color = params.get('color', '#4E5C6E')
    sharing = params.get('sharing', False)
    from system_settings import load_credential
    api_base = 'https://app.getoutline.com/api'
    token = load_credential('outline_api_key')
    if not token:
        return {'status': 'error', 'message': 'Missing Outline API token'}
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    payload = {'name': name, 'description': description, 'permission': permission, 'icon': icon, 'color': color, 'sharing': sharing}
    res = requests.post(f'{api_base}/collections.create', json=payload, headers=headers, verify=False)
    res.raise_for_status()
    return res.json()


def get_collection(collection_id):
    resolved_id, _ = _resolve_collection_id(collection_id)
    from system_settings import load_credential
    api_base = 'https://app.getoutline.com/api'
    token = load_credential('outline_api_key')
    if not token:
        return {'status': 'error', 'message': 'Missing Outline API token'}
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    payload = {'id': resolved_id}
    res = requests.post(f'{api_base}/collections.info', json=payload, headers=headers, verify=False)
    res.raise_for_status()
    return res.json()


def update_collection(params):
    collection_id = params.get('collection_id')
    name = params.get('name')
    description = params.get('description')
    permission = params.get('permission')
    icon = params.get('icon')
    color = params.get('color')
    sharing = params.get('sharing')
    resolved_id, _ = _resolve_collection_id(collection_id)
    from system_settings import load_credential
    api_base = 'https://app.getoutline.com/api'
    token = load_credential('outline_api_key')
    if not token:
        return {'status': 'error', 'message': 'Missing Outline API token'}
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    payload = {'id': resolved_id}
    if name:
        payload['name'] = name
    if description:
        payload['description'] = description
    if permission:
        payload['permission'] = permission
    if icon:
        payload['icon'] = icon
    if color:
        payload['color'] = color
    if sharing is not None:
        payload['sharing'] = sharing
    res = requests.post(f'{api_base}/collections.update', json=payload, headers=headers, verify=False)
    res.raise_for_status()
    return res.json()


def delete_collection(collection_id):
    resolved_id, _ = _resolve_collection_id(collection_id)
    from system_settings import load_credential
    api_base = 'https://app.getoutline.com/api'
    token = load_credential('outline_api_key')
    if not token:
        return {'status': 'error', 'message': 'Missing Outline API token'}
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    payload = {'id': resolved_id}
    res = requests.post(f'{api_base}/collections.delete', json=payload, headers=headers, verify=False)
    res.raise_for_status()
    return res.json()


def ask_outline_ai(params):
    query = params.get('query')
    from system_settings import load_credential
    token = load_credential('outline_api_key')
    if not token:
        return {'status': 'error', 'message': 'Missing Outline API token'}
    url = "https://app.getoutline.com/api/documents.answerQuestion"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"query": query}
    res = requests.post(url, headers=headers, json=payload, verify=False)
    if res.status_code != 200:
        return {'status': 'error', 'message': res.text}
    return {'status': 'success', 'data': res.json()}


def get_nested_doc(params):
    doc_id = params.get('doc_id')
    from system_settings import load_credential
    token = load_credential("outline_api_key")
    if not token:
        return {"status": "error", "message": "Missing Outline API key."}
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    api_base = "https://app.getoutline.com/api"
    res = requests.post(f"{api_base}/documents.info", headers=headers, json={"id": doc_id})
    res.raise_for_status()
    parent = res.json().get("data", {})
    children_res = requests.post(f"{api_base}/documents.list", headers=headers, json={"parentDocumentId": doc_id})
    children_res.raise_for_status()
    children = children_res.json().get("data", [])
    return {"status": "success", "parent": parent, "children": children, "child_count": len(children)}


def list_collection_docs(params):
    collection = params.get('collection')
    if not collection:
        return {"status": "error", "message": "collection is required"}
    collection_id, _ = _resolve_collection_id(collection)
    from system_settings import load_credential
    api_base = "https://app.getoutline.com/api"
    token = load_credential("outline_api_key")
    if not token:
        return {"status": "error", "message": "Missing Outline API key."}
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"collectionId": collection_id, "limit": 100}
    res = requests.post(f"{api_base}/documents.list", headers=headers, json=payload, verify=False)
    if res.status_code != 200:
        return {"status": "error", "message": res.text}
    docs = res.json().get("data", [])
    return {"status": "success", "documents": [{"id": doc.get("id"), "title": doc.get("title")} for doc in docs]}


def get_doc_comments(params):
    doc_id = params.get('doc_id')
    include_anchor_text = params.get('include_anchor_text', True)
    if not doc_id:
        return {'status': 'error', 'message': 'doc_id is required'}
    from system_settings import load_credential
    api_base = 'https://app.getoutline.com/api'
    token = load_credential('outline_api_key')
    if not token:
        return {'status': 'error', 'message': 'Missing Outline API token'}
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    payload = {'documentId': doc_id, 'includeAnchorText': include_anchor_text, 'limit': 100, 'offset': 0, 'sort': 'createdAt', 'direction': 'ASC'}
    res = requests.post(f'{api_base}/comments.list', json=payload, headers=headers, verify=False)
    res.raise_for_status()
    result = res.json()
    comments = result.get('data', [])
    return {'status': 'success', 'doc_id': doc_id, 'comment_count': len(comments), 'comments': comments}


def delete_comment(params):
    comment_id = params.get('comment_id')
    if not comment_id:
        return {'status': 'error', 'message': 'comment_id is required'}
    from system_settings import load_credential
    api_base = 'https://app.getoutline.com/api'
    token = load_credential('outline_api_key')
    if not token:
        return {'status': 'error', 'message': 'Missing Outline API token'}
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    payload = {'id': comment_id}
    res = requests.post(f'{api_base}/comments.delete', json=payload, headers=headers, verify=False)
    res.raise_for_status()
    return {'status': 'success', 'message': f'Comment {comment_id} deleted', 'comment_id': comment_id}


def delete_doc_comments(params):
    doc_id = params.get('doc_id')
    if not doc_id:
        return {'status': 'error', 'message': 'doc_id is required'}
    comments_result = get_doc_comments({'doc_id': doc_id})
    if comments_result.get('status') != 'success':
        return comments_result
    comments = comments_result.get('comments', [])
    if not comments:
        return {'status': 'success', 'message': 'No comments to delete', 'doc_id': doc_id, 'deleted_count': 0}
    deleted_count = 0
    errors = []
    for comment in comments:
        comment_id = comment.get('id')
        if comment_id:
            try:
                delete_comment({'comment_id': comment_id})
                deleted_count += 1
            except Exception as e:
                errors.append(f"Failed to delete {comment_id}: {str(e)}")
    return {'status': 'success', 'message': f'Deleted {deleted_count} comment(s) from doc {doc_id}', 'doc_id': doc_id, 'deleted_count': deleted_count, 'errors': errors if errors else None}


def sync_doc_index(params):
    from system_settings import load_credential
    api_base = 'https://app.getoutline.com/api'
    token = load_credential('outline_api_key')
    if not token:
        return {'status': 'error', 'message': 'Missing Outline API token'}
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    batch_size = params.get('batch_size', 100)
    aliases = _load_outline_aliases()
    collections = aliases.get('collections', {})
    id_to_alias = {cid: alias for alias, cid in collections.items()}
    all_docs = {}
    offset = 0
    total_fetched = 0
    while True:
        payload = {'limit': batch_size, 'offset': offset, 'sort': 'updatedAt', 'direction': 'DESC'}
        try:
            res = requests.post(f'{api_base}/documents.list', headers=headers, json=payload, verify=False)
            res.raise_for_status()
            result = res.json()
            docs = result.get('data', [])
            if not docs:
                break
            for doc in docs:
                doc_id = doc.get('id')
                if doc_id:
                    collection_id = doc.get('collectionId')
                    parent_doc_id = doc.get('parentDocumentId')
                    collection_alias = id_to_alias.get(collection_id, collection_id)
                    all_docs[doc_id] = {'title': doc.get('title', 'Untitled'), 'collection_id': collection_alias, 'parent_doc_id': parent_doc_id, 'url_id': doc.get('urlId')}
            total_fetched += len(docs)
            pagination = result.get('pagination', {})
            if not pagination.get('nextPath'):
                break
            offset += batch_size
        except Exception as e:
            return {'status': 'error', 'message': f'Failed to fetch docs at offset {offset}: {str(e)}', 'docs_fetched': total_fetched}
    reference_file = os.path.join(PROJECT_ROOT, 'data/outline_reference.json')
    os.makedirs(os.path.dirname(reference_file), exist_ok=True)
    try:
        with open(reference_file, 'w', encoding='utf-8') as f:
            json.dump(all_docs, f, indent=2)
    except Exception as e:
        return {'status': 'error', 'message': f'Failed to write reference file: {str(e)}', 'docs_fetched': total_fetched}
    return {'status': 'success', 'message': f'Synced {total_fetched} docs to outline_reference.json', 'total_docs': total_fetched, 'reference_file': reference_file}


def search_local(params):
    query = params.get('query', '').lower()
    limit = params.get('limit', 10)
    collection_filter = params.get('collection_id')
    if not query:
        return {'status': 'error', 'message': 'Missing required parameter: query'}
    reference_file = os.path.join(PROJECT_ROOT, 'data/outline_reference.json')
    if not os.path.exists(reference_file):
        return {'status': 'error', 'message': 'outline_reference.json not found. Run sync_doc_index first.', 'hint': 'python3 tools/outline_editor.py sync_doc_index'}
    try:
        with open(reference_file, 'r', encoding='utf-8') as f:
            all_docs = json.load(f)
    except Exception as e:
        return {'status': 'error', 'message': f'Failed to read reference file: {str(e)}'}
    matches = []
    for doc_id, doc_data in all_docs.items():
        title = doc_data.get('title', '').lower()
        if collection_filter and doc_data.get('collection_id') != collection_filter:
            continue
        if query in title:
            matches.append({'id': doc_id, 'title': doc_data.get('title'), 'collection_id': doc_data.get('collection_id'), 'parent_id': doc_data.get('parent_id'), 'url_id': doc_data.get('url_id')})
    matches = matches[:limit]
    return {'status': 'success', 'message': f'Found {len(matches)} matching doc(s)', 'matches': matches, 'total_matches': len(matches), 'query': query, 'note': 'This search used local index. Use get_doc(doc_id) to fetch full content.'}


def add_field_to_reference_entry(params):
    doc_id = params.get('doc_id')
    field_name = params.get('field_name')
    field_value = params.get('field_value')
    if not doc_id:
        return {'status': 'error', 'message': 'Missing required parameter: doc_id'}
    if not field_name:
        return {'status': 'error', 'message': 'Missing required parameter: field_name'}
    reference_file = os.path.join(PROJECT_ROOT, 'data/outline_reference.json')
    if not os.path.exists(reference_file):
        return {'status': 'error', 'message': 'outline_reference.json not found. Run sync_doc_index first.'}
    try:
        with open(reference_file, 'r', encoding='utf-8') as f:
            all_docs = json.load(f)
    except Exception as e:
        return {'status': 'error', 'message': f'Failed to read reference file: {str(e)}'}
    if doc_id not in all_docs:
        return {'status': 'error', 'message': f'Document {doc_id} not found in outline_reference.json'}
    all_docs[doc_id][field_name] = field_value
    try:
        with open(reference_file, 'w', encoding='utf-8') as f:
            json.dump(all_docs, f, indent=2)
    except Exception as e:
        return {'status': 'error', 'message': f'Failed to write reference file: {str(e)}'}
    return {'status': 'success', 'message': f'Added field "{field_name}" to doc {doc_id}', 'doc_id': doc_id, 'field_name': field_name, 'field_value': field_value, 'updated_entry': all_docs[doc_id]}


def batch_add_field_to_reference(params):
    doc_ids = params.get('doc_ids', [])
    field_name = params.get('field_name')
    field_value = params.get('field_value')
    per_doc_values = params.get('per_doc_values', {})
    if not doc_ids:
        return {'status': 'error', 'message': 'Missing required parameter: doc_ids (list)'}
    if not field_name:
        return {'status': 'error', 'message': 'Missing required parameter: field_name'}
    if not isinstance(doc_ids, list):
        return {'status': 'error', 'message': 'doc_ids must be a list'}
    reference_file = os.path.join(PROJECT_ROOT, 'data/outline_reference.json')
    if not os.path.exists(reference_file):
        return {'status': 'error', 'message': 'outline_reference.json not found. Run sync_doc_index first.'}
    try:
        with open(reference_file, 'r', encoding='utf-8') as f:
            all_docs = json.load(f)
    except Exception as e:
        return {'status': 'error', 'message': f'Failed to read reference file: {str(e)}'}
    updated_count = 0
    errors = []
    for doc_id in doc_ids:
        if doc_id not in all_docs:
            errors.append(f'Doc {doc_id} not found')
            continue
        value_to_set = per_doc_values.get(doc_id, field_value)
        all_docs[doc_id][field_name] = value_to_set
        updated_count += 1
    try:
        with open(reference_file, 'w', encoding='utf-8') as f:
            json.dump(all_docs, f, indent=2)
    except Exception as e:
        return {'status': 'error', 'message': f'Failed to write reference file: {str(e)}'}
    return {'status': 'success', 'message': f'Added field "{field_name}" to {updated_count} doc(s)', 'updated_count': updated_count, 'total_requested': len(doc_ids), 'errors': errors if errors else None}


def queue_doc(params):
    title = params.get('title')
    file = params.get('file')
    collection = params.get('collection')
    parent_doc_id = params.get('parent_doc_id')
    publish = params.get('publish', True)
    if not title:
        return {'status': 'error', 'message': 'Missing required parameter: title'}
    if not file:
        return {'status': 'error', 'message': 'Missing required parameter: file'}

    # REJECT inbox reply attempts - these should use update_doc directly
    inbox_reply_patterns = ['inbox_reply', 'claude_reply', 'inbox_update', 'inbox_response']
    file_lower = file.lower()
    for pattern in inbox_reply_patterns:
        if pattern in file_lower:
            return {
                'status': 'error',
                'message': f'❌ REJECTED: "{file}" looks like an inbox reply. Use update_doc with append=true instead of queue_doc. Inbox replies update existing docs, not create new ones.'
            }

    # REJECT debug output as titles
    debug_patterns = ['process_queue', 'after loading', 'task:', 'debug:', 'log:', 'print(']
    title_lower = title.lower()
    for pattern in debug_patterns:
        if pattern in title_lower:
            return {
                'status': 'error',
                'message': f'❌ REJECTED: Title "{title[:50]}..." looks like debug output, not a document title. Check your parameters.'
            }
    if 'outline_docs_queue/' in file or 'outline_docs_queue\\' in file:
        return {'status': 'error', 'message': 'Filename must not include "outline_docs_queue/" directory prefix'}
    if '/' in file or '\\' in file:
        return {'status': 'error', 'message': 'Filename must not contain path separators'}
    if not file.endswith('.md'):
        return {'status': 'error', 'message': 'Filename must end with .md extension'}

    # Check slug violations
    queue_key = file.replace('.md', '')
    slug_check = _check_slug_violation(queue_key)
    if slug_check['status'] == 'error':
        return slug_check

    # Read file content to extract hashtags
    file_path = os.path.join(PROJECT_ROOT, 'outline_docs_queue', file)
    file_content = ""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()

    # Parse hashtags from file content
    aliases = _load_outline_aliases()
    collection_aliases = {alias.lower(): alias for alias in aliases.get('collections', {}).keys()}
    parent_aliases = {alias.lower(): alias for alias in aliases.get('parent_docs', {}).keys()}

    # Extract all hashtags from content
    hashtags = re.findall(r'#([\w-]+)', file_content)

    parsed_collection = None
    parsed_parent = None

    # Match hashtags: collections first, then parent docs
    for tag in hashtags:
        tag_lower = tag.lower()
        if tag_lower in collection_aliases and not parsed_collection:
            parsed_collection = collection_aliases[tag_lower]
        elif tag_lower in parent_aliases and not parsed_parent:
            parsed_parent = parent_aliases[tag_lower]

    # Explicit params override parsed hashtags
    final_collection = collection or parsed_collection
    final_parent = parent_doc_id or parsed_parent

    # If parent exists but no collection specified, get parent's collection
    if final_parent and not final_collection:
        parent_doc_id_resolved = _resolve_parent_doc_id(final_parent)
        if parent_doc_id_resolved:
            parent_doc = get_doc(parent_doc_id_resolved)
            if parent_doc.get('data') and parent_doc['data'].get('collectionId'):
                parent_collection_id = parent_doc['data']['collectionId']
                # Map collection ID back to collection name
                collections = aliases.get('collections', {})
                for coll_name, coll_id in collections.items():
                    if coll_id == parent_collection_id:
                        final_collection = coll_name
                        break

    # Collection is required (either from param or parsed or parent)
    if not final_collection:
        return {'status': 'error', 'message': 'Missing collection: provide collection param or use #collection hashtag in file'}

    # Validate collection
    valid_collections = list(aliases.get('collections', {}).keys())
    if final_collection.lower() not in [c.lower() for c in valid_collections]:
        return {'status': 'error', 'message': f'Invalid collection: "{final_collection}". Must be one of: {", ".join(valid_collections)}'}

    queue_key = file.replace('.md', '')
    queue_file = os.path.join(PROJECT_ROOT, 'data/outline_queue.json')
    if os.path.exists(queue_file):
        with open(queue_file, 'r', encoding='utf-8') as f:
            queue = json.load(f)
    else:
        queue = {'entries': {}}
    if 'entries' not in queue:
        queue['entries'] = {}

    # LAYER 3: QUEUE ENFORCEMENT - Reject duplicate queue attempts
    if queue_key in queue['entries']:
        existing = queue['entries'][queue_key]
        return {
            'status': 'error',
            'message': f'❌ Doc already queued: {queue_key}',
            'violation': {
                'file': file,
                'existing_entry': existing,
                'hint': 'Use Edit tool to modify existing file, not Write tool to create new versions'
            }
        }

    # LAYER 2: AUTO-CLEANUP - Delete duplicate files before queueing
    queue_dir = os.path.join(PROJECT_ROOT, 'outline_docs_queue')
    if os.path.exists(queue_dir):
        base_slug = queue_key.rsplit('_', 1)[0] if '_' in queue_key else queue_key
        pattern = re.compile(rf'^{re.escape(base_slug)}.*\.md$')

        duplicate_files = []
        for existing_file in os.listdir(queue_dir):
            if pattern.match(existing_file) and existing_file != file:
                duplicate_files.append(existing_file)

        if duplicate_files:
            for dup_file in duplicate_files:
                dup_path = os.path.join(queue_dir, dup_file)
                try:
                    os.remove(dup_path)
                    print(f"🗑️  Auto-cleanup: Deleted duplicate file {dup_file}", file=sys.stderr)
                except Exception as e:
                    print(f"⚠️  Warning: Could not delete {dup_file}: {e}", file=sys.stderr)

    # Mark doc as in progress
    mark_result = _mark_doc_in_progress(queue_key)
    if mark_result['status'] == 'error':
        return mark_result

    entry = {'title': title, 'file': file, 'collection': final_collection, 'status': 'queued', 'created_at': datetime.now().isoformat(), 'publish': publish}
    if final_parent:
        entry['parent_doc_id'] = final_parent
    queue['entries'][queue_key] = entry
    with open(queue_file, 'w', encoding='utf-8') as f:
        json.dump(queue, f, indent=2)

    # Clear in-progress state after successful queue
    _clear_doc_in_progress()

    return {'status': 'success', 'message': f'Queued doc "{title}" for processing', 'queue_key': queue_key, 'entry': entry, 'note': 'automation_engine will process this and change status to "processed"', 'parsed_hashtags': {'collection': parsed_collection, 'parent': parsed_parent}}


def update_queue_entry(params):
    queue_key = params.get('queue_key')
    if not queue_key:
        return {'status': 'error', 'message': 'queue_key is required'}
    queue_file = os.path.join(PROJECT_ROOT, 'data/outline_queue.json')
    if not os.path.exists(queue_file):
        return {'status': 'error', 'message': 'outline_queue.json not found'}
    with open(queue_file, 'r', encoding='utf-8') as f:
        queue = json.load(f)
    if 'entries' not in queue:
        return {'status': 'error', 'message': 'outline_queue.json has no entries object'}
    if queue_key not in queue['entries']:
        return {'status': 'error', 'message': f'Entry "{queue_key}" not found in queue', 'available_keys': list(queue['entries'].keys())}
    entry = queue['entries'][queue_key]
    update_fields = {k: v for k, v in params.items() if k != 'queue_key'}
    if update_fields:
        entry.update(update_fields)
        entry['updated_at'] = datetime.now().isoformat()
    with open(queue_file, 'w', encoding='utf-8') as f:
        json.dump(queue, f, indent=2)
    return {'status': 'success', 'message': f'Updated queue entry "{queue_key}" with {len(update_fields)} field(s)', 'queue_key': queue_key, 'updated_fields': list(update_fields.keys()), 'entry': entry}


def clear_doc_state():
    _clear_doc_in_progress()
    return {'status': 'success', 'message': 'Cleared doc in-progress state'}


def reset_doc_state():
    state = {'doc_in_progress': None, 'slug_history': []}
    _save_doc_state(state)
    return {'status': 'success', 'message': 'Reset doc state (cleared history and in-progress)'}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('action')
    parser.add_argument('--params')
    parser.add_argument('--debounce', type=float, default=0.1, help='Debounce time for watch mode')
    args = parser.parse_args()
    params = json.loads(args.params) if args.params else {}

    if args.action == 'create_doc':
        result = create_doc(params)
    elif args.action == 'create_child_doc':
        result = create_child_doc(params)
    elif args.action == 'get_doc':
        result = get_doc(**params)
    elif args.action == 'update_doc':
        result = update_doc(params)
    elif args.action == 'update_doc_by_title':
        result = update_doc_by_title(params)
    elif args.action == 'update_doc_section':
        result = update_doc_section(params)
    elif args.action == 'delete_doc':
        result = delete_doc(**params)
    elif args.action == 'restore_doc':
        result = restore_doc(**params)
    elif args.action == 'list_docs':
        result = list_docs(params)
    elif args.action == 'search_docs':
        result = search_docs(params)
    elif args.action == 'get_url':
        result = get_url(**params)
    elif args.action == 'export_doc':
        result = export_doc(params)
    elif args.action == 'import_doc_from_file':
        result = import_doc_from_file(params)
    elif args.action == 'move_doc':
        result = move_doc(params)
    elif args.action == 'create_collection':
        result = create_collection(params)
    elif args.action == 'get_collection':
        result = get_collection(**params)
    elif args.action == 'update_collection':
        result = update_collection(params)
    elif args.action == 'delete_collection':
        result = delete_collection(**params)
    elif args.action == 'ask_outline_ai':
        result = ask_outline_ai(params)
    elif args.action == 'list_collection_docs':
        result = list_collection_docs(params)
    elif args.action == 'get_nested_doc':
        result = get_nested_doc(params)
    elif args.action == 'get_doc_comments':
        result = get_doc_comments(params)
    elif args.action == 'delete_comment':
        result = delete_comment(params)
    elif args.action == 'delete_doc_comments':
        result = delete_doc_comments(params)
    elif args.action == 'sync_doc_index':
        result = sync_doc_index(params)
    elif args.action == 'search_local':
        result = search_local(params)
    elif args.action == 'add_field_to_reference_entry':
        result = add_field_to_reference_entry(params)
    elif args.action == 'batch_add_field_to_reference':
        result = batch_add_field_to_reference(params)
    elif args.action == 'queue_doc':
        result = queue_doc(params)
    elif args.action == 'update_queue_entry':
        result = update_queue_entry(params)
    elif args.action == 'create_share_link':
        result = create_share_link(params)
    elif args.action == 'clear_doc_state':
        result = clear_doc_state()
    elif args.action == 'reset_doc_state':
        result = reset_doc_state()
    elif args.action == 'reply_claude_inbox':
        result = reply_claude_inbox(params)
    else:
        result = {'status': 'error', 'message': f'Unknown action {args.action}'}

    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()