"""
Tests for how an unknown OAuth client is identified (Enterprise Edition):

- ee/backend/oauth_server/redirects.py: which redirect URIs are accepted and matched
- ee/backend/oauth_server/safe_fetch.py: fetching a URL someone else chose without
  reaching into our own network (server-side request forgery)
- ee/backend/oauth_server/client_metadata.py: the client_id URL, the Client ID
  Metadata Document, and its stored copy

No test here touches the network: DNS and the HTTPS exchange are stood in for.

Note: These tests require Enterprise Edition modules from ee/backend/oauth_server/
"""
import json
import os
import socket
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, OAuthClient

try:
    from ee.backend.oauth_server import client_metadata, redirects, safe_fetch
    from ee.backend.oauth_server.client_metadata import ClientMetadataError
    from ee.backend.oauth_server.safe_fetch import FetchError, FetchResult
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False
    client_metadata = redirects = safe_fetch = None
    ClientMetadataError = FetchError = Exception
    FetchResult = None

EE_TESTS_ENABLED = EE_AVAILABLE and os.environ.get('DECISION_RECORDS_EDITION', 'community') == 'enterprise'
pytestmark = pytest.mark.skipif(
    not EE_TESTS_ENABLED,
    reason="Enterprise Edition tests require DECISION_RECORDS_EDITION=enterprise and EE modules",
)

NOW = datetime(2026, 11, 25, 12, 0, 0)
CLIENT_ID = 'https://client.example.com/oauth/client.json'


@pytest.fixture(autouse=True)
def _no_remembered_fetch_failures():
    """A failed fetch is remembered in the process for a minute; one test's failure is not another's."""
    if client_metadata is not None:
        client_metadata.reset_fetch_state()
    yield
    if client_metadata is not None:
        client_metadata.reset_fetch_state()

# The documents two real clients published on 2026-11-25
CLAUDE_CODE = {
    "client_id": "https://claude.ai/oauth/claude-code-client-metadata", "client_name": "Claude Code",
    "client_uri": "https://claude.ai",
    "redirect_uris": ["http://localhost/callback", "http://127.0.0.1/callback"],
    "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
    "token_endpoint_auth_method": "none",
}
CLAUDE = {
    "client_id": "https://claude.ai/oauth/mcp-oauth-client-metadata", "client_name": "Claude",
    "client_uri": "https://claude.ai", "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
    "grant_types": ["authorization_code", "refresh_token", "urn:ietf:params:oauth:grant-type:jwt-bearer"],
    "response_types": ["code"], "token_endpoint_auth_method": "none",
}
CHATGPT = {
    "client_id": "https://chatgpt.com/oauth/client.json", "client_uri": "https://chatgpt.com/",
    "redirect_uris": ["https://chatgpt.com/connector_platform_oauth_redirect"],
    "token_endpoint_auth_method": "private_key_jwt",
    "token_endpoint_auth_methods_supported": ["none", "private_key_jwt"],
    "grant_types": ["authorization_code", "refresh_token", "urn:ietf:params:oauth:grant-type:jwt-bearer"],
    "response_types": ["code"], "client_name": "ChatGPT",
    "logo_uri": "https://persistent.oaistatic.com/sonic/misc/openai-logo.png",
    "token_endpoint_auth_signing_alg": "RS256", "jwks_uri": "https://chatgpt.com/oauth/jwks.json",
}


def _document(**changes):
    document = {
        'client_id': CLIENT_ID, 'client_name': 'Example Client', 'client_uri': 'https://client.example.com',
        'redirect_uris': ['https://client.example.com/callback'], 'token_endpoint_auth_method': 'none',
    }
    document.update(changes)
    return {key: value for key, value in document.items() if value is not ...}


# ============================================================================
# REDIRECT URIS
# ============================================================================

class TestRedirectUris:

    @pytest.mark.parametrize('uri', [
        'https://claude.ai/api/mcp/auth_callback',
        'https://chatgpt.com/connector_platform_oauth_redirect',
        'https://client.example.com/callback?x=1',
        'https://client.example.com:8443/callback',
        'http://localhost/callback',
        'http://localhost:3118/callback',
        'http://127.0.0.1/callback',
        'http://127.0.0.1:6274/oauth/callback',
        'http://[::1]:9000/callback',
    ])
    def test_registrable(self, uri):
        assert redirects.is_registrable(uri) is True

    @pytest.mark.parametrize('uri', [
        None, '', 42, 'callback', '/callback', '//client.example.com/callback',
        'http://client.example.com/callback',           # plain http anywhere but loopback
        'http://localhost.evil.test/callback',
        'http://127.0.0.1.evil.test/callback',
        'http://127.0.0.2/callback',
        'http://0.0.0.0/callback',
        'http://10.0.0.5/callback',
        'http://[::ffff:127.0.0.1]/callback',
        'https://localhost:bad/callback',
        'cursor://callback', 'myapp:/callback', 'javascript:alert(1)', 'data:text/html,x', 'file:///etc/passwd',
        'https://client.example.com/callback#fragment',
        'https://user@client.example.com/callback',
        'https://user:secret@client.example.com/callback',
        'https://client.example.com\\@evil.test/callback',
        'https://client.example.com/call back',
        'https://client.example.com/callback\n',
        'https://client.example.com/callback\x00',
        'https:///callback',
        'https://' + 'a' * 2050,
    ])
    def test_not_registrable(self, uri):
        assert redirects.is_registrable(uri) is False
        assert redirects.matches(uri, [uri]) is False

    @pytest.mark.parametrize('requested,registered,expected', [
        # https: exact string or nothing
        ('https://c.example/cb', ['https://c.example/cb'], True),
        ('https://c.example/cb', ['https://other.example/cb', 'https://c.example/cb'], True),
        ('https://c.example/cb/', ['https://c.example/cb'], False),
        ('https://c.example/cb?x=1', ['https://c.example/cb'], False),
        ('https://c.example/cb', ['https://c.example/cb?x=1'], False),
        ('https://c.example/CB', ['https://c.example/cb'], False),
        ('https://C.example/cb', ['https://c.example/cb'], False),
        ('https://c.example:443/cb', ['https://c.example/cb'], False),
        ('https://c.example:8443/cb', ['https://c.example/cb'], False),
        ('https://c.example/cb/../admin', ['https://c.example/cb'], False),
        ('https://c.example/cb%2f', ['https://c.example/cb/'], False),
        ('https://c.example.evil.test/cb', ['https://c.example/cb'], False),
        ('https://evil.test/c.example/cb', ['https://c.example/cb'], False),
        ('https://c.example/cb', ['https://c.example/'], False),
        ('https://c.example/cb', ['https://*.example/cb'], False),
        ('https://c.example/cb', [], False),
        ('https://c.example/cb', None, False),
        ('http://c.example/cb', ['https://c.example/cb'], False),
        # loopback: the port is ignored, nothing else is
        ('http://localhost:3118/callback', ['http://localhost/callback'], True),
        ('http://localhost/callback', ['http://localhost/callback'], True),
        ('http://localhost:3118/callback', ['http://localhost:8080/callback'], True),
        ('http://127.0.0.1:51000/callback', ['http://127.0.0.1/callback'], True),
        ('http://[::1]:51000/callback', ['http://[::1]/callback'], True),
        ('http://127.0.0.1:6274/oauth/callback', ['http://127.0.0.1:6276/oauth/callback'], True),
        ('http://localhost:3118/callback', ['http://127.0.0.1/callback'], False),
        ('http://127.0.0.1:3118/callback', ['http://localhost/callback'], False),
        ('http://localhost:3118/other', ['http://localhost/callback'], False),
        ('http://localhost:3118/callback?x=1', ['http://localhost/callback'], False),
        ('http://localhost:3118/callback', ['https://localhost/callback'], False),
        ('https://localhost:3118/callback', ['http://localhost/callback'], False),
        ('https://localhost:3118/callback', ['https://localhost/callback'], False),  # https is always exact
        ('http://localhost.evil.test:3118/callback', ['http://localhost/callback'], False),
        ('http://evil.test:3118/callback', ['http://localhost/callback'], False),
        ('http://localhost:3118/callback', ['https://c.example/cb'], False),
    ])
    def test_matching(self, requested, registered, expected):
        assert redirects.matches(requested, registered) is expected

    def test_the_two_real_claude_documents(self):
        assert redirects.matches('http://localhost:3118/callback', CLAUDE_CODE['redirect_uris'])
        assert redirects.matches('http://127.0.0.1:49152/callback', CLAUDE_CODE['redirect_uris'])
        assert redirects.matches('https://claude.ai/api/mcp/auth_callback', CLAUDE['redirect_uris'])
        assert not redirects.matches('https://claude.com/api/mcp/auth_callback', CLAUDE['redirect_uris'])

    def test_host_shown_to_the_user(self):
        assert redirects.redirect_host('https://claude.ai/api/mcp/auth_callback') == 'claude.ai'
        assert redirects.redirect_host('http://localhost:3118/callback') == 'localhost'
        assert redirects.redirect_host('http://[::1]:3118/callback') == '[::1]'
        assert redirects.redirect_host('nonsense') is None

    def test_loopback_only_clients_are_recognised_for_the_warning(self):
        assert redirects.loopback_only(CLAUDE_CODE['redirect_uris']) is True
        assert redirects.loopback_only(CLAUDE['redirect_uris']) is False
        assert redirects.loopback_only(['http://localhost/cb', 'https://c.example/cb']) is False
        assert redirects.loopback_only([]) is False


# ============================================================================
# FETCHING WITHOUT REACHING INSIDE
# ============================================================================

class TestPublicAddresses:

    @pytest.mark.parametrize('address', [
        '8.8.8.8', '1.1.1.1', '160.79.104.10', '2606:4700:4700::1111', '::ffff:8.8.8.8',
    ])
    def test_public(self, address):
        assert safe_fetch.is_public_address(address) is True

    @pytest.mark.parametrize('address', [
        '127.0.0.1', '127.8.9.10', '0.0.0.0', '10.1.2.3', '172.16.0.1', '172.31.255.255', '192.168.1.1',
        '169.254.169.254',        # cloud instance metadata
        '168.63.129.16',          # Azure platform services, in public address space
        '100.64.0.1',             # carrier-grade NAT
        '192.0.2.1', '198.51.100.7', '203.0.113.9', '198.18.0.1', '224.0.0.1', '240.0.0.1', '255.255.255.255',
        '::1', '::', 'fe80::1', 'fc00::1', 'fd12:3456::1', 'fec0::1', 'ff02::1',
        '::ffff:127.0.0.1', '::ffff:10.1.2.3', '::ffff:169.254.169.254',
        '64:ff9b::a01:203',       # NAT64 form of 10.1.2.3
        '2002:a01:203::',         # 6to4 form of 10.1.2.3
        '2001:0:4136:e378:8000:63bf:3fff:fdd2',  # Teredo
        '2001:db8::1',
        'not-an-address', '', '10.0.0.1/8',
    ])
    def test_not_public(self, address):
        assert safe_fetch.is_public_address(address) is False


class TestHostNames:

    @pytest.mark.parametrize('host', ['claude.ai', 'chatgpt.com', 'Client.Example.COM', 'a-b.example.org.'])
    def test_accepted(self, host):
        assert safe_fetch.check_host(host) == host.lower().rstrip('.')

    @pytest.mark.parametrize('host', [
        '', None, 'localhost', 'LOCALHOST', 'intranet', 'db',
        '127.0.0.1', '10.1.2.3', '[::1]', '::1', '169.254.169.254', '2130706433', '0x7f.0.0.1', '127.1',
        'printer.local', 'database.internal', 'something.localhost', 'vault.corp', 'router.lan', 'x.home.arpa',
        'metadata.google.internal', 'host.test', 'thing.example', 'hidden.onion',
        'bad_host.example.org', 'a..example.org', '.example.org', 'ex ample.org', 'exämple.org',
        'a' * 64 + '.example.org', ('a' * 60 + '.') * 5 + 'org',
    ])
    def test_refused(self, host):
        with pytest.raises(FetchError) as excinfo:
            safe_fetch.check_host(host)
        assert excinfo.value.transient is False


def _resolver(*addresses):
    calls = []

    def resolve(host):
        calls.append(host)
        return list(addresses)
    resolve.calls = calls
    return resolve


def _transport(status=200, headers=None, body=None, document=None, raises=None):
    calls = []

    def send(host, address, target, deadline):
        calls.append((host, address, target))
        if raises is not None:
            raise raises
        payload = body if body is not None else json.dumps(document if document is not None else _document()).encode()
        response_headers = {'content-type': 'application/json'}
        response_headers.update(headers or {})
        return status, response_headers, payload
    send.calls = calls
    return send


class TestSafeFetch:

    def test_the_document_is_fetched_from_the_address_that_was_checked(self):
        resolver, transport = _resolver('93.184.216.34'), _transport()

        result = safe_fetch.fetch_json(CLIENT_ID, resolver=resolver, transport=transport)

        assert result.document['client_id'] == CLIENT_ID
        assert resolver.calls == ['client.example.com']
        assert transport.calls == [('client.example.com', '93.184.216.34', '/oauth/client.json')]

    def test_ipv4_addresses_are_tried_first(self):
        transport = _transport()
        safe_fetch.fetch_json(CLIENT_ID, transport=transport,
                              resolver=_resolver('2606:4700::1111', '2606:4700::1001', '93.184.216.34'))
        assert transport.calls[0][1] == '93.184.216.34'

    @pytest.mark.parametrize('url', [
        'http://client.example.com/client.json',
        'ftp://client.example.com/client.json',
        'file:///etc/passwd',
        'gopher://client.example.com/x',
        'https://client.example.com:8443/client.json',
        'https://client.example.com:22/client.json',
        'https://user:pw@client.example.com/client.json',
        'https://127.0.0.1/client.json',
        'https://[::1]/client.json',
        'https://169.254.169.254/latest/meta-data/',
        'https://localhost/client.json',
        'https://database.internal/client.json',
        'https://intranet/client.json',
        'https:///client.json',
        'https://client.example.com:bad/client.json',
        '', 'client.example.com/client.json',
    ])
    def test_unacceptable_urls_are_refused_before_any_lookup(self, url):
        resolver, transport = _resolver('93.184.216.34'), _transport()
        with pytest.raises(FetchError) as excinfo:
            safe_fetch.fetch_json(url, resolver=resolver, transport=transport)
        assert excinfo.value.transient is False
        assert resolver.calls == [] and transport.calls == []

    @pytest.mark.parametrize('addresses', [
        ['10.1.2.3'], ['127.0.0.1'], ['169.254.169.254'], ['168.63.129.16'], ['::1'], ['fd00::1'],
        ['::ffff:10.0.0.1'],
        ['93.184.216.34', '10.1.2.3'],   # one inside address among public ones refuses the name
        ['10.1.2.3', '93.184.216.34'],
    ])
    def test_a_name_that_resolves_inside_is_never_connected_to(self, addresses):
        transport = _transport()
        with pytest.raises(FetchError) as excinfo:
            safe_fetch.fetch_json(CLIENT_ID, resolver=_resolver(*addresses), transport=transport)
        assert excinfo.value.transient is False
        assert transport.calls == []

    def test_the_name_is_resolved_once_so_it_cannot_answer_differently_later(self):
        """DNS rebinding: public on the first lookup, inside on the second. There is no second lookup."""
        answers = [['93.184.216.34'], ['10.1.2.3']]
        lookups = []

        def resolver(host):
            lookups.append(host)
            return answers[len(lookups) - 1]
        transport = _transport()

        safe_fetch.fetch_json(CLIENT_ID, resolver=resolver, transport=transport)

        assert len(lookups) == 1
        assert [call[1] for call in transport.calls] == ['93.184.216.34']

    def test_resolution_failure_is_temporary(self):
        def resolver(host):
            raise socket.gaierror('no such host')
        with pytest.raises(FetchError) as excinfo:
            safe_fetch.fetch_json(CLIENT_ID, resolver=resolver, transport=_transport())
        assert excinfo.value.transient is True

        with pytest.raises(FetchError) as excinfo:
            safe_fetch.fetch_json(CLIENT_ID, resolver=_resolver(), transport=_transport())
        assert excinfo.value.transient is True

    @pytest.mark.parametrize('status', [301, 302, 303, 307, 308])
    def test_redirects_are_not_followed(self, status):
        transport = _transport(status=status, headers={'location': 'http://169.254.169.254/latest/meta-data/'})
        with pytest.raises(FetchError) as excinfo:
            safe_fetch.fetch_json(CLIENT_ID, resolver=_resolver('93.184.216.34'), transport=transport)
        assert excinfo.value.transient is False
        assert len(transport.calls) == 1

    @pytest.mark.parametrize('status,transient', [
        (400, False), (401, False), (403, False), (404, False), (410, False), (204, False), (206, False),
        (408, True), (429, True), (500, True), (502, True), (503, True),
    ])
    def test_other_statuses(self, status, transient):
        with pytest.raises(FetchError) as excinfo:
            safe_fetch.fetch_json(CLIENT_ID, resolver=_resolver('93.184.216.34'),
                                  transport=_transport(status=status))
        assert excinfo.value.transient is transient

    def test_an_oversized_document_is_refused(self):
        body = b'{"client_id": "' + b'a' * safe_fetch.MAX_RESPONSE_BYTES + b'"}'
        with pytest.raises(FetchError):
            safe_fetch.fetch_json(CLIENT_ID, resolver=_resolver('93.184.216.34'), transport=_transport(body=body))

    @pytest.mark.parametrize('content_type', ['text/html', 'text/plain', '', 'application/octet-stream',
                                              'text/html; charset=utf-8'])
    def test_only_json_is_accepted(self, content_type):
        transport = _transport(headers={'content-type': content_type})
        with pytest.raises(FetchError):
            safe_fetch.fetch_json(CLIENT_ID, resolver=_resolver('93.184.216.34'), transport=transport)

    @pytest.mark.parametrize('content_type', ['application/json', 'application/json; charset=utf-8',
                                              'Application/JSON', 'application/cimd+json'])
    def test_json_content_types(self, content_type):
        transport = _transport(headers={'content-type': content_type})
        assert safe_fetch.fetch_json(CLIENT_ID, resolver=_resolver('93.184.216.34'), transport=transport).document

    @pytest.mark.parametrize('body', [b'', b'<html>', b'{"a":', b'[1, 2]', b'"text"', b'null', b'7', b'\xff\xfe{}'])
    def test_the_body_must_be_a_json_object(self, body):
        with pytest.raises(FetchError):
            safe_fetch.fetch_json(CLIENT_ID, resolver=_resolver('93.184.216.34'), transport=_transport(body=body))

    def test_a_connection_failure_is_temporary_and_a_second_address_is_tried(self):
        attempts = []

        def transport(host, address, target, deadline):
            attempts.append(address)
            if address == '93.184.216.34':
                raise ConnectionRefusedError()
            return 200, {'content-type': 'application/json'}, json.dumps(_document()).encode()

        result = safe_fetch.fetch_json(CLIENT_ID, resolver=_resolver('93.184.216.34', '93.184.216.35'),
                                       transport=transport)
        assert result.document['client_name'] == 'Example Client'
        assert attempts == ['93.184.216.34', '93.184.216.35']

        with pytest.raises(FetchError) as excinfo:
            safe_fetch.fetch_json(CLIENT_ID, resolver=_resolver('93.184.216.34'),
                                  transport=_transport(raises=socket.timeout('slow')))
        assert excinfo.value.transient is True

    def test_at_most_two_addresses_are_tried(self):
        transport = _transport(raises=ConnectionRefusedError())
        with pytest.raises(FetchError):
            safe_fetch.fetch_json(CLIENT_ID, transport=transport,
                                  resolver=_resolver('93.184.216.1', '93.184.216.2', '93.184.216.3', '93.184.216.4'))
        assert len(transport.calls) == safe_fetch.MAX_ADDRESSES_TRIED

    def test_the_real_transport_connects_to_the_given_address_not_the_name(self, monkeypatch):
        """https_get must open its socket to the checked address and verify TLS for the name."""
        seen = {}

        class Stop(Exception):
            pass

        def fake_create_connection(address, timeout=None, **kwargs):
            seen['address'] = address
            seen['timeout'] = timeout
            raise Stop()

        monkeypatch.setattr(safe_fetch.socket, 'create_connection', fake_create_connection)
        with pytest.raises(Stop):
            safe_fetch.https_get('client.example.com', '93.184.216.34', '/client.json', deadline=10 ** 12)

        assert seen['address'] == ('93.184.216.34', 443)
        assert seen['timeout'] == safe_fetch.CONNECT_TIMEOUT_SECONDS

    def test_tls_is_verified_against_the_name(self):
        context = safe_fetch._tls_context()
        assert context.check_hostname is True
        assert context.verify_mode.name == 'CERT_REQUIRED'


class TestTheRealTransport:
    """https_get against a local server, with TLS and the connect address stood in for."""

    @pytest.fixture
    def server(self, monkeypatch):
        import http.server
        import threading

        state = {'body': json.dumps(_document()).encode(), 'delay': 0, 'requests': [], 'sni': []}

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def do_GET(self):
                state['requests'].append((self.path, dict(self.headers)))
                import time as _time
                _time.sleep(state['delay'])
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Cache-Control', 'max-age=300')
                self.send_header('Content-Length', str(len(state['body'])))
                self.send_header('Connection', 'close')
                self.end_headers()
                try:
                    self.wfile.write(state['body'])
                except OSError:
                    pass

            def log_message(self, *args):
                pass

        httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()

        real_create_connection = socket.create_connection
        state['connected_to'] = []

        def create_connection(address, timeout=None, **kwargs):
            state['connected_to'].append(address)
            return real_create_connection(('127.0.0.1', port), timeout=timeout)

        class PlainContext:
            def wrap_socket(self, sock, server_hostname=None):
                state['sni'].append(server_hostname)
                return sock

        monkeypatch.setattr(safe_fetch.socket, 'create_connection', create_connection)
        monkeypatch.setattr(safe_fetch, '_tls_context', lambda: PlainContext())
        yield state
        httpd.shutdown()
        httpd.server_close()

    def test_a_document_is_read_from_a_closing_connection(self, server):
        import time
        status, headers, body = safe_fetch.https_get(
            'client.example.com', '93.184.216.34', '/oauth/client.json', time.monotonic() + 5)

        assert status == 200
        assert headers['content-type'] == 'application/json'
        assert json.loads(body)['client_id'] == CLIENT_ID
        assert server['connected_to'] == [('93.184.216.34', 443)]
        assert server['sni'] == ['client.example.com']
        path, sent = server['requests'][0]
        assert path == '/oauth/client.json'
        assert sent['Host'] == 'client.example.com'
        assert sent['Accept'] == 'application/json'
        assert 'DecisionRecords' in sent['User-Agent']
        assert 'Cookie' not in sent and 'Authorization' not in sent

    def test_the_whole_fetch_through_the_real_transport(self, server):
        result = safe_fetch.fetch_json(CLIENT_ID, resolver=_resolver('93.184.216.34'))
        assert result.document['client_name'] == 'Example Client'
        assert client_metadata.cache_lifetime(result.headers) == timedelta(minutes=5)

    def test_reading_stops_just_past_the_size_limit(self, server):
        import time
        server['body'] = b'{"x": "' + b'a' * (safe_fetch.MAX_RESPONSE_BYTES * 4) + b'"}'

        _status, _headers, body = safe_fetch.https_get(
            'client.example.com', '93.184.216.34', '/big.json', time.monotonic() + 5)
        assert len(body) == safe_fetch.MAX_RESPONSE_BYTES + 1

        with pytest.raises(FetchError):
            safe_fetch.fetch_json(CLIENT_ID, resolver=_resolver('93.184.216.34'))

    def test_a_slow_server_is_given_up_on(self, server):
        import time
        server['delay'] = 1.5
        started = time.monotonic()
        with pytest.raises(OSError):
            safe_fetch.https_get('client.example.com', '93.184.216.34', '/slow.json', time.monotonic() + 0.3)
        assert time.monotonic() - started < 1.4

    def test_a_deadline_already_passed_sends_nothing(self, server):
        import time
        with pytest.raises(OSError):
            safe_fetch.https_get('client.example.com', '93.184.216.34', '/late.json', time.monotonic() - 1)
        assert server['requests'] == []


class TestOneDeadlineForTheWholeFetch:
    """
    A server that sends one byte just inside every socket timeout must not
    hold the caller: resolving, connecting, the TLS handshake, the response
    head and the body together get one deadline. Real TLS against a local
    server; only the certificate trust and the connect address are stood in for.
    """

    HOST = 'slow.example.org'

    @pytest.fixture
    def tls_server(self, monkeypatch, tmp_path):
        import ssl
        import threading
        from datetime import timezone as tz
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID

        key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, self.HOST)])
        now = datetime.now(tz.utc)
        certificate = (
            x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(self.HOST)]), critical=False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256())
        )
        cert_path, key_path = tmp_path / 'c.pem', tmp_path / 'k.pem'
        cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))

        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(5)
        port = listener.getsockname()[1]
        server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_context.load_cert_chain(str(cert_path), str(key_path))
        state = {'behaviour': None, 'stop': threading.Event()}

        def serve():
            while not state['stop'].is_set():
                try:
                    listener.settimeout(0.2)
                    connection, _ = listener.accept()
                except OSError:
                    continue
                threading.Thread(target=handle, args=(connection,), daemon=True).start()

        def handle(connection):
            try:
                if state['behaviour'] == 'no-handshake':
                    state['stop'].wait(20)
                    return
                tls = server_context.wrap_socket(connection, server_side=True)
                tls.recv(4096)
                state['behaviour'](tls)
            except OSError:
                pass
            finally:
                try:
                    connection.close()
                except OSError:
                    pass

        threading.Thread(target=serve, daemon=True).start()

        client_context = ssl.create_default_context(cafile=str(cert_path))
        real_create_connection = socket.create_connection
        monkeypatch.setattr(safe_fetch, '_tls_context', lambda: client_context)
        monkeypatch.setattr(safe_fetch.socket, 'create_connection',
                            lambda address, timeout=None, **kwargs: real_create_connection(
                                ('127.0.0.1', port), timeout=timeout))
        yield state
        state['stop'].set()
        listener.close()

    @staticmethod
    def _drip(data, pause=0.15):
        def behaviour(tls):
            import time
            for index in range(len(data)):
                tls.send(data[index:index + 1])
                time.sleep(pause)
        return behaviour

    def _timed_get(self, seconds=0.8):
        import time
        started = time.monotonic()
        with pytest.raises(OSError) as excinfo:
            safe_fetch.https_get(self.HOST, '93.184.216.34', '/client.json', started + seconds)
        return time.monotonic() - started, excinfo.value

    BODY = json.dumps({'client_id': CLIENT_ID}).encode()

    def test_a_dripped_status_line_is_cut_off_at_the_deadline(self, tls_server):
        """The reviewer's case: one byte every moment, each inside the socket timeout, for as long as it likes."""
        tls_server['behaviour'] = self._drip(b'HTTP/1.1 200 ' + b'A' * 60000)
        elapsed, error = self._timed_get()
        assert elapsed < 1.6, elapsed
        assert isinstance(error, socket.timeout)

    def test_dripped_headers_are_cut_off_at_the_deadline(self, tls_server):
        tls_server['behaviour'] = self._drip(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nX-Pad: '
                                             + b'a' * 60000)
        elapsed, _error = self._timed_get()
        assert elapsed < 1.6, elapsed

    def test_a_dripped_body_is_cut_off_at_the_deadline(self, tls_server):
        head = b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 5000\r\n\r\n'

        def behaviour(tls):
            tls.sendall(head)
            self._drip(b'{' + b' ' * 4999)(tls)
        tls_server['behaviour'] = behaviour
        elapsed, _error = self._timed_get()
        assert elapsed < 1.6, elapsed

    def test_a_stalled_tls_handshake_is_cut_off_at_the_deadline(self, tls_server):
        tls_server['behaviour'] = 'no-handshake'
        elapsed, _error = self._timed_get()
        assert elapsed < 1.6, elapsed

    def test_the_whole_fetch_reports_it_as_temporary(self, tls_server, monkeypatch):
        import time
        monkeypatch.setattr(safe_fetch, 'TOTAL_TIMEOUT_SECONDS', 0.8)
        tls_server['behaviour'] = self._drip(b'HTTP/1.1 200 ' + b'A' * 60000)
        started = time.monotonic()
        with pytest.raises(FetchError) as excinfo:
            safe_fetch.fetch_json(f'https://{self.HOST}/client.json', resolver=_resolver('93.184.216.34'))
        assert excinfo.value.transient is True
        # Not once per address either: the deadline is for the fetch, and there is one address here
        assert time.monotonic() - started < 1.6

    def test_a_slow_name_lookup_counts_against_the_same_deadline(self, monkeypatch):
        import time
        monkeypatch.setattr(safe_fetch, 'TOTAL_TIMEOUT_SECONDS', 0.3)
        transport = _transport()

        def slow_resolver(host):
            time.sleep(2)
            return ['93.184.216.34']

        started = time.monotonic()
        with pytest.raises(FetchError) as excinfo:
            safe_fetch.fetch_json(CLIENT_ID, resolver=slow_resolver, transport=transport)
        assert time.monotonic() - started < 1.0
        assert excinfo.value.transient is True
        assert transport.calls == []

    def test_an_oversized_head_is_refused(self, tls_server):
        def behaviour(tls):
            tls.sendall(b'HTTP/1.1 200 OK\r\nX-Pad: ' + b'a' * (safe_fetch.MAX_HEAD_BYTES + 100) + b'\r\n\r\n{}')
        tls_server['behaviour'] = behaviour
        import http.client
        import time
        with pytest.raises(http.client.HTTPException):
            safe_fetch.https_get(self.HOST, '93.184.216.34', '/client.json', time.monotonic() + 3)
        with pytest.raises(FetchError):
            safe_fetch.fetch_json(f'https://{self.HOST}/client.json', resolver=_resolver('93.184.216.34'))

    @pytest.mark.parametrize('framing', ['content-length', 'chunked', 'until-close'])
    def test_ordinary_responses_are_read_whichever_way_they_are_framed(self, tls_server, framing):
        import time
        body = self.BODY
        head = b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n'
        response = {
            'content-length': head + b'Content-Length: %d\r\n\r\n' % len(body) + body,
            'chunked': head + b'Transfer-Encoding: chunked\r\n\r\n%x\r\n' % len(body) + body + b'\r\n0\r\n\r\n',
            'until-close': head + b'Connection: close\r\n\r\n' + body,
        }[framing]
        tls_server['behaviour'] = lambda tls: tls.sendall(response)

        status, headers, received = safe_fetch.https_get(
            self.HOST, '93.184.216.34', '/client.json', time.monotonic() + 3)

        assert status == 200
        assert headers['content-type'] == 'application/json'
        assert json.loads(received) == {'client_id': CLIENT_ID}

    def test_a_server_that_keeps_the_connection_open_does_not_cost_the_whole_deadline(self, tls_server):
        """The response is complete; the caller does not wait for a close that never comes."""
        import time
        body = self.BODY

        def behaviour(tls):
            tls.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n%s'
                        % (len(body), body))
            time.sleep(3)
        tls_server['behaviour'] = behaviour

        started = time.monotonic()
        status, _headers, received = safe_fetch.https_get(
            self.HOST, '93.184.216.34', '/client.json', started + 3)
        assert status == 200 and json.loads(received) == {'client_id': CLIENT_ID}
        assert time.monotonic() - started < 1.5

    def test_the_certificate_must_be_for_the_name(self, tls_server):
        import ssl
        import time
        tls_server['behaviour'] = lambda tls: None
        with pytest.raises(ssl.SSLCertVerificationError):
            safe_fetch.https_get('other.example.org', '93.184.216.34', '/client.json', time.monotonic() + 3)


# ============================================================================
# THE CLIENT_ID URL
# ============================================================================

class TestClientIdUrl:

    @pytest.mark.parametrize('client_id', [
        'https://claude.ai/oauth/claude-code-client-metadata',
        'https://claude.ai/oauth/mcp-oauth-client-metadata',
        'https://chatgpt.com/oauth/client.json',
        'https://chatgpt.com/oauth/abc123/client.json',
        'https://client.example.com:443/client.json',
        'https://client.example.com/a',
    ])
    def test_accepted(self, client_id):
        assert client_metadata.check_client_id_url(client_id) == client_id

    @pytest.mark.parametrize('client_id', [
        None, '', 7, 'client-123', 'dcr_abc',
        'http://client.example.com/client.json',
        'HTTPS://client.example.com/client.json',
        'https://client.example.com',                      # no path
        'https://client.example.com/',
        'https://client.example.com//',
        'https://client.example.com/client.json#frag',
        'https://client.example.com/client.json?v=2',
        'https://client.example.com/client.json?',
        'https://user@client.example.com/client.json',
        'https://user:pw@client.example.com/client.json',
        'https://client.example.com/../client.json',
        'https://client.example.com/a/./client.json',
        'https://client.example.com/a/../client.json',
        'https://client.example.com/a/%2e%2e/client.json',
        'https://client.example.com/a%2Fclient.json',
        'https://client.example.com:8443/client.json',
        'https://Client.Example.com/client.json',
        'https://127.0.0.1/client.json',
        'https://[::1]/client.json',
        'https://localhost/client.json',
        'https://server.internal/client.json',
        'https://169.254.169.254/client.json',
        'https://client.example.com/client json',
        'https://client.example.com/"><script>alert(1)</script>',
        "https://client.example.com/client'.json",
        'https://client.example.com/client<.json',
        'https://client.example.com/{client}.json',
        'https://client.example.com/client|.json',
        'https://client.example.com/client`.json',
        'https://client.example.com/client.json\n',
        'https://client.example.com\\@evil.test/client.json',
        'https://clïent.example.com/client.json',
        'https://client.example.com/' + 'a' * 500,
    ])
    def test_refused(self, client_id):
        with pytest.raises(ClientMetadataError):
            client_metadata.check_client_id_url(client_id)

    def test_host_is_the_identity(self):
        assert client_metadata.client_host('https://claude.ai/oauth/mcp-oauth-client-metadata') == 'claude.ai'


# ============================================================================
# THE DOCUMENT
# ============================================================================

class TestDocumentValidation:

    def test_a_minimal_document(self):
        client = client_metadata.validate_document(CLIENT_ID, _document())
        assert client.client_id == CLIENT_ID
        assert client.client_name == 'Example Client'
        assert client.client_uri == 'https://client.example.com'
        assert client.redirect_uris == ['https://client.example.com/callback']

    @pytest.mark.parametrize('document', [CLAUDE_CODE, CLAUDE, CHATGPT])
    def test_the_documents_real_clients_publish_are_accepted(self, document):
        client = client_metadata.validate_document(document['client_id'], document)
        assert client.client_name == document['client_name']
        assert client.redirect_uris == document['redirect_uris']

    @pytest.mark.parametrize('document', [
        None, [], 'text', 7,
        _document(client_id='https://other.example.com/oauth/client.json'),
        _document(client_id=CLIENT_ID + '/'),
        _document(client_id=CLIENT_ID.upper()),
        _document(client_id=...),
        _document(client_name=...),
        _document(client_name=''),
        _document(client_name='   '),
        _document(client_name=42),
        _document(client_name='‮​'),
        _document(redirect_uris=...),
        _document(redirect_uris=[]),
        _document(redirect_uris='https://client.example.com/callback'),
        _document(redirect_uris=[1, 2]),
        _document(redirect_uris=['cursor://callback', 'http://client.example.com/callback']),
        _document(redirect_uris=['https://client.example.com/cb%d' % n for n in range(21)]),
        _document(client_secret='s3cret'),
        _document(client_secret_expires_at=0),
        _document(token_endpoint_auth_method='client_secret_basic'),
        _document(token_endpoint_auth_method='client_secret_post'),
        _document(token_endpoint_auth_method='client_secret_jwt'),
        _document(token_endpoint_auth_method='private_key_jwt'),
        _document(token_endpoint_auth_method='tls_client_auth'),
        _document(token_endpoint_auth_method=['none']),
        _document(token_endpoint_auth_method='none', token_endpoint_auth_methods_supported=['client_secret_post']),
        _document(token_endpoint_auth_methods_supported='none'),
        _document(grant_types=['client_credentials']),
        _document(grant_types=['refresh_token']),
        _document(grant_types='authorization_code'),
        _document(response_types=['token']),
    ])
    def test_refused(self, document):
        with pytest.raises(ClientMetadataError) as excinfo:
            client_metadata.validate_document(CLIENT_ID, document)
        assert excinfo.value.transient is False

    @pytest.mark.parametrize('document', [
        _document(token_endpoint_auth_method='private_key_jwt\n2026-11-25 [SECURITY:AUTH] forged line'),
        _document(token_endpoint_auth_method='tls_client_auth forged line'),
        _document(grant_types=['implicit forged line']),
        _document(response_types=['token forged line']),
    ])
    def test_refusals_do_not_repeat_what_the_document_said(self, document):
        """The message goes to the security log and to the consent page; the document is whatever its author wrote."""
        with pytest.raises(ClientMetadataError) as excinfo:
            client_metadata.validate_document(CLIENT_ID, document)
        message = str(excinfo.value)
        assert 'forged line' not in message and '\n' not in message and '\r' not in message

    def test_a_missing_auth_method_is_taken_as_a_public_client(self):
        assert client_metadata.validate_document(CLIENT_ID, _document(token_endpoint_auth_method=...))

    def test_unusable_redirect_uris_are_left_out_and_repeats_removed(self):
        client = client_metadata.validate_document(CLIENT_ID, _document(redirect_uris=[
            'cursor://callback', 'https://client.example.com/callback', 'http://insecure.example.com/cb',
            'http://localhost/callback', 'https://client.example.com/callback', 'https://x.example/cb#frag',
        ]))
        assert client.redirect_uris == ['https://client.example.com/callback', 'http://localhost/callback']

    @pytest.mark.parametrize('claimed,shown', [
        ('  Example \n Client\t ', 'Example Client'),
        ('Decision Records‮ (official)', 'Decision Records (official)'),   # direction override removed
        ('Ex​ample⁠ Cl­ient', 'Example Client'),                 # zero-width and soft hyphen
        ('Line one Line two', 'Line one Line two'),
        ('Tab\x00Null\x1b[31m', 'TabNull[31m'),
        ('<script>alert(1)</script>', '<script>alert(1)</script>'),              # kept as text; never rendered as markup
        ('ｆｕｌｌｗｉｄｔｈ', 'fullwidth'),
        ('x' * 500, 'x' * 60),
    ])
    def test_the_claimed_name_is_cleaned_for_display(self, claimed, shown):
        client = client_metadata.validate_document(CLIENT_ID, _document(client_name=claimed))
        assert client.client_name == shown

    @pytest.mark.parametrize('client_uri', [
        'http://client.example.com', 'javascript:alert(1)', 'https://client.example.com/\n', 7, None,
        'https://' + 'a' * 600,
    ])
    def test_an_unusable_client_uri_is_dropped_not_fatal(self, client_uri):
        assert client_metadata.validate_document(CLIENT_ID, _document(client_uri=client_uri)).client_uri is None

    # 'default', 'min' and 'max' stand for the module's bounds, so that the table
    # can be built when the Enterprise modules are absent and the tests are skipped
    @pytest.mark.parametrize('header,expected', [
        (None, 'default'),
        ('', 'default'),
        ('public', 'default'),
        ('max-age=3600', timedelta(hours=1)),
        ('public, max-age=7200', timedelta(hours=2)),
        ('Max-Age=600', timedelta(minutes=10)),
        ('max-age=1', 'min'),
        ('max-age=0', 'min'),
        ('max-age=31536000', 'max'),
        ('no-store', 'min'),
        ('no-cache, max-age=86400', 'min'),
        ('s-maxage=99999', 'default'),
        ('max-age=abc', 'default'),
    ])
    def test_cache_lifetime(self, header, expected):
        bounds = {'default': client_metadata.DEFAULT_CACHE, 'min': client_metadata.MIN_CACHE,
                  'max': client_metadata.MAX_CACHE}
        headers = {} if header is None else {'cache-control': header}
        assert client_metadata.cache_lifetime(headers) == bounds.get(expected, expected)

    def test_cache_bounds(self):
        assert client_metadata.MIN_CACHE == timedelta(minutes=5)
        assert client_metadata.DEFAULT_CACHE == timedelta(hours=1)
        assert client_metadata.MAX_CACHE == timedelta(hours=24)


# ============================================================================
# RESOLVING AND REMEMBERING A CLIENT
# ============================================================================

def _fetch(document=None, headers=None, error=None):
    calls = []

    def fetch(url):
        calls.append(url)
        if error is not None:
            raise error
        return FetchResult(document if document is not None else _document(), headers or {})
    fetch.calls = calls
    return fetch


class TestResolveClient:

    def test_first_sight_fetches_validates_and_stores(self, app):
        fetch = _fetch(headers={'cache-control': 'max-age=1800'})

        client = client_metadata.resolve_client(CLIENT_ID, now=NOW, fetch=fetch)

        assert fetch.calls == [CLIENT_ID]
        stored = OAuthClient.query.one()
        assert stored.id == client.id
        assert stored.client_id == CLIENT_ID and stored.kind == 'cimd'
        assert stored.client_name == 'Example Client'
        assert stored.redirect_uris == ['https://client.example.com/callback']
        assert stored.metadata_fetched_at == NOW
        assert stored.metadata_expires_at == NOW + timedelta(minutes=30)

    def test_a_fresh_copy_is_used_without_fetching(self, app):
        client_metadata.resolve_client(CLIENT_ID, now=NOW, fetch=_fetch())
        fetch = _fetch()

        client_metadata.resolve_client(CLIENT_ID, now=NOW + timedelta(minutes=59), fetch=fetch)

        assert fetch.calls == []

    def test_an_expired_copy_is_fetched_again_and_updated(self, app):
        client_metadata.resolve_client(CLIENT_ID, now=NOW, fetch=_fetch())
        changed = _document(client_name='Renamed Client',
                            redirect_uris=['https://client.example.com/new-callback'])

        client = client_metadata.resolve_client(CLIENT_ID, now=NOW + timedelta(hours=2), fetch=_fetch(changed))

        assert OAuthClient.query.count() == 1
        assert client.client_name == 'Renamed Client'
        assert client.redirect_uris == ['https://client.example.com/new-callback']
        assert client.metadata_fetched_at == NOW + timedelta(hours=2)

    def test_an_unacceptable_client_id_is_never_fetched(self, app):
        fetch = _fetch()
        for client_id in ('http://client.example.com/client.json', 'https://10.1.2.3/client.json',
                          'https://client.example.com/client.json?x=1', 'client-123'):
            with pytest.raises(ClientMetadataError):
                client_metadata.resolve_client(client_id, now=NOW, fetch=fetch)
        assert fetch.calls == []
        assert OAuthClient.query.count() == 0

    def test_a_failure_is_not_stored_and_is_tried_again_after_a_minute(self, app, monkeypatch):
        moment = {'now': 50.0}
        monkeypatch.setattr(client_metadata, '_monotonic', lambda: moment['now'])
        failing = _fetch(error=FetchError('The server answered 404'))
        with pytest.raises(ClientMetadataError) as first:
            client_metadata.resolve_client(CLIENT_ID, now=NOW, fetch=failing)
        # Within the minute the same answer is given without fetching (second review, F3)
        moment['now'] += 59.9
        with pytest.raises(ClientMetadataError) as second:
            client_metadata.resolve_client(CLIENT_ID, now=NOW, fetch=failing)
        assert len(failing.calls) == 1
        assert str(second.value) == str(first.value) and second.value.transient is first.value.transient
        assert OAuthClient.query.count() == 0

        moment['now'] += 0.2
        with pytest.raises(ClientMetadataError):
            client_metadata.resolve_client(CLIENT_ID, now=NOW, fetch=failing)
        assert len(failing.calls) == 2

        moment['now'] += 61
        with pytest.raises(ClientMetadataError):
            client_metadata.resolve_client(CLIENT_ID, now=NOW, fetch=_fetch(_document(client_name='')))
        assert OAuthClient.query.count() == 0

    def test_a_success_ends_the_memory_of_a_failure(self, app, monkeypatch):
        moment = {'now': 50.0}
        monkeypatch.setattr(client_metadata, '_monotonic', lambda: moment['now'])
        with pytest.raises(ClientMetadataError):
            client_metadata.resolve_client(CLIENT_ID, now=NOW, fetch=_fetch(error=FetchError('timeout', transient=True)))
        moment['now'] += 61
        client_metadata.resolve_client(CLIENT_ID, now=NOW, fetch=_fetch())
        assert CLIENT_ID not in client_metadata._failed_fetches

    def test_a_transient_failure_is_remembered_as_transient(self, app):
        fetch = _fetch(error=FetchError('timeout', transient=True))
        for _ in range(3):
            with pytest.raises(ClientMetadataError) as excinfo:
                client_metadata.resolve_client(CLIENT_ID, now=NOW, fetch=fetch)
            assert excinfo.value.transient is True
            assert client_metadata.as_oauth_error(excinfo.value).status == 503
        assert len(fetch.calls) == 1

    def test_at_most_two_fetches_are_in_flight_and_a_third_is_refused_at_once(self, app):
        """
        Second review, F3. Three fetches "at the same time" without threads:
        the first fetch asks for a second application while it is running,
        and that one for a third.
        """
        ids = [f'https://client.example.com/app-{index}.json' for index in range(3)]
        seen = []
        outcome = {}

        def fetch(url):
            seen.append(url)
            depth = ids.index(url)
            if depth < 2:
                try:
                    client_metadata.resolve_client(ids[depth + 1], now=NOW, fetch=fetch)
                except ClientMetadataError as exc:
                    outcome[ids[depth + 1]] = exc
            return FetchResult(_document(client_id=url), {})

        client_metadata.resolve_client(ids[0], now=NOW, fetch=fetch)

        assert seen == ids[:2]                                   # the third was never fetched
        refused = outcome[ids[2]]
        assert refused.transient is True and client_metadata.as_oauth_error(refused).status == 503
        assert ids[1] not in outcome                             # the second had a place
        # Being refused a place is not remembered: with the places free again it is fetched
        client_metadata.resolve_client(ids[2], now=NOW, fetch=fetch)
        assert seen == ids
        assert OAuthClient.query.count() == 3

    def test_a_place_is_given_back_however_the_fetch_ends(self, app):
        def explode(url):
            raise RuntimeError('unexpected')
        for index in range(3):
            with pytest.raises(RuntimeError):
                client_metadata.resolve_client(f'https://client.example.com/x-{index}.json', now=NOW, fetch=explode)
        for index in range(3):
            with pytest.raises(ClientMetadataError):
                client_metadata.resolve_client(f'https://client.example.com/y-{index}.json', now=NOW,
                                               fetch=_fetch(error=FetchError('timeout', transient=True)))
        client_metadata.resolve_client(CLIENT_ID, now=NOW, fetch=_fetch())
        assert OAuthClient.query.count() == 1

    def test_the_memory_of_failures_is_bounded(self, app, monkeypatch):
        monkeypatch.setattr(client_metadata, 'FAILED_FETCH_MEMORY_SIZE', 5)
        failing = _fetch(error=FetchError('The server answered 404'))
        ids = [f'https://client.example.com/z-{index}.json' for index in range(12)]
        for client_id in ids:
            with pytest.raises(ClientMetadataError):
                client_metadata.resolve_client(client_id, now=NOW, fetch=failing)
        assert list(client_metadata._failed_fetches) == ids[-5:]
        assert client_metadata.FAILED_FETCH_MEMORY_SIZE == 5 and client_metadata.FAILED_FETCH_MEMORY == timedelta(seconds=60)

    def test_a_document_that_became_invalid_ends_the_stored_copy(self, app):
        client_metadata.resolve_client(CLIENT_ID, now=NOW, fetch=_fetch())
        later = NOW + timedelta(hours=2)

        with pytest.raises(ClientMetadataError) as excinfo:
            client_metadata.resolve_client(CLIENT_ID, now=later, fetch=_fetch(_document(client_secret='x')))
        assert excinfo.value.transient is False
        # ... and so does a definite "gone"
        with pytest.raises(ClientMetadataError):
            client_metadata.resolve_client(CLIENT_ID, now=later,
                                           fetch=_fetch(error=FetchError('The server answered 404')))
        # The stored copy is not refreshed by either
        assert OAuthClient.query.one().metadata_fetched_at == NOW

    def test_an_unreachable_document_falls_back_to_a_recent_copy(self, app):
        client_metadata.resolve_client(CLIENT_ID, now=NOW, fetch=_fetch())
        down = _fetch(error=FetchError('The server answered 503', transient=True))
        later = NOW + timedelta(days=3)

        client = client_metadata.resolve_client(CLIENT_ID, now=later, fetch=down)

        assert client.client_name == 'Example Client'
        assert client.metadata_fetched_at == NOW
        # It is not asked again on every request while it is down
        client_metadata.resolve_client(CLIENT_ID, now=later + timedelta(minutes=1), fetch=down)
        assert len(down.calls) == 1
        client_metadata.resolve_client(CLIENT_ID, now=later + timedelta(minutes=6), fetch=down)
        assert len(down.calls) == 2

    def test_the_fallback_ends_after_a_week(self, app):
        client_metadata.resolve_client(CLIENT_ID, now=NOW, fetch=_fetch())
        down = _fetch(error=FetchError('timeout', transient=True))

        with pytest.raises(ClientMetadataError) as excinfo:
            client_metadata.resolve_client(CLIENT_ID, now=NOW + client_metadata.STALE_IF_UNREACHABLE, fetch=down)
        assert excinfo.value.transient is True
        assert client_metadata.as_oauth_error(excinfo.value).status == 503

    def test_an_unreachable_document_never_seen_before_is_refused(self, app):
        with pytest.raises(ClientMetadataError) as excinfo:
            client_metadata.resolve_client(CLIENT_ID, now=NOW,
                                           fetch=_fetch(error=FetchError('timeout', transient=True)))
        assert excinfo.value.transient is True
        assert OAuthClient.query.count() == 0

    def test_a_blocked_client_is_refused_without_fetching(self, app):
        client = client_metadata.resolve_client(CLIENT_ID, now=NOW, fetch=_fetch())
        client.disabled_at = NOW
        client.disabled_reason = 'pretends to be us'
        db.session.commit()
        fetch = _fetch()

        for moment in (NOW + timedelta(minutes=1), NOW + timedelta(days=30)):
            with pytest.raises(ClientMetadataError):
                client_metadata.resolve_client(CLIENT_ID, now=moment, fetch=fetch)
        assert fetch.calls == []

    def test_errors_become_invalid_client(self, app):
        with pytest.raises(ClientMetadataError) as excinfo:
            client_metadata.resolve_client('client-123', now=NOW, fetch=_fetch())
        error = client_metadata.as_oauth_error(excinfo.value)
        assert error.error == 'invalid_client' and error.status == 400

    def test_the_default_fetch_is_the_safe_one(self, app, monkeypatch):
        """Without a fetcher passed in, the module's fetch_json is used, and that is safe_fetch's."""
        assert client_metadata.fetch_json is safe_fetch.fetch_json
        calls = []

        def recording(url):
            calls.append(url)
            return FetchResult(_document(), {})
        monkeypatch.setattr(client_metadata, 'fetch_json', recording)

        client_metadata.resolve_client(CLIENT_ID, now=NOW)
        assert calls == [CLIENT_ID]
