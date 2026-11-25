"""
The visitor's address, and the rate limiter's bucket.

The limiter used to key on the connection's peer. Behind a reverse proxy that
is the proxy for every visitor, so all visitors shared one bucket of 200
requests a minute and anyone could use it up for everybody. Login history and
the audit log took the address from a `CF-Connecting-IP` header without
checking who sent it.

`client_address.get_client_address()` is now the one answer. These tests pin:
  * the default (no TRUSTED_PROXIES): no header is believed;
  * behind named proxies the address they report is used, read from the right;
  * a header from a peer that is not a trusted proxy changes nothing;
  * two visitors behind one proxy do not share a bucket, in a small app and in
    the real app with the limiter switched on;
  * the Enterprise wiring (the hosted service's proxy chain).
"""
import json
import os
import subprocess
import sys

import pytest
from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import client_address
from client_address import get_client_address, rate_limit_key

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VISITOR = '198.51.100.7'
OTHER_VISITOR = '198.51.100.8'
LOCAL_PROXY = '172.17.0.1'
OUTER_PROXY = '203.0.113.10'       # stands for a CDN edge address
SPOOFED = '192.0.2.99'


@pytest.fixture
def trusted():
    """Set the trusted proxies for one test; nothing trusted to begin with.

    Importing the Enterprise app adds networks of its own to the module, so
    both lists are saved and put back.
    """
    saved = (client_address._env_networks, client_address._extra_networks)
    client_address._env_networks = ()
    client_address._extra_networks = ()

    def set_trusted(value):
        client_address.load_trusted_proxies(value)

    yield set_trusted
    client_address._env_networks, client_address._extra_networks = saved


flask_app = Flask(__name__)


def address(peer, headers=None, key=False):
    with flask_app.test_request_context('/', environ_base={'REMOTE_ADDR': peer}, headers=headers or {}):
        return rate_limit_key() if key else get_client_address()


class TestDefaultTrustsNothing:
    """Community default: TRUSTED_PROXIES is unset."""

    def test_the_address_is_the_peer(self, trusted):
        assert address(VISITOR) == VISITOR

    @pytest.mark.parametrize('header', ['X-Forwarded-For', 'X-Real-IP', 'CF-Connecting-IP', 'Forwarded', 'True-Client-IP'])
    def test_no_header_is_believed(self, trusted, header):
        value = f'for={SPOOFED}' if header == 'Forwarded' else SPOOFED
        assert address(VISITOR, {header: value}) == VISITOR

    def test_a_private_or_loopback_peer_is_not_trusted_by_default(self, trusted):
        for peer in ('127.0.0.1', LOCAL_PROXY, '10.0.0.5', '::1'):
            assert address(peer, {'X-Forwarded-For': SPOOFED}) == peer

    def test_unset_and_empty_setting_trust_nothing(self, trusted, monkeypatch):
        monkeypatch.delenv('TRUSTED_PROXIES', raising=False)
        assert client_address.load_trusted_proxies() == ()
        monkeypatch.setenv('TRUSTED_PROXIES', ' , ')
        assert client_address.load_trusted_proxies() == ()

    def test_outside_a_request_there_is_no_address(self, trusted):
        assert get_client_address() is None


class TestBehindTrustedProxies:

    def test_one_proxy_reports_the_visitor(self, trusted):
        trusted(LOCAL_PROXY)
        assert address(LOCAL_PROXY, {'X-Forwarded-For': VISITOR}) == VISITOR

    def test_what_the_visitor_sent_is_to_the_left_and_ignored(self, trusted):
        trusted(LOCAL_PROXY)
        assert address(LOCAL_PROXY, {'X-Forwarded-For': f'{SPOOFED}, {VISITOR}'}) == VISITOR

    def test_two_proxies_are_both_skipped(self, trusted):
        trusted(f'{LOCAL_PROXY}, 203.0.113.0/24')
        chain = f'{SPOOFED}, {VISITOR}, {OUTER_PROXY}'
        assert address(LOCAL_PROXY, {'X-Forwarded-For': chain}) == VISITOR

    def test_a_request_that_skipped_the_outer_proxy_is_not_believed(self, trusted):
        """Someone reaches the inner proxy directly and claims to be a visitor."""
        trusted(f'{LOCAL_PROXY}, 203.0.113.0/24')
        chain = f'{VISITOR}, {SPOOFED}'      # SPOOFED connected to the inner proxy itself
        assert address(LOCAL_PROXY, {'X-Forwarded-For': chain}) == SPOOFED

    def test_other_headers_are_never_read(self, trusted):
        trusted(LOCAL_PROXY)
        headers = {'X-Forwarded-For': VISITOR, 'CF-Connecting-IP': SPOOFED, 'X-Real-IP': SPOOFED}
        assert address(LOCAL_PROXY, headers) == VISITOR

    def test_trusted_proxy_without_the_header_is_its_own_address(self, trusted):
        """A health check made from the proxy host itself."""
        trusted(LOCAL_PROXY)
        assert address(LOCAL_PROXY) == LOCAL_PROXY

    def test_a_chain_of_trusted_proxies_only_gives_the_outermost(self, trusted):
        trusted(f'{LOCAL_PROXY}, 203.0.113.0/24')
        assert address(LOCAL_PROXY, {'X-Forwarded-For': OUTER_PROXY}) == OUTER_PROXY

    def test_repeated_header_lines_are_one_chain(self, trusted):
        trusted(LOCAL_PROXY)
        with flask_app.test_request_context(
            '/', environ_base={'REMOTE_ADDR': LOCAL_PROXY},
            headers=[('X-Forwarded-For', SPOOFED), ('X-Forwarded-For', VISITOR)],
        ):
            assert get_client_address() == VISITOR

    def test_something_that_is_not_an_address_ends_the_chain(self, trusted):
        trusted(f'{LOCAL_PROXY}, 203.0.113.0/24')
        chain = f'{VISITOR}, <script>, {OUTER_PROXY}'
        assert address(LOCAL_PROXY, {'X-Forwarded-For': chain}) == OUTER_PROXY
        assert address(LOCAL_PROXY, {'X-Forwarded-For': 'unknown'}) == LOCAL_PROXY
        assert address(LOCAL_PROXY, {'X-Forwarded-For': ' , '}) == LOCAL_PROXY

    def test_a_very_long_header_is_cut_from_the_left(self, trusted):
        trusted(LOCAL_PROXY)
        chain = ', '.join([SPOOFED] * 500 + [VISITOR])
        assert address(LOCAL_PROXY, {'X-Forwarded-For': chain}) == VISITOR

    def test_ipv6_visitor_and_ipv6_proxy(self, trusted):
        trusted('2001:db8:ffff::/48, ::1')
        chain = '2001:db8:1::5, 2001:db8:ffff::1'
        assert address('::1', {'X-Forwarded-For': chain}) == '2001:db8:1::5'

    def test_ipv4_mapped_ipv6_is_the_ipv4_address(self, trusted):
        trusted(LOCAL_PROXY)
        assert address(f'::ffff:{LOCAL_PROXY}', {'X-Forwarded-For': f'::ffff:{VISITOR}'}) == VISITOR

    def test_a_peer_without_an_address_is_returned_as_it_is(self, trusted):
        trusted(LOCAL_PROXY)
        assert address('', {'X-Forwarded-For': SPOOFED}) in ('', None)


class TestSpoofingFromAnUntrustedPeer:

    def test_header_from_a_peer_that_is_not_a_proxy_is_ignored(self, trusted):
        trusted(LOCAL_PROXY)
        assert address(VISITOR, {'X-Forwarded-For': SPOOFED}) == VISITOR
        assert address(VISITOR, {'X-Forwarded-For': f'{SPOOFED}, {LOCAL_PROXY}'}) == VISITOR

    def test_claiming_to_be_a_trusted_proxy_in_the_header_does_not_help(self, trusted):
        trusted(f'{LOCAL_PROXY}, 203.0.113.0/24')
        # The visitor writes a chain that ends in a trusted address; the real
        # proxy still appends the visitor's own address after it.
        chain = f'{SPOOFED}, {OUTER_PROXY}, {VISITOR}'
        assert address(LOCAL_PROXY, {'X-Forwarded-For': chain}) == VISITOR


class TestSetting:

    def test_addresses_and_networks_are_accepted(self, trusted):
        trusted('172.17.0.1, 10.0.0.0/8 ,2001:db8::/32,')
        assert [str(n) for n in client_address.trusted_proxy_networks()] == [
            '172.17.0.1/32', '10.0.0.0/8', '2001:db8::/32',
        ]

    def test_a_bad_entry_is_ignored_and_reported(self, trusted, caplog):
        with caplog.at_level('ERROR', logger='client_address'):
            trusted('nginx, 172.17.0.1, *, 0.0.0.0/33')
        assert [str(n) for n in client_address.trusted_proxy_networks()] == ['172.17.0.1/32']
        assert caplog.text.count('TRUSTED_PROXIES') == 3

    def test_networks_added_by_code_join_the_operators(self, trusted):
        trusted(LOCAL_PROXY)
        client_address.trust_proxy_networks(['203.0.113.0/24', '203.0.113.0/24'])
        client_address.trust_proxy_networks(['203.0.113.0/24'])
        assert len(client_address.trusted_proxy_networks()) == 2
        chain = f'{VISITOR}, {OUTER_PROXY}'
        assert address(LOCAL_PROXY, {'X-Forwarded-For': chain}) == VISITOR

    def test_networks_added_by_code_do_not_make_the_peer_trusted(self, trusted):
        """Naming a far proxy does not make a header from anyone else believed."""
        client_address.trust_proxy_networks(['203.0.113.0/24'])
        assert address(LOCAL_PROXY, {'X-Forwarded-For': f'{VISITOR}, {OUTER_PROXY}'}) == LOCAL_PROXY


class TestRateLimitKey:

    def test_ipv4_key_is_the_address(self, trusted):
        assert address(VISITOR, key=True) == VISITOR

    def test_ipv6_key_is_the_64_block(self, trusted):
        assert address('2001:db8:1:2:aaaa::1', key=True) == '2001:db8:1:2::/64'
        assert address('2001:db8:1:2:bbbb::9', key=True) == '2001:db8:1:2::/64'
        assert address('2001:db8:1:3::1', key=True) == '2001:db8:1:3::/64'

    def test_key_follows_the_trusted_chain(self, trusted):
        trusted(LOCAL_PROXY)
        assert address(LOCAL_PROXY, {'X-Forwarded-For': VISITOR}, key=True) == VISITOR
        assert address(VISITOR, {'X-Forwarded-For': SPOOFED}, key=True) == VISITOR

    def test_key_is_never_empty(self, trusted):
        assert address('', key=True)


class TestBucketsInASmallApp:
    """flask-limiter with the key function, as app.py sets it up."""

    @pytest.fixture
    def limited_client(self, trusted):
        pytest.importorskip('flask_limiter')
        from flask_limiter import Limiter

        small = Flask('limited')
        Limiter(key_func=rate_limit_key, app=small, default_limits=['3 per minute'], storage_uri='memory://')

        @small.route('/')
        def home():
            return 'ok'

        client = small.test_client()

        def get(peer, forwarded=None):
            headers = {'X-Forwarded-For': forwarded} if forwarded else {}
            return client.get('/', environ_base={'REMOTE_ADDR': peer}, headers=headers).status_code

        return trusted, get

    def test_two_visitors_behind_one_proxy_do_not_share_a_bucket(self, limited_client):
        trusted, get = limited_client
        trusted(LOCAL_PROXY)

        assert [get(LOCAL_PROXY, VISITOR) for _ in range(4)] == [200, 200, 200, 429]
        assert get(LOCAL_PROXY, OTHER_VISITOR) == 200

    def test_a_visitor_cannot_get_a_new_bucket_by_sending_a_header(self, limited_client):
        trusted, get = limited_client
        trusted(LOCAL_PROXY)

        statuses = [get(LOCAL_PROXY, f'192.0.2.{n}, {VISITOR}') for n in range(4)]
        assert statuses == [200, 200, 200, 429]

    def test_without_trusted_proxies_a_header_does_not_choose_the_bucket(self, limited_client):
        _trusted, get = limited_client

        statuses = [get(VISITOR, f'192.0.2.{n}') for n in range(4)]
        assert statuses == [200, 200, 200, 429]
        assert get(OTHER_VISITOR) == 200

    def test_a_visitor_cannot_use_up_someone_elses_bucket(self, limited_client):
        """Not behind the proxy, claiming to be VISITOR."""
        trusted, get = limited_client
        trusted(LOCAL_PROXY)

        assert [get(SPOOFED, VISITOR) for _ in range(4)] == [200, 200, 200, 429]
        assert get(LOCAL_PROXY, VISITOR) == 200


def run_real_app(script, **extra_env):
    """Run `script` against the real app with the limiter on, in a new process."""
    pytest.importorskip('flask_limiter')
    env = {
        key: value for key, value in os.environ.items()
        if key not in ('FLASK_ENV', 'TESTING', 'TEST_DATABASE_URL', 'REDIS_URL', 'PYTHONPATH', 'TRUSTED_PROXIES')
    }
    env.update({
        'DECISION_RECORDS_EDITION': 'community',
        'DATABASE_URL': 'sqlite:///:memory:',
        'SECRET_KEY': 'client-address-subprocess-test',
        'PYTHONDONTWRITEBYTECODE': '1',
    })
    env.update(extra_env)
    completed = subprocess.run(
        [sys.executable, '-c', script], cwd=REPO_ROOT, env=env,
        capture_output=True, text=True, timeout=120,
    )
    lines = [line for line in completed.stdout.splitlines() if line.startswith('RESULT ')]
    assert lines, completed.stdout[-2000:] + completed.stderr[-2000:]
    return json.loads(lines[-1][len('RESULT '):])


REAL_APP_SCRIPT = (
    "import json\n"
    "import app as app_module\n"
    "from models import db, LoginHistory\n"
    "import client_address\n"
    "client = app_module.app.test_client()\n"
    "payload = {'username': 'nobody', 'password': 'wrong-password'}\n"
    "def attempt(forwarded):\n"
    "    return client.post('/auth/local', json=payload, headers={'X-Forwarded-For': forwarded,\n"
    "                       'CF-Connecting-IP': '192.0.2.99'}).status_code\n"
    "first = [attempt('198.51.100.7') for _ in range(6)]\n"
    "second = [attempt('198.51.100.8') for _ in range(2)]\n"
    "with app_module.app.app_context():\n"
    "    recorded = sorted({row.ip_address for row in LoginHistory.query.all()})\n"
    "version = client.get('/api/version', headers={'X-Forwarded-For': '198.51.100.9'})\n"
    "print('RESULT ' + json.dumps({'first': first, 'second': second, 'recorded': recorded,\n"
    "      'key_func': app_module.limiter._key_func is client_address.rate_limit_key,\n"
    "      'remaining': version.headers.get('X-RateLimit-Remaining')}))\n"
)


class TestTheRealApp:
    """app.py with rate limiting on, which the rest of the suite switches off."""

    def test_visitors_behind_a_trusted_proxy_have_their_own_buckets(self):
        # The test client connects from 127.0.0.1, which plays the proxy.
        result = run_real_app(REAL_APP_SCRIPT, TRUSTED_PROXIES='127.0.0.1')

        assert result['key_func'] is True
        # Super admin sign-in allows 5 attempts a minute for each visitor.
        assert result['first'] == [401] * 5 + [429]
        assert result['second'] == [401, 401]
        # Login history holds the visitors, not the proxy and not the header
        # anyone can write.
        assert result['recorded'] == ['198.51.100.7', '198.51.100.8']
        # A third visitor's first request has the whole default limit left.
        assert result['remaining'] == '199'

    def test_community_default_believes_no_header(self):
        result = run_real_app(REAL_APP_SCRIPT)

        # Every request is from the peer, whatever the headers say: the
        # second "visitor" finds the bucket already used up.
        assert result['first'] == [401] * 5 + [429]
        assert result['second'] == [429, 429]
        assert result['recorded'] == ['127.0.0.1']


class TestAppUsesOneHelper:
    """Nothing in the public code reads a visitor address for itself."""

    @pytest.mark.parametrize('filename', ['app.py', 'security.py', 'auth.py', 'governance.py', 'notifications.py'])
    def test_no_direct_reads_of_address_headers(self, filename):
        with open(os.path.join(REPO_ROOT, filename), encoding='utf-8') as handle:
            source = handle.read()

        for needle in ('CF-Connecting-IP', 'X-Real-IP', 'request.remote_addr', 'get_remote_address',
                       "headers.get('X-Forwarded-For"):
            assert needle not in source, f'{filename} reads {needle}: use client_address.get_client_address()'


# ---------------------------------------------------------------------------
# Enterprise Edition: the hosted service's proxies
# ---------------------------------------------------------------------------

try:
    from ee.backend.cloudflare import cloudflare_security
    EE_AVAILABLE = True
except ImportError:
    cloudflare_security = None
    EE_AVAILABLE = False

enterprise = pytest.mark.skipif(not EE_AVAILABLE, reason='Enterprise Edition modules not available')

CDN_EDGE = '104.22.1.1'            # inside a published Cloudflare range
CDN_EDGE_V6 = '2606:4700::1234'


@pytest.fixture
def hosted(trusted):
    """Trust what the production image trusts: the local proxy and the CDN ranges."""
    trusted(LOCAL_PROXY)
    client_address.trust_proxy_networks(
        cloudflare_security.CLOUDFLARE_IPV4_RANGES + cloudflare_security.CLOUDFLARE_IPV6_RANGES)


@enterprise
class TestHostedServiceChain:
    """Visitor -> CDN edge -> nginx on the VM -> container."""

    def test_importing_the_module_registered_the_ranges(self):
        networks = {str(n) for n in client_address.trusted_proxy_networks()}
        for cidr in cloudflare_security.CLOUDFLARE_IPV4_RANGES + cloudflare_security.CLOUDFLARE_IPV6_RANGES:
            assert cidr in networks

    def test_the_visitor_is_found_through_both_proxies(self, hosted):
        assert address(LOCAL_PROXY, {'X-Forwarded-For': f'{VISITOR}, {CDN_EDGE}'}) == VISITOR

    def test_what_the_visitor_sent_is_ignored(self, hosted):
        headers = {'X-Forwarded-For': f'{SPOOFED},{VISITOR}, {CDN_EDGE}', 'CF-Connecting-IP': SPOOFED}
        assert address(LOCAL_PROXY, headers) == VISITOR

    def test_ipv6_visitor_through_an_ipv6_edge(self, hosted):
        chain = f'2001:db8:1::5, {CDN_EDGE_V6}'
        assert address(LOCAL_PROXY, {'X-Forwarded-For': chain}) == '2001:db8:1::5'

    def test_a_request_that_did_not_pass_the_cdn_is_its_own_sender(self, hosted):
        """If the origin were ever reachable directly, the header would not be believed."""
        headers = {'X-Forwarded-For': f'{VISITOR}, {SPOOFED}', 'CF-Connecting-IP': VISITOR, 'CF-Ray': 'x'}
        assert address(LOCAL_PROXY, headers) == SPOOFED

    def test_cdn_ranges_alone_do_not_make_a_peer_trusted(self, trusted):
        client_address.trust_proxy_networks(cloudflare_security.CLOUDFLARE_IPV4_RANGES)
        assert address(LOCAL_PROXY, {'X-Forwarded-For': f'{VISITOR}, {CDN_EDGE}'}) == LOCAL_PROXY

    def test_get_real_client_ip_is_the_same_answer(self, hosted):
        headers = {'X-Forwarded-For': f'{VISITOR}, {CDN_EDGE}', 'CF-Connecting-IP': SPOOFED}
        with flask_app.test_request_context('/', environ_base={'REMOTE_ADDR': LOCAL_PROXY}, headers=headers):
            assert cloudflare_security.get_real_client_ip() == VISITOR
        with flask_app.test_request_context('/', environ_base={'REMOTE_ADDR': VISITOR}, headers=headers):
            assert cloudflare_security.get_real_client_ip() == VISITOR

    def test_the_production_image_trusts_the_docker_bridge_gateway(self):
        path = os.path.join(REPO_ROOT, 'ee', 'deployment', 'Dockerfile.production')
        with open(path, encoding='utf-8') as handle:
            lines = [line.strip() for line in handle]
        assert 'ENV TRUSTED_PROXIES=172.17.0.1' in lines
