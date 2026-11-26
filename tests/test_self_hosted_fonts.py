"""
The web app serves its own fonts and icon font.

It used to load them from Google Fonts, which sent every visitor's IP address
to Google. These tests fail if a third-party font host comes back: in the
page, in a stylesheet, in a component, or as an allowance in the Content
Security Policy. They also check that every font file the stylesheet names
is in the repository, is WOFF2, matches the hash in its name and sits next
to its licence.
"""

import hashlib
import re
from pathlib import Path

import pytest

from models import db
from tests.app_test_utils import load_test_app

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_SRC = ROOT / 'frontend' / 'src'
FONTS_DIR = FRONTEND_SRC / 'assets' / 'fonts'
FONTS_SCSS = FRONTEND_SRC / '_fonts.scss'

THIRD_PARTY_FONT_HOSTS = (
    'fonts.googleapis.com', 'fonts.gstatic.com', 'themes.googleusercontent.com', 'fonts.bunny.net',
    'use.typekit.net', 'p.typekit.net', 'use.fontawesome.com', 'kit.fontawesome.com', 'rsms.me',
    'api.fontshare.com', 'cdn.jsdelivr.net', 'cdnjs.cloudflare.com', 'unpkg.com',
)
FAMILIES = {
    'inter': 'SIL Open Font License',
    'plus-jakarta-sans': 'SIL Open Font License',
    'roboto': 'SIL Open Font License',
    'material-icons': 'Apache License',
}


def font_urls():
    return [url for url in re.findall(r"url\('(/assets/fonts/[^']+)'\)", expanded_scss()) if '#{' not in url]


def expanded_scss():
    """The stylesheet with the one interpolation it uses written out."""
    text = FONTS_SCSS.read_text(encoding='utf-8')
    files = re.findall(r"@include text-face\([^;]*?'([a-z-]+/[^']+\.woff2)'", text)
    return text + '\n' + '\n'.join(f"url('/assets/fonts/{name}')" for name in files)


class TestNoThirdPartyFontHost:

    def source_files(self):
        patterns = ('*.html', '*.scss', '*.css', '*.ts')
        return [path for pattern in patterns for path in FRONTEND_SRC.rglob(pattern)
                if 'node_modules' not in path.parts]

    def test_no_page_stylesheet_or_component_names_one(self):
        offenders = []
        for path in self.source_files():
            text = path.read_text(encoding='utf-8', errors='replace')
            offenders += [f'{path.relative_to(ROOT)}: {host}' for host in THIRD_PARTY_FONT_HOSTS if host in text]

        assert offenders == []

    def test_index_html_links_no_remote_stylesheet_or_font(self):
        html = (FRONTEND_SRC / 'index.html').read_text(encoding='utf-8')
        links = re.findall(r'<link\b[^>]*>', html)
        remote = [link for link in links
                  if re.search(r'rel="(stylesheet|preload|preconnect|dns-prefetch)"', link)
                  and re.search(r'href="(https?:)?//', link)]

        assert remote == []

    def test_no_stylesheet_imports_from_another_origin(self):
        for path in self.source_files():
            if path.suffix in ('.scss', '.css'):
                text = path.read_text(encoding='utf-8')
                assert not re.search(r'@import\s+(url\()?["\']?(https?:)?//', text), path

    def test_global_stylesheet_loads_the_fonts(self):
        assert "@use 'fonts';" in (FRONTEND_SRC / 'styles.scss').read_text(encoding='utf-8')


class TestContentSecurityPolicy:

    @pytest.fixture
    def policy(self):
        app_module, test_app = load_test_app(secret_key='test-secret-key-fonts-12345')
        with test_app.app_context():
            db.create_all()
            app_module.init_database()
            response = test_app.test_client().get('/api/health')
            db.session.remove()
            db.drop_all()
            app_module._db_initialized = False
        header = response.headers.get('Content-Security-Policy')
        if header is None:
            pytest.skip('Flask-Talisman is not installed: no policy is sent')
        return {part.split()[0]: part.split()[1:] for part in header.split(';') if part.strip()}

    def test_fonts_and_styles_come_from_the_app_only(self, policy):
        assert policy['font-src'] == ["'self'"]
        assert policy['style-src'] == ["'self'", "'unsafe-inline'"]

    def test_no_directive_allows_a_font_host(self, policy):
        allowed = ' '.join(source for sources in policy.values() for source in sources)

        for host in THIRD_PARTY_FONT_HOSTS:
            assert host not in allowed


class TestFontFiles:

    def test_the_stylesheet_names_seven_files_and_all_exist(self):
        urls = sorted(set(font_urls()))

        assert len(urls) == 7
        for url in urls:
            assert (FRONTEND_SRC / url.lstrip('/')).is_file(), url

    def test_every_file_is_woff2_and_matches_the_hash_in_its_name(self):
        files = sorted(FONTS_DIR.rglob('*.woff2'))
        assert len(files) == 7
        for path in files:
            data = path.read_bytes()
            assert data[:4] == b'wOF2', path.name
            digest = re.search(r'\.([0-9a-f]{8})\.woff2$', path.name).group(1)
            assert hashlib.sha256(data).hexdigest().startswith(digest), path.name

    def test_no_file_is_shipped_that_the_stylesheet_does_not_use(self):
        used = {url.rsplit('/', 1)[1] for url in font_urls()}
        shipped = {path.name for path in FONTS_DIR.rglob('*') if path.is_file() and path.name != 'LICENSE.txt'}

        assert shipped == used

    def test_only_woff2_is_shipped_and_the_bundle_stays_small(self):
        files = [path for path in FONTS_DIR.rglob('*') if path.is_file() and path.name != 'LICENSE.txt']

        assert {path.suffix for path in files} == {'.woff2'}
        assert sum(path.stat().st_size for path in files) < 450_000

    @pytest.mark.parametrize('family, licence', sorted(FAMILIES.items()))
    def test_each_family_ships_its_licence(self, family, licence):
        text = (FONTS_DIR / family / 'LICENSE.txt').read_text(encoding='utf-8')

        assert licence in text
        assert {path.name for path in FONTS_DIR.iterdir() if path.is_dir()} == set(FAMILIES)

    def test_the_icon_font_is_preloaded_from_the_app(self):
        html = (FRONTEND_SRC / 'index.html').read_text(encoding='utf-8')
        icon_file = next(path.name for path in (FONTS_DIR / 'material-icons').glob('*.woff2'))

        assert f'href="/assets/fonts/material-icons/{icon_file}"' in html

    def test_icons_are_not_swapped_for_their_names_while_loading(self):
        """font-display: swap would show "check_circle" as text until the font arrived."""
        text = FONTS_SCSS.read_text(encoding='utf-8')
        icon_face = text[text.index("font-family: 'Material Icons'"):]

        assert 'font-display: block' in icon_face.split('}')[0]
