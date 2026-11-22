"""
Validation of the tokens the Teams integration accepts (Enterprise Edition).

Two kinds of token arrive from outside: the Bot Framework token on the bot
webhook, and the Teams SSO token the tab sends to sign in. These tests sign
tokens with a local RSA key standing in for Microsoft's published keys and
check each rule: signature, algorithm, issuer, audience, expiry, required
claims, and for the bot the serviceUrl binding.
"""
import base64
import json
import os
import sys
import time

import jwt
import pytest
from flask import Flask
from unittest.mock import Mock
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if not os.path.exists(os.path.join(_ROOT, 'models.py')):
    _ROOT = os.getcwd()
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from ee.backend.teams import teams_security
    from ee.backend.oauth_providers import microsoft_oauth
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False
    teams_security = None
    microsoft_oauth = None

EE_TESTS_ENABLED = EE_AVAILABLE and os.environ.get('DECISION_RECORDS_EDITION', 'community') == 'enterprise'
pytestmark = pytest.mark.skipif(
    not EE_TESTS_ENABLED,
    reason="Enterprise Edition tests require DECISION_RECORDS_EDITION=enterprise and EE modules",
)

BOT_APP_ID = 'a1b2c3d4-0000-4000-8000-00000000b077'
OTHER_APP_ID = 'ffffffff-0000-4000-8000-00000000ffff'
MS_TENANT = '11111111-1111-4111-8111-111111111111'
OTHER_MS_TENANT = '22222222-2222-4222-8222-222222222222'
SERVICE_URL = 'https://smba.trafficmanager.net/emea/'
USER_OID = 'aaaaaaaa-0000-4000-8000-000000000001'


def _new_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


MICROSOFT_KEY = _new_key() if EE_TESTS_ENABLED else None
ATTACKER_KEY = _new_key() if EE_TESTS_ENABLED else None


def _pem(private_key):
    return private_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


def _public_pem(private_key):
    return private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)


def sign(claims, key=None, algorithm='RS256'):
    return jwt.encode(claims, _pem(key or MICROSOFT_KEY), algorithm=algorithm, headers={'kid': 'key-1'})


def unsigned(claims):
    def part(data):
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b'=').decode()
    return f"{part({'alg': 'none', 'typ': 'JWT', 'kid': 'key-1'})}.{part(claims)}."


def hs256_with_public_key(claims):
    """A token 'signed' with the published public key used as an HMAC secret."""
    def part(data):
        return base64.urlsafe_b64encode(data).rstrip(b'=').decode()
    import hashlib
    import hmac
    header = part(json.dumps({'alg': 'HS256', 'typ': 'JWT', 'kid': 'key-1'}).encode())
    body = part(json.dumps(claims).encode())
    signature = hmac.new(_public_pem(MICROSOFT_KEY), f'{header}.{body}'.encode(), hashlib.sha256).digest()
    return f'{header}.{body}.{part(signature)}'


@pytest.fixture
def published_keys(monkeypatch):
    """Stand in for the key sets Microsoft publishes: every token resolves to MICROSOFT_KEY."""
    client = Mock()
    client.get_signing_key_from_jwt.return_value = Mock(key=MICROSOFT_KEY.public_key())
    monkeypatch.setattr(teams_security, '_get_jwks_client', lambda: client)
    monkeypatch.setattr(microsoft_oauth, 'get_jwks_client', lambda: client)
    monkeypatch.setenv('TEAMS_BOT_APP_ID', BOT_APP_ID)
    monkeypatch.setattr(teams_security, '_teams_bot_app_id', None)
    monkeypatch.setenv('APP_BASE_URL', 'https://app.decisions.example')
    monkeypatch.setenv('OAUTH_BASE_URL', 'https://decisions.example')
    monkeypatch.delenv('TEAMS_SSO_APP_ID_URI_HOSTS', raising=False)
    monkeypatch.setenv('MICROSOFT_CLIENT_ID', OTHER_APP_ID)
    monkeypatch.setattr(microsoft_oauth, '_microsoft_client_id', None)
    yield client
    teams_security._teams_bot_app_id = None


# ---------------------------------------------------------------------------
# Bot Framework token on the webhook
# ---------------------------------------------------------------------------

def bot_claims(**overrides):
    now = int(time.time())
    claims = {
        'iss': 'https://api.botframework.com',
        'aud': BOT_APP_ID,
        'iat': now - 10,
        'nbf': now - 10,
        'exp': now + 600,
        'serviceurl': SERVICE_URL,
    }
    claims.update(overrides)
    return {k: v for k, v in claims.items() if v is not None}


def bot_validate(token, service_url=SERVICE_URL):
    return teams_security.validate_teams_jwt(f'Bearer {token}', service_url=service_url)


class TestBotFrameworkToken:

    def test_valid_token_is_accepted(self, published_keys):
        claims = bot_validate(sign(bot_claims()))
        assert claims is not None
        assert claims['aud'] == BOT_APP_ID

    def test_service_url_is_read_from_the_request_body(self, published_keys):
        app = Flask(__name__)
        token = sign(bot_claims())
        with app.test_request_context('/api/teams/webhook', method='POST',
                                      json={'type': 'message', 'serviceUrl': SERVICE_URL}):
            assert teams_security.validate_teams_jwt(f'Bearer {token}') is not None
        with app.test_request_context('/api/teams/webhook', method='POST',
                                      json={'type': 'message', 'serviceUrl': 'https://elsewhere.example/'}):
            assert teams_security.validate_teams_jwt(f'Bearer {token}') is None
        with app.test_request_context('/api/teams/webhook', method='POST', json={'type': 'message'}):
            assert teams_security.validate_teams_jwt(f'Bearer {token}') is None

    def test_trailing_slash_does_not_matter(self, published_keys):
        assert bot_validate(sign(bot_claims()), service_url=SERVICE_URL.rstrip('/')) is not None

    def test_camel_case_claim_name_is_accepted(self, published_keys):
        assert bot_validate(sign(bot_claims(serviceurl=None, serviceUrl=SERVICE_URL))) is not None

    def test_token_for_another_service_url_is_refused(self, published_keys):
        assert bot_validate(sign(bot_claims(serviceurl='https://attacker.example/'))) is None

    def test_token_without_a_service_url_claim_is_refused(self, published_keys):
        assert bot_validate(sign(bot_claims(serviceurl=None))) is None

    def test_no_activity_service_url_is_refused(self, published_keys):
        # No argument and no request to read it from
        assert teams_security.validate_teams_jwt(f'Bearer {sign(bot_claims())}') is None
        assert bot_validate(sign(bot_claims()), service_url='') is None

    @pytest.mark.parametrize('issuer', [
        'https://login.microsoftonline.com/d6d49420-f39b-4df7-a1dc-d59a935871db/v2.0',
        'https://sts.windows.net/d6d49420-f39b-4df7-a1dc-d59a935871db/',
        'https://api.botframework.com.attacker.example',
        'https://api.botframework.com/',
        'https://attacker.example',
        None,
    ])
    def test_other_issuers_are_refused(self, published_keys, issuer):
        assert bot_validate(sign(bot_claims(iss=issuer))) is None

    @pytest.mark.parametrize('audience', [
        OTHER_APP_ID, f'api://{BOT_APP_ID}', [BOT_APP_ID, OTHER_APP_ID], [BOT_APP_ID], '', None,
    ])
    def test_other_audiences_are_refused(self, published_keys, audience):
        assert bot_validate(sign(bot_claims(aud=audience))) is None

    def test_expired_token_is_refused(self, published_keys):
        now = int(time.time())
        assert bot_validate(sign(bot_claims(exp=now - 3600, iat=now - 7200, nbf=now - 7200))) is None

    def test_token_without_expiry_is_refused(self, published_keys):
        assert bot_validate(sign(bot_claims(exp=None))) is None

    def test_token_signed_by_another_key_is_refused(self, published_keys):
        assert bot_validate(sign(bot_claims(), key=ATTACKER_KEY)) is None

    def test_unsigned_token_is_refused(self, published_keys):
        assert bot_validate(unsigned(bot_claims())) is None
        published_keys.get_signing_key_from_jwt.assert_not_called()

    def test_hmac_token_made_with_the_public_key_is_refused(self, published_keys):
        assert bot_validate(hs256_with_public_key(bot_claims())) is None

    def test_tampered_payload_is_refused(self, published_keys):
        header, _, signature = sign(bot_claims()).split('.')
        forged_body = base64.urlsafe_b64encode(
            json.dumps(bot_claims(serviceurl='https://attacker.example/')).encode()).rstrip(b'=').decode()
        assert bot_validate(f'{header}.{forged_body}.{signature}',
                            service_url='https://attacker.example/') is None

    def test_no_app_id_configured_is_refused(self, published_keys, monkeypatch):
        monkeypatch.delenv('TEAMS_BOT_APP_ID')
        monkeypatch.setattr(teams_security, '_teams_bot_app_id', None)
        monkeypatch.setattr(teams_security, 'get_teams_bot_app_id', lambda: None)
        assert bot_validate(sign(bot_claims())) is None


# ---------------------------------------------------------------------------
# Teams SSO token from the tab
# ---------------------------------------------------------------------------

def sso_claims(version=2, **overrides):
    now = int(time.time())
    claims = {
        'aud': BOT_APP_ID,
        'iss': f'https://login.microsoftonline.com/{MS_TENANT}/v2.0',
        'iat': now - 10,
        'nbf': now - 10,
        'exp': now + 600,
        'oid': USER_OID,
        'tid': MS_TENANT,
        'name': 'Alice Example',
        'preferred_username': 'alice@alpha.example',
        'ver': '2.0',
    }
    if version == 1:
        claims.update({
            'aud': f'api://app.decisions.example/botid-{BOT_APP_ID}',
            'iss': f'https://sts.windows.net/{MS_TENANT}/',
            'ver': '1.0',
            'upn': 'alice@alpha.example',
        })
        del claims['preferred_username']
    claims.update(overrides)
    return {k: v for k, v in claims.items() if v is not None}


class TestTeamsSsoToken:

    def test_valid_v2_token_is_accepted(self, published_keys):
        result = microsoft_oauth.validate_teams_sso_token(sign(sso_claims()))
        assert result['oid'] == USER_OID
        assert result['tid'] == MS_TENANT
        assert result['email'] == 'alice@alpha.example'
        assert result['name'] == 'Alice Example'

    def test_valid_v1_token_is_accepted(self, published_keys):
        result = microsoft_oauth.validate_teams_sso_token(sign(sso_claims(version=1)))
        assert result['oid'] == USER_OID
        assert result['email'] == 'alice@alpha.example'

    @pytest.mark.parametrize('audience', [
        BOT_APP_ID,
        BOT_APP_ID.upper(),
        f'api://{BOT_APP_ID}',
        f'api://app.decisions.example/{BOT_APP_ID}',
        f'api://app.decisions.example/botid-{BOT_APP_ID}',
        f'api://decisions.example/botid-{BOT_APP_ID}',
    ])
    def test_application_id_and_its_uri_forms_are_accepted(self, published_keys, audience):
        assert microsoft_oauth.validate_teams_sso_token(sign(sso_claims(aud=audience))) is not None

    @pytest.mark.parametrize('audience', [
        OTHER_APP_ID,                                              # another application (the web sign-in one)
        f'api://{OTHER_APP_ID}',
        f'api://attacker.example/{BOT_APP_ID}',                    # our ID under someone else's host
        f'api://attacker.example/botid-{BOT_APP_ID}',
        f'api://app.decisions.example.attacker.example/botid-{BOT_APP_ID}',
        f'api://app.decisions.example/botid-{OTHER_APP_ID}',
        f'api://app.decisions.example/x/{BOT_APP_ID}',
        f'https://app.decisions.example/{BOT_APP_ID}',
        f'{BOT_APP_ID}0',
        '00000003-0000-0000-c000-000000000000',                    # Microsoft Graph
        [BOT_APP_ID],
        [BOT_APP_ID, OTHER_APP_ID],
        '',
        None,
    ])
    def test_other_audiences_are_refused(self, published_keys, audience):
        assert microsoft_oauth.validate_teams_sso_token(sign(sso_claims(aud=audience))) is None

    def test_extra_uri_hosts_can_be_configured(self, published_keys, monkeypatch):
        token = sign(sso_claims(aud=f'api://tab.partner.example/botid-{BOT_APP_ID}'))
        assert microsoft_oauth.validate_teams_sso_token(token) is None
        monkeypatch.setenv('TEAMS_SSO_APP_ID_URI_HOSTS', 'tab.partner.example')
        assert microsoft_oauth.validate_teams_sso_token(token) is not None

    def test_expected_audience_names_the_application(self, published_keys):
        token = sign(sso_claims(aud=OTHER_APP_ID))
        assert microsoft_oauth.validate_teams_sso_token(token, expected_audience=OTHER_APP_ID) is not None
        assert microsoft_oauth.validate_teams_sso_token(sign(sso_claims()), expected_audience=OTHER_APP_ID) is None

    def test_no_bot_application_id_configured_is_refused(self, published_keys, monkeypatch):
        # The web sign-in application ID is not used in its place
        monkeypatch.setattr(microsoft_oauth, '_teams_sso_app_id', lambda: None)
        assert microsoft_oauth.validate_teams_sso_token(sign(sso_claims(aud=OTHER_APP_ID))) is None

    @pytest.mark.parametrize('issuer', [
        f'https://login.microsoftonline.com/{OTHER_MS_TENANT}/v2.0',   # Entra ID, but not the token's tenant
        f'https://sts.windows.net/{OTHER_MS_TENANT}/',
        'https://login.microsoftonline.com/common/v2.0',
        f'https://login.microsoftonline.com/{MS_TENANT}/v2.0/extra',
        f'https://login.microsoftonline.com.attacker.example/{MS_TENANT}/v2.0',
        f'https://attacker.example/{MS_TENANT}/v2.0',
        'https://api.botframework.com',
        None,
    ])
    def test_issuer_must_be_entra_id_for_the_tokens_tenant(self, published_keys, issuer):
        assert microsoft_oauth.validate_teams_sso_token(sign(sso_claims(iss=issuer))) is None

    @pytest.mark.parametrize('tenant_id', ['common', 'organizations', '', '../' + MS_TENANT, None])
    def test_tenant_claim_must_be_a_tenant_id(self, published_keys, tenant_id):
        issuer = f'https://login.microsoftonline.com/{tenant_id}/v2.0'
        assert microsoft_oauth.validate_teams_sso_token(sign(sso_claims(tid=tenant_id, iss=issuer))) is None

    @pytest.mark.parametrize('missing', ['exp', 'iat', 'aud', 'iss', 'oid', 'tid'])
    def test_required_claims(self, published_keys, missing):
        assert microsoft_oauth.validate_teams_sso_token(sign(sso_claims(**{missing: None}))) is None

    def test_expired_token_is_refused(self, published_keys):
        now = int(time.time())
        claims = sso_claims(exp=now - 3600, iat=now - 7200, nbf=now - 7200)
        assert microsoft_oauth.validate_teams_sso_token(sign(claims)) is None

    def test_token_signed_by_another_key_is_refused(self, published_keys):
        assert microsoft_oauth.validate_teams_sso_token(sign(sso_claims(), key=ATTACKER_KEY)) is None

    def test_unsigned_token_is_refused(self, published_keys):
        assert microsoft_oauth.validate_teams_sso_token(unsigned(sso_claims())) is None
        published_keys.get_signing_key_from_jwt.assert_not_called()

    def test_hmac_token_made_with_the_public_key_is_refused(self, published_keys):
        assert microsoft_oauth.validate_teams_sso_token(hs256_with_public_key(sso_claims())) is None

    @pytest.mark.parametrize('token', [None, '', 'not-a-token', 'a.b.c', 12345, {'token': 'x'}])
    def test_malformed_tokens_are_refused(self, published_keys, token):
        assert microsoft_oauth.validate_teams_sso_token(token) is None

    def test_sign_in_name_is_preferred_over_the_email_claim(self, published_keys):
        token = sign(sso_claims(email='someone-else@victim.example'))
        assert microsoft_oauth.validate_teams_sso_token(token)['email'] == 'alice@alpha.example'

    def test_upn_is_preferred_over_the_email_claim(self, published_keys):
        token = sign(sso_claims(version=1, email='someone-else@victim.example'))
        assert microsoft_oauth.validate_teams_sso_token(token)['email'] == 'alice@alpha.example'
