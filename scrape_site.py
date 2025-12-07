#!/usr/bin/env python3
"""
Site Scraper - Standalone CLI utility
Scrapes website content, downloads assets, saves to semantic_memory/{site-name}/

Usage:
    python3 scrape_site.py https://example.com
    python3 scrape_site.py https://example.com --name custom-site-name

Output:
    semantic_memory/{site-name}/
        ├── index.html          # Full page HTML
        ├── content.txt         # Extracted text content
        ├── images/             # Downloaded images
        └── assets/             # Other assets (css, js, etc)
"""

import sys
import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import argparse
from pathlib import Path


def sanitize_filename(url):
    """Convert URL to safe directory name"""
    parsed = urlparse(url)
    name = parsed.netloc.replace('www.', '')
    # Remove invalid chars
    name = re.sub(r'[^\w\-]', '_', name)
    return name


def download_file(url, output_path):
    """Download a file from URL to output_path"""
    try:
        response = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        response.raise_for_status()

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, 'wb') as f:
            f.write(response.content)

        return True
    except Exception as e:
        print(f"  ⚠️  Failed to download {url}: {str(e)}")
        return False


def scrape_site(url, site_name=None):
    """
    Scrape website content and assets

    Args:
        url: Website URL to scrape
        site_name: Optional custom name for output directory

    Returns:
        Path to created directory
    """
    print(f"🌐 Scraping: {url}")

    # Determine site name
    if not site_name:
        site_name = sanitize_filename(url)

    # Create output directory in semantic_memory
    base_dir = Path(__file__).parent / 'semantic_memory' / site_name
    base_dir.mkdir(parents=True, exist_ok=True)

    images_dir = base_dir / 'images'
    assets_dir = base_dir / 'assets'
    images_dir.mkdir(exist_ok=True)
    assets_dir.mkdir(exist_ok=True)

    print(f"📁 Output directory: {base_dir}")

    # Fetch the page
    try:
        response = requests.get(url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Failed to fetch {url}: {str(e)}")
        return None

    soup = BeautifulSoup(response.content, 'html.parser')

    # Save full HTML
    html_path = base_dir / 'index.html'
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(soup.prettify())
    print(f"✅ Saved HTML: index.html")

    # Extract text content
    # Remove script and style elements
    for script in soup(['script', 'style', 'nav', 'footer', 'header']):
        script.decompose()

    text_content = soup.get_text(separator='\n', strip=True)

    content_path = base_dir / 'content.txt'
    with open(content_path, 'w', encoding='utf-8') as f:
        f.write(text_content)
    print(f"✅ Saved text content: content.txt ({len(text_content)} chars)")

    # Download images
    images = soup.find_all('img')
    print(f"\n🖼️  Found {len(images)} images, downloading...")

    downloaded_images = 0
    for idx, img in enumerate(images):
        src = img.get('src')
        if not src:
            continue

        # Handle relative URLs
        img_url = urljoin(url, src)

        # Generate filename
        parsed = urlparse(img_url)
        original_name = os.path.basename(parsed.path)
        if not original_name or '.' not in original_name:
            # Generate name from index if no filename
            ext = '.jpg'  # default
            if 'png' in img_url.lower():
                ext = '.png'
            elif 'gif' in img_url.lower():
                ext = '.gif'
            elif 'svg' in img_url.lower():
                ext = '.svg'
            original_name = f"image_{idx}{ext}"

        output_path = images_dir / original_name

        print(f"  [{idx+1}/{len(images)}] {original_name}")
        if download_file(img_url, output_path):
            downloaded_images += 1

    print(f"✅ Downloaded {downloaded_images}/{len(images)} images")

    # Download CSS files
    css_links = soup.find_all('link', rel='stylesheet')
    print(f"\n🎨 Found {len(css_links)} CSS files, downloading...")

    downloaded_css = 0
    for idx, link in enumerate(css_links):
        href = link.get('href')
        if not href:
            continue

        css_url = urljoin(url, href)
        parsed = urlparse(css_url)
        css_name = os.path.basename(parsed.path) or f'style_{idx}.css'

        output_path = assets_dir / css_name

        print(f"  [{idx+1}/{len(css_links)}] {css_name}")
        if download_file(css_url, output_path):
            downloaded_css += 1

    print(f"✅ Downloaded {downloaded_css}/{len(css_links)} CSS files")

    # Create summary file
    summary_path = base_dir / 'SUMMARY.md'
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(f"# Site Scrape: {site_name}\n\n")
        f.write(f"**Source URL:** {url}\n\n")
        f.write(f"**Scraped:** {Path(html_path).stat().st_mtime}\n\n")
        f.write(f"## Contents\n\n")
        f.write(f"- `index.html` - Full page HTML\n")
        f.write(f"- `content.txt` - Extracted text ({len(text_content)} chars)\n")
        f.write(f"- `images/` - {downloaded_images} images\n")
        f.write(f"- `assets/` - {downloaded_css} CSS files\n")

    print(f"\n✅ Summary saved: SUMMARY.md")
    print(f"\n🎉 Scrape complete!")
    print(f"📂 Location: {base_dir}")
    print(f"🔗 Shareable path: semantic_memory/{site_name}/")

    return base_dir


def main():
    parser = argparse.ArgumentParser(
        description='Scrape website content and assets to semantic_memory directory'
    )
    parser.add_argument('url', help='Website URL to scrape')
    parser.add_argument('--name', help='Custom name for output directory (default: derived from URL)')

    args = parser.parse_args()

    if not args.url.startswith('http'):
        print("❌ URL must start with http:// or https://")
        sys.exit(1)

    result = scrape_site(args.url, args.name)

    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
