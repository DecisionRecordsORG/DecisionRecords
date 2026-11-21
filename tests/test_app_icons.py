"""
The app's icon set: every icon the page or the web manifest points to must be
a file the Angular build copies to its output root, where Flask serves it.
"""
import json
import mimetypes
import os
import re
import struct
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(REPO_ROOT, 'frontend')
PUBLIC = os.path.join(FRONTEND, 'public')
INDEX_HTML = os.path.join(FRONTEND, 'src', 'index.html')

ICON_FILES = [
    'favicon.ico', 'favicon.svg', 'apple-touch-icon.png', 'icon-192.png', 'icon-512.png',
    'site.webmanifest',
]


def _link_tags():
    with open(INDEX_HTML, encoding='utf-8') as handle:
        html = handle.read()
    tags = {}
    for tag in re.findall(r'<link\b[^>]*>', html):
        rel = re.search(r'rel="([^"]+)"', tag)
        href = re.search(r'href="([^"]+)"', tag)
        if rel and href and rel.group(1) in ('icon', 'apple-touch-icon', 'manifest'):
            tags.setdefault(rel.group(1), []).append((href.group(1), tag))
    return tags


def _png_size(path):
    with open(path, 'rb') as handle:
        header = handle.read(24)
    assert header[:8] == b'\x89PNG\r\n\x1a\n', f'{path} is not a PNG'
    return struct.unpack('>II', header[16:24])


@pytest.mark.parametrize('name', ICON_FILES)
def test_icon_file_is_in_the_folder_the_build_copies_to_its_root(name):
    path = os.path.join(PUBLIC, name)

    assert os.path.isfile(path), f'{name} is missing from frontend/public'
    assert os.path.getsize(path) > 0


def test_build_copies_the_public_folder_to_the_output_root():
    with open(os.path.join(FRONTEND, 'angular.json'), encoding='utf-8') as handle:
        config = json.load(handle)

    assets = config['projects']['frontend']['architect']['build']['options']['assets']

    public_entries = [entry for entry in assets if isinstance(entry, dict) and entry.get('input') == 'public']
    assert public_entries, 'angular.json no longer copies frontend/public'
    assert public_entries[0]['glob'] == '**/*'
    assert 'output' not in public_entries[0]  # copied to the root, where the link tags point


def test_page_links_the_four_icon_tags():
    tags = _link_tags()

    icon_hrefs = [href for href, _tag in tags['icon']]
    assert icon_hrefs == ['favicon.ico', 'favicon.svg']
    assert 'sizes="48x48"' in tags['icon'][0][1]
    assert 'type="image/svg+xml"' in tags['icon'][1][1]
    assert [href for href, _tag in tags['apple-touch-icon']] == ['apple-touch-icon.png']
    assert [href for href, _tag in tags['manifest']] == ['site.webmanifest']


def test_every_linked_icon_exists():
    for entries in _link_tags().values():
        for href, _tag in entries:
            assert os.path.isfile(os.path.join(PUBLIC, href.lstrip('/'))), f'{href} is linked but missing'


def test_manifest_is_valid_and_its_icons_exist_at_the_stated_sizes():
    with open(os.path.join(PUBLIC, 'site.webmanifest'), encoding='utf-8') as handle:
        manifest = json.load(handle)

    assert manifest['name'] == 'Decision Records'
    assert len(manifest['icons']) == 2
    for icon in manifest['icons']:
        path = os.path.join(PUBLIC, icon['src'].lstrip('/'))
        assert os.path.isfile(path), f"{icon['src']} is in the manifest but missing"
        width, height = _png_size(path)
        assert f'{width}x{height}' == icon['sizes']
        assert icon['type'] == 'image/png'


def test_apple_touch_icon_is_180_pixels_square():
    assert _png_size(os.path.join(PUBLIC, 'apple-touch-icon.png')) == (180, 180)


def test_favicon_ico_is_an_icon_file():
    with open(os.path.join(PUBLIC, 'favicon.ico'), 'rb') as handle:
        assert handle.read(4) == b'\x00\x00\x01\x00'


def test_flask_serves_the_icons_with_the_right_content_types():
    """app.py names these types itself, so they do not depend on the host's mime.types."""
    import app  # noqa: F401  (registers the types on import)

    assert mimetypes.guess_type('site.webmanifest')[0] == 'application/manifest+json'
    assert mimetypes.guess_type('favicon.ico')[0] == 'image/x-icon'
    assert mimetypes.guess_type('favicon.svg')[0] == 'image/svg+xml'
    assert mimetypes.guess_type('icon-192.png')[0] == 'image/png'


def test_icon_names_are_not_caught_by_the_scanner_path_filter():
    """block_attack_paths answers 404 for paths containing these fragments."""
    from app import ATTACK_PATH_PATTERNS

    for name in ICON_FILES:
        assert not any(pattern in f'/{name}'.lower() for pattern in ATTACK_PATH_PATTERNS), name
