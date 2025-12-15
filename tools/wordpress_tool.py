#!/usr/bin/env python3
"""
WordPress Tool - Queue-based WordPress publishing with templates.
Authentication via credentials.json under "wordpress" key.
"""

import json
import os
import re
import base64
import requests
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

QUEUE_FILE = os.path.join(PROJECT_ROOT, 'data/wordpress_queue.json')
TEMPLATES_FILE = os.path.join(PROJECT_ROOT, 'data/wordpress_templates.json')
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, 'credentials.json')


# === Credential Loading ===

def load_wordpress_credentials(site):
    """Load WordPress credentials for a specific site from credentials.json"""
    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            creds = json.load(f)
        wp_creds = creds.get('wordpress', {})
        site_creds = wp_creds.get(site)
        if not site_creds:
            return None
        return site_creds
    except Exception:
        return None


def get_auth_header(site):
    """Get authorization header for WordPress REST API"""
    creds = load_wordpress_credentials(site)
    if not creds:
        return None

    # WordPress Application Passwords use Basic Auth
    # Format: base64(username:application_password)
    token = creds.get('token')
    if not token:
        return None

    # Token should be in format "username:password" or just the token if already base64
    if ':' in token:
        encoded = base64.b64encode(token.encode()).decode()
    else:
        encoded = token

    return {'Authorization': f'Basic {encoded}'}


# === Queue Management ===

def load_queue():
    """Load the WordPress queue"""
    if not os.path.exists(QUEUE_FILE):
        return []
    try:
        with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def save_queue(queue):
    """Save the WordPress queue"""
    os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
    with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
        json.dump(queue, f, indent=2)


def load_templates():
    """Load WordPress templates"""
    if not os.path.exists(TEMPLATES_FILE):
        # Create default templates
        default_templates = {
            "speaker": {
                "type": "page",
                "content_template": """<div class="speaker-profile">
  <img src="{{photo_url}}" alt="{{name}}">
  <h1>{{name}}</h1>
  <div class="bio">{{bio}}</div>
  <div class="social">{{social_links}}</div>
</div>"""
            },
            "sponsor": {
                "type": "page",
                "content_template": """<div class="sponsor">
  <img src="{{logo_url}}" alt="{{company}}">
  <h1>{{company}}</h1>
  <div class="description">{{description}}</div>
</div>"""
            },
            "event": {
                "type": "page",
                "content_template": """<div class="event">
  <h1>{{title}}</h1>
  <div class="date">{{date}}</div>
  <div class="details">{{details}}</div>
</div>"""
            },
            "post": {
                "type": "post",
                "content_template": "{{content}}"
            },
            "page": {
                "type": "page",
                "content_template": "{{content}}"
            }
        }
        os.makedirs(os.path.dirname(TEMPLATES_FILE), exist_ok=True)
        with open(TEMPLATES_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_templates, f, indent=2)
        return default_templates

    try:
        with open(TEMPLATES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def render_template(template_content, params):
    """Render a template with given params using {{variable}} syntax"""
    result = template_content
    for key, value in params.items():
        if isinstance(value, dict):
            # Convert dict to formatted string for things like social_links
            value = ', '.join([f'{k}: {v}' for k, v in value.items()])
        elif isinstance(value, list):
            value = ', '.join(str(v) for v in value)
        result = result.replace(f'{{{{{key}}}}}', str(value) if value else '')
    return result


def render_from_config(config_file):
    """
    Render HTML from a JSON config file. Deterministic config-based rendering
    for landing pages with array support (e.g., speakers list).

    Config structure:
    {
        "title": "Event Title",
        "dates": "January 15-17, 2025",
        "location": "San Francisco, CA",
        "cta_text": "Register Now",
        "cta_link": "https://example.com/register",
        "description": "Event description...",
        "speakers": [
            {"name": "Speaker Name", "title": "CEO", "bio": "Bio text..."},
            ...
        ]
    }

    Returns rendered HTML ready for WordPress publish.
    """
    # Load config file
    config_path = config_file
    if not os.path.isabs(config_file):
        config_path = os.path.join(PROJECT_ROOT, 'data', config_file)

    if not os.path.exists(config_path):
        return {'status': 'error', 'message': f'Config file not found: {config_path}'}

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        return {'status': 'error', 'message': f'Invalid JSON in config: {e}'}

    # Extract config values with defaults
    title = config.get('title', 'Untitled Event')
    dates = config.get('dates', '')
    location = config.get('location', '')
    cta_text = config.get('cta_text', 'Learn More')
    cta_link = config.get('cta_link', '#')
    description = config.get('description', '')
    speakers = config.get('speakers', [])

    # Build subtitle from dates/location
    subtitle_parts = []
    if dates:
        subtitle_parts.append(dates)
    if location:
        subtitle_parts.append(location)
    subtitle = ' • '.join(subtitle_parts) if subtitle_parts else ''

    # Build speaker cards HTML
    speaker_cards = []
    for speaker in speakers:
        speaker_name = speaker.get('name', '')
        speaker_title = speaker.get('title', '')
        speaker_bio = speaker.get('bio', '')
        speaker_image = speaker.get('image', 'https://via.placeholder.com/150')
        speaker_cards.append(f'''<div style="background: white; border-radius: 12px; padding: 30px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); text-align: center;">
        <img src="{speaker_image}" alt="{speaker_name}" style="width: 150px; height: 150px; border-radius: 50%; object-fit: cover; margin-bottom: 20px;">
        <h3 style="font-size: 24px; margin: 0 0 8px 0; color: #333;">{speaker_name}</h3>
        <p style="font-size: 16px; color: #667eea; margin: 0 0 15px 0; font-weight: 500;">{speaker_title}</p>
        <p style="font-size: 14px; line-height: 1.5; color: #666; margin: 0;">{speaker_bio}</p>
      </div>''')
    speakers_html = '\n      '.join(speaker_cards)

    # Build full HTML with inline styles (theme-independent)
    rendered_html = f'''<style>header, nav, .site-header, .page-title, .entry-title, .tcb-page-title, .tve-page-title, .ast-page-title, .elementor-page-title {{ display: none !important; }} body {{ margin: 0; padding: 0; }}</style>
<div style="width: 100%; margin: 0; padding: 0;">
  <!-- Hero Section -->
  <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 500px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; padding: 60px 20px;">
    <h1 style="color: white; font-size: 72px; font-weight: bold; margin: 0 0 20px 0; line-height: 1.1;">{title}</h1>
    <p style="color: white; font-size: 24px; margin: 0 0 30px 0;">{subtitle}</p>
    <a href="{cta_link}" style="display: inline-block; background: white; color: #667eea; font-size: 18px; font-weight: bold; padding: 20px 40px; border-radius: 8px; text-decoration: none;">{cta_text}</a>
  </div>

  <!-- Description Section -->
  <div style="max-width: 800px; margin: 60px auto; padding: 0 20px; text-align: center;">
    <p style="font-size: 20px; line-height: 1.6; color: #333;">{description}</p>
  </div>

  <!-- Speakers Section -->
  <div style="background: #f8f9fa; padding: 60px 20px;">
    <h2 style="text-align: center; font-size: 42px; margin: 0 0 40px 0; color: #333;">Speakers</h2>
    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 30px; max-width: 1000px; margin: 0 auto;">
      {speakers_html}
    </div>
  </div>
</div>'''

    return {
        'status': 'success',
        'html': rendered_html,
        'title': title,
        'config_file': config_file
    }


# === Thrive Theme Builder Config ===
# Map of sites to their blank canvas Thrive template IDs
# These templates have no header, nav, sidebar, or footer
THRIVE_BLANK_TEMPLATES = {
    "unmistakablecreative.com": 24110  # "Blank Landing Page (No Header/Footer)"
}

# === Custom PHP Template Config ===
# Sites that have page-blank-canvas.php uploaded to their theme directory
# This template bypasses ALL frameworks (including Thrive) - just renders content
BLANK_CANVAS_PHP_SITES = {
    "unmistakablecreative.com": "page-blank-canvas.php"  # Custom PHP template
}


def get_blank_canvas_template(site):
    """Get the custom blank canvas PHP template slug for a site if configured"""
    return BLANK_CANVAS_PHP_SITES.get(site)


def get_thrive_blank_template_id(site):
    """Get the blank canvas Thrive template ID for a site if configured"""
    return THRIVE_BLANK_TEMPLATES.get(site)


# === WordPress API Functions ===

def get_api_base(site):
    """Get WordPress REST API base URL"""
    # Ensure site has protocol
    if not site.startswith('http'):
        site = f'https://{site}'
    return f'{site}/wp-json/wp/v2'


def fetch_categories(site):
    """Fetch all categories from WordPress site"""
    auth = get_auth_header(site)
    if not auth:
        return []

    api_base = get_api_base(site)
    try:
        resp = requests.get(f'{api_base}/categories', headers=auth, params={'per_page': 100})
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def find_or_create_category(site, category_name):
    """Find existing category or create new one"""
    auth = get_auth_header(site)
    if not auth:
        return None

    api_base = get_api_base(site)
    categories = fetch_categories(site)

    # Look for existing category
    for cat in categories:
        if cat.get('name', '').lower() == category_name.lower():
            return cat['id']

    # Create new category
    try:
        resp = requests.post(
            f'{api_base}/categories',
            headers={**auth, 'Content-Type': 'application/json'},
            json={'name': category_name}
        )
        resp.raise_for_status()
        return resp.json().get('id')
    except Exception:
        return None


def auto_categorize(title, content):
    """Auto-detect category based on content analysis"""
    text = f'{title} {content}'.lower()

    category_keywords = {
        'speaker': ['speaker', 'keynote', 'presenter', 'talk'],
        'sponsor': ['sponsor', 'partner', 'company', 'brand'],
        'event': ['event', 'conference', 'meetup', 'workshop', 'webinar'],
        'news': ['news', 'announcement', 'update', 'press'],
        'blog': ['blog', 'article', 'post', 'thoughts'],
    }

    for category, keywords in category_keywords.items():
        if any(kw in text for kw in keywords):
            return category

    return 'uncategorized'


def create_post(site, title, content, status='draft', categories=None):
    """Create a WordPress post"""
    auth = get_auth_header(site)
    if not auth:
        return {'status': 'error', 'message': f'No credentials found for site: {site}'}

    api_base = get_api_base(site)

    payload = {
        'title': title,
        'content': content,
        'status': status  # draft, publish, pending, future, private
    }

    if categories:
        payload['categories'] = categories

    try:
        resp = requests.post(
            f'{api_base}/posts',
            headers={**auth, 'Content-Type': 'application/json'},
            json=payload
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            'status': 'success',
            'post_id': data.get('id'),
            'published_url': data.get('link'),
            'title': data.get('title', {}).get('rendered', title)
        }
    except requests.exceptions.HTTPError as e:
        return {'status': 'error', 'message': f'HTTP Error: {e.response.status_code} - {e.response.text}'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def create_page(site, title, content, status='draft', meta=None, template=None, use_blank_canvas=False):
    """Create a WordPress page

    Args:
        site: WordPress site key from credentials
        title: Page title
        content: Page content (HTML)
        status: draft, publish, pending, future, private
        meta: Dict of meta fields. For Thrive: {"thrive_tcb_post_hide_title": "1"}
              Common keys: _wp_page_template, thrive_tcb_post_hide_title
        template: Page template slug. Use list_page_templates to see available options.
                  Common values: '', 'elementor_canvas', 'full-width', etc.
                  Note: Thrive Theme Builder sites use set_thrive_template instead.
        use_blank_canvas: If True, automatically apply blank canvas template.
                          First checks for custom PHP template (page-blank-canvas.php),
                          falls back to Thrive blank template if PHP not available.
    """
    auth = get_auth_header(site)
    if not auth:
        return {'status': 'error', 'message': f'No credentials found for site: {site}'}

    api_base = get_api_base(site)

    payload = {
        'title': title,
        'content': content,
        'status': status  # draft, publish, pending, future, private
    }

    # Check for custom blank canvas PHP template first
    blank_canvas_php = get_blank_canvas_template(site) if use_blank_canvas else None
    if blank_canvas_php and template is None:
        # Use custom PHP template that bypasses all frameworks
        payload['template'] = blank_canvas_php
    elif template is not None:
        payload['template'] = template

    if meta:
        payload['meta'] = meta

    try:
        resp = requests.post(
            f'{api_base}/pages',
            headers={**auth, 'Content-Type': 'application/json'},
            json=payload
        )
        resp.raise_for_status()
        data = resp.json()
        page_id = data.get('id')

        result = {
            'status': 'success',
            'page_id': page_id,
            'published_url': data.get('link'),
            'title': data.get('title', {}).get('rendered', title)
        }

        # If PHP template was used, note it
        if blank_canvas_php and template is None:
            result['template_applied'] = blank_canvas_php
            result['template_type'] = 'custom_php_blank_canvas'
        # Otherwise, try Thrive blank template if requested
        elif use_blank_canvas and page_id and not blank_canvas_php:
            thrive_template_id = get_thrive_blank_template_id(site)
            if thrive_template_id:
                template_result = set_thrive_template(site, page_id, thrive_template_id)
                if template_result.get('status') == 'success':
                    result['thrive_template_applied'] = thrive_template_id
                    result['thrive_template_name'] = 'Blank Landing Page (No Header/Footer)'
                else:
                    result['thrive_template_warning'] = template_result.get('message')

        return result
    except requests.exceptions.HTTPError as e:
        return {'status': 'error', 'message': f'HTTP Error: {e.response.status_code} - {e.response.text}'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


# === Actions ===

ACTIONS = {
    "queue_for_publish": {
        "required": ["entry_key", "title", "site"],
        "optional": ["content", "template_name", "params", "status", "type", "scheduled_time"],
        "description": "Add entry to WordPress publishing queue"
    },
    "publish_queue": {
        "required": [],
        "optional": ["site", "entry_key"],
        "description": "Process and publish all queued entries (or filter by site/entry_key)"
    },
    "update_post": {
        "required": ["site", "post_id"],
        "optional": ["title", "content", "status"],
        "description": "Update existing WordPress post"
    },
    "update_page": {
        "required": ["site", "page_id"],
        "optional": ["title", "content", "status", "meta", "template"],
        "description": "Update existing WordPress page. meta accepts dict like {thrive_tcb_post_hide_title: '1'} for Thrive. template for page template slug."
    },
    "list_posts": {
        "required": ["site"],
        "optional": ["status", "per_page"],
        "description": "List posts from WordPress site"
    },
    "list_pages": {
        "required": ["site"],
        "optional": ["status", "per_page"],
        "description": "List pages from WordPress site"
    },
    "get_queue": {
        "required": [],
        "optional": ["site"],
        "description": "View current WordPress queue"
    },
    "remove_from_queue": {
        "required": ["entry_key"],
        "optional": [],
        "description": "Remove entry from queue"
    },
    "add_template": {
        "required": ["template_name", "type", "content_template"],
        "optional": [],
        "description": "Add or update a WordPress template"
    },
    "list_templates": {
        "required": [],
        "optional": [],
        "description": "List available WordPress templates"
    },
    "publish_from_config": {
        "required": ["config_file", "site", "entry_key"],
        "optional": ["status", "use_blank_canvas"],
        "description": "Render landing page from JSON config and publish to WordPress. use_blank_canvas=true (default) applies Thrive blank template."
    },
    "create_page": {
        "required": ["site", "title", "content"],
        "optional": ["status", "meta", "template", "use_blank_canvas"],
        "description": "Create WordPress page. use_blank_canvas=true applies Thrive blank template (no header/footer). meta accepts dict for custom fields."
    },
    "list_page_templates": {
        "required": ["site"],
        "optional": [],
        "description": "List available page templates including Thrive templates if the site uses Thrive Theme Builder"
    },
    "set_thrive_template": {
        "required": ["site", "page_id", "template_id"],
        "optional": [],
        "description": "Assign a Thrive Theme Builder template to a page. Use list_page_templates to find template IDs."
    },
    "get_page": {
        "required": ["site", "page_id"],
        "optional": [],
        "description": "Get details of a WordPress page including template and Thrive settings"
    }
}


def queue_for_publish(entry_key, title, site, content=None, template_name=None, params=None, status='draft', type=None, scheduled_time=None):
    """Add entry to WordPress publishing queue"""
    queue = load_queue()

    # Check for duplicate entry_key
    existing = [e for e in queue if e.get('entry_key') == entry_key]
    if existing:
        return {'status': 'error', 'message': f'Entry key "{entry_key}" already exists in queue'}

    # Determine content type
    if type:
        content_type = type
    elif template_name:
        templates = load_templates()
        template = templates.get(template_name, {})
        content_type = template.get('type', 'post')
    else:
        content_type = 'post'

    entry = {
        'entry_key': entry_key,
        'title': title,
        'content': content,
        'type': content_type,
        'status': status,  # draft, publish, pending, future, private
        'template_name': template_name,
        'params': params or {},
        'site': site,
        'queued_at': datetime.now().isoformat(),
        'published_url': None,
        'post_id': None
    }

    if scheduled_time:
        entry['scheduled_time'] = scheduled_time
        entry['status'] = 'future'

    queue.append(entry)
    save_queue(queue)

    return {
        'status': 'success',
        'message': f'Queued "{title}" for {site}',
        'entry_key': entry_key,
        'type': content_type
    }


def publish_queue(site=None, entry_key=None):
    """Process and publish all queued entries"""
    queue = load_queue()

    if not queue:
        return {'status': 'success', 'message': 'Queue is empty', 'published': 0}

    # Filter by site if specified
    to_process = queue
    if site:
        to_process = [e for e in queue if e.get('site') == site]
    if entry_key:
        to_process = [e for e in to_process if e.get('entry_key') == entry_key]

    # Only process entries without post_id (not yet published)
    to_process = [e for e in to_process if not e.get('post_id')]

    if not to_process:
        return {'status': 'success', 'message': 'No unpublished entries to process', 'published': 0}

    templates = load_templates()
    results = []

    for entry in to_process:
        entry_site = entry.get('site')
        entry_title = entry.get('title')
        entry_content = entry.get('content')
        entry_type = entry.get('type', 'post')
        entry_status = entry.get('status', 'draft')
        template_name = entry.get('template_name')
        params = entry.get('params', {})

        # Render content from template if specified
        if template_name and template_name in templates:
            template = templates[template_name]
            template_content = template.get('content_template', '{{content}}')
            # Merge params with any direct content
            if entry_content:
                params['content'] = entry_content
            entry_content = render_template(template_content, params)
        elif params:
            # If no template but params provided, use them directly
            entry_content = params.get('content', entry_content or '')

        # Auto-categorize for posts
        categories = None
        if entry_type == 'post':
            category_name = auto_categorize(entry_title, entry_content or '')
            cat_id = find_or_create_category(entry_site, category_name)
            if cat_id:
                categories = [cat_id]

        # Create post or page
        if entry_type == 'page':
            result = create_page(entry_site, entry_title, entry_content, entry_status)
        else:
            result = create_post(entry_site, entry_title, entry_content, entry_status, categories)

        # Update queue entry with result
        entry_key_current = entry.get('entry_key')
        for q_entry in queue:
            if q_entry.get('entry_key') == entry_key_current:
                if result.get('status') == 'success':
                    q_entry['post_id'] = result.get('post_id') or result.get('page_id')
                    q_entry['published_url'] = result.get('published_url')
                    q_entry['published_at'] = datetime.now().isoformat()
                else:
                    q_entry['error'] = result.get('message')
                break

        results.append({
            'entry_key': entry_key_current,
            'title': entry_title,
            **result
        })

    save_queue(queue)

    successful = [r for r in results if r.get('status') == 'success']
    failed = [r for r in results if r.get('status') == 'error']

    return {
        'status': 'success' if not failed else 'partial',
        'message': f'Published {len(successful)} of {len(results)} entries',
        'published': len(successful),
        'failed': len(failed),
        'results': results
    }


def update_post(site, post_id, title=None, content=None, status=None):
    """Update existing WordPress post"""
    auth = get_auth_header(site)
    if not auth:
        return {'status': 'error', 'message': f'No credentials found for site: {site}'}

    api_base = get_api_base(site)

    payload = {}
    if title:
        payload['title'] = title
    if content:
        payload['content'] = content
    if status:
        payload['status'] = status

    if not payload:
        return {'status': 'error', 'message': 'No update parameters provided'}

    try:
        resp = requests.post(
            f'{api_base}/posts/{post_id}',
            headers={**auth, 'Content-Type': 'application/json'},
            json=payload
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            'status': 'success',
            'post_id': data.get('id'),
            'published_url': data.get('link'),
            'message': f'Updated post {post_id}'
        }
    except requests.exceptions.HTTPError as e:
        return {'status': 'error', 'message': f'HTTP Error: {e.response.status_code} - {e.response.text}'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def update_page(site, page_id, title=None, content=None, status=None, meta=None, template=None):
    """Update existing WordPress page

    Args:
        site: WordPress site key from credentials
        page_id: Page ID to update
        title: New page title (optional)
        content: New page content (optional)
        status: New status (optional)
        meta: Dict of meta fields. For Thrive hide title: {"thrive_tcb_post_hide_title": "1"}
              Common keys: _wp_page_template, thrive_tcb_post_hide_title
              Thrive visibility: tve_tcb_visibility
        template: Page template slug. Use list_page_templates to see available options.
                  Note: Thrive Theme Builder sites use set_thrive_template instead.
    """
    auth = get_auth_header(site)
    if not auth:
        return {'status': 'error', 'message': f'No credentials found for site: {site}'}

    api_base = get_api_base(site)

    payload = {}
    if title:
        payload['title'] = title
    if content:
        payload['content'] = content
    if status:
        payload['status'] = status
    if template is not None:
        payload['template'] = template
    if meta:
        payload['meta'] = meta

    if not payload:
        return {'status': 'error', 'message': 'No update parameters provided'}

    try:
        resp = requests.post(
            f'{api_base}/pages/{page_id}',
            headers={**auth, 'Content-Type': 'application/json'},
            json=payload
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            'status': 'success',
            'page_id': data.get('id'),
            'published_url': data.get('link'),
            'message': f'Updated page {page_id}'
        }
    except requests.exceptions.HTTPError as e:
        return {'status': 'error', 'message': f'HTTP Error: {e.response.status_code} - {e.response.text}'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def list_posts(site, status=None, per_page=10):
    """List posts from WordPress site"""
    auth = get_auth_header(site)
    if not auth:
        return {'status': 'error', 'message': f'No credentials found for site: {site}'}

    api_base = get_api_base(site)

    params = {'per_page': per_page}
    if status:
        params['status'] = status

    try:
        resp = requests.get(f'{api_base}/posts', headers=auth, params=params)
        resp.raise_for_status()
        posts = resp.json()
        return {
            'status': 'success',
            'count': len(posts),
            'posts': [{
                'id': p.get('id'),
                'title': p.get('title', {}).get('rendered'),
                'status': p.get('status'),
                'link': p.get('link'),
                'date': p.get('date')
            } for p in posts]
        }
    except requests.exceptions.HTTPError as e:
        return {'status': 'error', 'message': f'HTTP Error: {e.response.status_code} - {e.response.text}'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def list_pages(site, status=None, per_page=10):
    """List pages from WordPress site"""
    auth = get_auth_header(site)
    if not auth:
        return {'status': 'error', 'message': f'No credentials found for site: {site}'}

    api_base = get_api_base(site)

    params = {'per_page': per_page}
    if status:
        params['status'] = status

    try:
        resp = requests.get(f'{api_base}/pages', headers=auth, params=params)
        resp.raise_for_status()
        pages = resp.json()
        return {
            'status': 'success',
            'count': len(pages),
            'pages': [{
                'id': p.get('id'),
                'title': p.get('title', {}).get('rendered'),
                'status': p.get('status'),
                'link': p.get('link'),
                'date': p.get('date')
            } for p in pages]
        }
    except requests.exceptions.HTTPError as e:
        return {'status': 'error', 'message': f'HTTP Error: {e.response.status_code} - {e.response.text}'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def get_queue(site=None):
    """View current WordPress queue"""
    queue = load_queue()

    if site:
        queue = [e for e in queue if e.get('site') == site]

    return {
        'status': 'success',
        'count': len(queue),
        'entries': queue
    }


def remove_from_queue(entry_key):
    """Remove entry from queue"""
    queue = load_queue()
    original_len = len(queue)
    queue = [e for e in queue if e.get('entry_key') != entry_key]

    if len(queue) == original_len:
        return {'status': 'error', 'message': f'Entry "{entry_key}" not found in queue'}

    save_queue(queue)
    return {'status': 'success', 'message': f'Removed "{entry_key}" from queue'}


def add_template(template_name, type, content_template):
    """Add or update a WordPress template"""
    templates = load_templates()
    templates[template_name] = {
        'type': type,
        'content_template': content_template
    }

    with open(TEMPLATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(templates, f, indent=2)

    return {'status': 'success', 'message': f'Template "{template_name}" saved'}


def list_templates():
    """List available WordPress templates"""
    templates = load_templates()
    return {
        'status': 'success',
        'count': len(templates),
        'templates': {name: {'type': t.get('type')} for name, t in templates.items()}
    }


def publish_from_config(config_file, site, entry_key, status='draft', use_blank_canvas=True):
    """
    Read config JSON, render with landing-page template, queue and publish.

    Args:
        config_file: Path to JSON config (relative to data/ or absolute)
        site: WordPress site key from credentials
        entry_key: Unique identifier for this publish
        status: WordPress status (draft, publish, pending, future, private)
        use_blank_canvas: If True (default), auto-apply Thrive blank canvas template
                          for landing pages (no header, nav, sidebar, footer)

    Returns:
        post_id and published_url on success
    """
    # Render HTML from config
    render_result = render_from_config(config_file)

    if render_result.get('status') == 'error':
        return render_result

    html_content = render_result.get('html')
    title = render_result.get('title')

    # Queue the entry
    queue_result = queue_for_publish(
        entry_key=entry_key,
        title=title,
        site=site,
        content=html_content,
        status=status,
        type='page'
    )

    if queue_result.get('status') == 'error':
        return queue_result

    # Publish immediately
    publish_result = publish_queue(site=site, entry_key=entry_key)

    if publish_result.get('status') == 'error':
        return publish_result

    # Extract result for this specific entry
    results = publish_result.get('results', [])
    for r in results:
        if r.get('entry_key') == entry_key:
            page_id = r.get('page_id') or r.get('post_id')

            final_result = {
                'status': 'success',
                'post_id': page_id,
                'published_url': r.get('published_url'),
                'title': title,
                'config_file': config_file
            }

            # Auto-apply Thrive blank canvas template for landing pages
            if use_blank_canvas and page_id:
                thrive_template_id = get_thrive_blank_template_id(site)
                if thrive_template_id:
                    template_result = set_thrive_template(site, page_id, thrive_template_id)
                    if template_result.get('status') == 'success':
                        final_result['thrive_template_applied'] = thrive_template_id
                        final_result['thrive_template_name'] = 'Blank Landing Page (No Header/Footer)'
                    else:
                        final_result['thrive_template_warning'] = template_result.get('message')

            return final_result

    return {
        'status': 'error',
        'message': 'Publish completed but entry not found in results'
    }


def list_page_templates(site):
    """List available page templates for the site

    Returns both standard WordPress templates and Thrive Theme Builder templates
    if the site uses Thrive.

    Args:
        site: WordPress site key from credentials

    Returns:
        Dict with available templates and active theme info
    """
    auth = get_auth_header(site)
    if not auth:
        return {'status': 'error', 'message': f'No credentials found for site: {site}'}

    api_base = get_api_base(site)
    site_url = api_base.replace('/wp-json/wp/v2', '')

    result = {
        'status': 'success',
        'standard_templates': [],
        'thrive_templates': [],
        'active_theme': None,
        'uses_thrive': False
    }

    # Get active theme
    try:
        resp = requests.get(f'{api_base}/themes', headers=auth)
        if resp.status_code == 200:
            themes = resp.json()
            for t in themes:
                if t.get('status') == 'active':
                    theme_name = t.get('name', {})
                    if isinstance(theme_name, dict):
                        result['active_theme'] = theme_name.get('rendered', theme_name.get('raw', ''))
                    else:
                        result['active_theme'] = str(theme_name)
                    if 'thrive' in result['active_theme'].lower():
                        result['uses_thrive'] = True
                    break
    except Exception:
        pass

    # Try to get standard page templates by checking a page's template options
    # WordPress REST API returns allowed templates in OPTIONS response
    try:
        resp = requests.options(f'{api_base}/pages', headers=auth)
        if resp.status_code == 200:
            # Templates would be in the response schema if available
            pass  # Standard templates need theme registration to show
    except Exception:
        pass

    # If Thrive theme detected, get Thrive templates
    if result['uses_thrive']:
        try:
            resp = requests.get(f'{site_url}/wp-json/wp/v2/thrive_template?per_page=50', headers=auth)
            if resp.status_code == 200:
                templates = resp.json()
                for t in templates:
                    title = t.get('title', {})
                    if isinstance(title, dict):
                        title_text = title.get('rendered', title.get('raw', ''))
                    else:
                        title_text = str(title)
                    result['thrive_templates'].append({
                        'id': t.get('id'),
                        'title': title_text or f'Template {t.get("id")}',
                        'slug': t.get('slug', '')
                    })
        except Exception:
            pass

    # Add note about blank templates
    result['notes'] = []
    if result['uses_thrive']:
        result['notes'].append('Site uses Thrive Theme Builder. Use set_thrive_template action to assign templates.')
        result['notes'].append('For blank/landing pages without header/footer, create a custom Thrive template in WP admin.')
    else:
        result['notes'].append('Use the template parameter in create_page/update_page with template slugs.')

    return result


def set_thrive_template(site, page_id, template_id):
    """Set Thrive Theme Builder template for a page

    This uses the TTB API to assign a Thrive template to a page.
    Use list_page_templates to find available template IDs.

    Args:
        site: WordPress site key from credentials
        page_id: The page ID to update
        template_id: The Thrive template ID to assign

    Returns:
        Success/error status
    """
    auth = get_auth_header(site)
    if not auth:
        return {'status': 'error', 'message': f'No credentials found for site: {site}'}

    api_base = get_api_base(site)
    site_url = api_base.replace('/wp-json/wp/v2', '')

    # Use TTB API endpoint: POST /ttb/v1/post/{post_id}/template/{template_id}
    try:
        resp = requests.post(
            f'{site_url}/wp-json/ttb/v1/post/{page_id}/template/{template_id}',
            headers={**auth, 'Content-Type': 'application/json'}
        )

        if resp.status_code == 200:
            # Verify the assignment
            verify_resp = requests.get(
                f'{api_base}/pages/{page_id}?context=edit',
                headers=auth
            )
            if verify_resp.status_code == 200:
                page_data = verify_resp.json()
                assigned_template = page_data.get('thrive_post_template', '')
                return {
                    'status': 'success',
                    'message': f'Thrive template {template_id} assigned to page {page_id}',
                    'page_id': page_id,
                    'template_id': template_id,
                    'thrive_post_template': assigned_template
                }
            return {
                'status': 'success',
                'message': f'Thrive template {template_id} assigned to page {page_id}',
                'page_id': page_id,
                'template_id': template_id
            }
        else:
            return {
                'status': 'error',
                'message': f'Failed to set template: {resp.status_code} - {resp.text[:200]}'
            }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def get_page(site, page_id):
    """Get details of a WordPress page including template info

    Args:
        site: WordPress site key from credentials
        page_id: Page ID to retrieve

    Returns:
        Page details including template, meta, and Thrive settings
    """
    auth = get_auth_header(site)
    if not auth:
        return {'status': 'error', 'message': f'No credentials found for site: {site}'}

    api_base = get_api_base(site)

    try:
        resp = requests.get(
            f'{api_base}/pages/{page_id}?context=edit',
            headers=auth
        )
        resp.raise_for_status()
        page = resp.json()

        # Extract key fields
        return {
            'status': 'success',
            'page': {
                'id': page.get('id'),
                'title': page.get('title', {}).get('rendered') if isinstance(page.get('title'), dict) else page.get('title'),
                'status': page.get('status'),
                'link': page.get('link'),
                'template': page.get('template', ''),
                'thrive_post_template': page.get('thrive_post_template', ''),
                'date': page.get('date'),
                'modified': page.get('modified')
            }
        }
    except requests.exceptions.HTTPError as e:
        return {'status': 'error', 'message': f'HTTP Error: {e.response.status_code} - {e.response.text}'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


# === Main Dispatcher ===

def run(action, params=None):
    """Main action dispatcher"""
    params = params or {}

    if action not in ACTIONS:
        return {'status': 'error', 'message': f'Unknown action: {action}', 'available_actions': list(ACTIONS.keys())}

    action_config = ACTIONS[action]

    # Check required params
    missing = [p for p in action_config.get('required', []) if p not in params]
    if missing:
        return {'status': 'error', 'message': f'Missing required params: {missing}'}

    # Dispatch to action function
    action_func = {
        'queue_for_publish': queue_for_publish,
        'publish_queue': publish_queue,
        'update_post': update_post,
        'update_page': update_page,
        'list_posts': list_posts,
        'list_pages': list_pages,
        'get_queue': get_queue,
        'remove_from_queue': remove_from_queue,
        'add_template': add_template,
        'list_templates': list_templates,
        'publish_from_config': publish_from_config,
        'create_page': create_page,
        'list_page_templates': list_page_templates,
        'set_thrive_template': set_thrive_template,
        'get_page': get_page
    }.get(action)

    if not action_func:
        return {'status': 'error', 'message': f'Action not implemented: {action}'}

    try:
        return action_func(**params)
    except TypeError as e:
        return {'status': 'error', 'message': f'Invalid params: {str(e)}'}
    except Exception as e:
        return {'status': 'error', 'message': f'Error: {str(e)}'}


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print(json.dumps({'status': 'error', 'message': 'Usage: python wordpress_tool.py <action> [--params JSON]'}))
        sys.exit(1)

    action = sys.argv[1]
    params = {}

    if '--params' in sys.argv:
        idx = sys.argv.index('--params')
        if idx + 1 < len(sys.argv):
            try:
                params = json.loads(sys.argv[idx + 1])
            except json.JSONDecodeError as e:
                print(json.dumps({'status': 'error', 'message': f'Invalid JSON params: {e}'}))
                sys.exit(1)

    result = run(action, params)
    print(json.dumps(result, indent=2))
