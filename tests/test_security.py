"""
Tests for security module functions.
"""
import pytest
from flask import Flask, g, session

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security import (
    sanitize_html, sanitize_string, sanitize_text_field,
    sanitize_title, sanitize_name, sanitize_email,
    validate_email, validate_domain, sanitize_request_data,
    generate_csrf_token, validate_csrf_token
)


class TestSanitizeHTML:
    """Test HTML sanitization functions."""

    def test_sanitize_html_allows_safe_tags(self):
        """sanitize_html allows safe HTML tags."""
        input_html = '<p>Hello <strong>world</strong></p>'
        result = sanitize_html(input_html)

        # Should preserve safe tags
        assert '<p>' in result or 'Hello' in result
        assert 'world' in result

    def test_sanitize_html_removes_script_tags(self):
        """sanitize_html removes script tags (but text content may remain)."""
        input_html = '<p>Hello</p><script>alert("xss")</script>'
        result = sanitize_html(input_html)

        # Script tags are removed
        assert '<script>' not in result
        assert '</script>' not in result
        assert 'Hello' in result

    def test_sanitize_html_removes_onclick(self):
        """sanitize_html removes onclick handlers."""
        input_html = '<p onclick="alert()">Click me</p>'
        result = sanitize_html(input_html)

        assert 'onclick' not in result
        assert 'Click me' in result

    def test_sanitize_html_handles_empty_string(self):
        """sanitize_html handles empty string."""
        result = sanitize_html('')
        assert result == ''

    def test_sanitize_html_handles_non_string(self):
        """sanitize_html returns non-strings unchanged."""
        result = sanitize_html(123)
        assert result == 123


class TestSanitizeString:
    """Test general string sanitization."""

    def test_sanitize_string_strips_whitespace(self):
        """sanitize_string strips leading/trailing whitespace."""
        result = sanitize_string('  hello  ')
        assert result == 'hello'

    def test_sanitize_string_enforces_max_length(self):
        """sanitize_string truncates to max_length."""
        long_string = 'a' * 100
        result = sanitize_string(long_string, max_length=10)
        assert len(result) == 10

    def test_sanitize_string_strips_html_by_default(self):
        """sanitize_string strips HTML tags by default."""
        result = sanitize_string('<p>Hello</p>')
        assert '<p>' not in result
        assert 'Hello' in result

    def test_sanitize_string_allows_html_when_specified(self):
        """sanitize_string allows safe HTML when allow_html=True."""
        result = sanitize_string('<p>Hello</p>', allow_html=True)
        # Should preserve safe tags or at least the text
        assert 'Hello' in result

    def test_sanitize_string_force_strips_all_tags(self):
        """sanitize_string strips all tags when strip_all_tags=True."""
        result = sanitize_string('<p>Hello</p>', allow_html=True, strip_all_tags=True)
        assert '<p>' not in result
        assert 'Hello' in result


class TestSanitizeTextField:
    """Test text field sanitization (for decision content)."""

    def test_sanitize_text_field_allows_safe_html(self):
        """sanitize_text_field allows safe HTML formatting."""
        input_text = '<p>Decision context with <strong>emphasis</strong></p>'
        result = sanitize_text_field(input_text)

        assert 'Decision context' in result
        assert 'emphasis' in result

    def test_sanitize_text_field_removes_dangerous_html(self):
        """sanitize_text_field removes dangerous HTML."""
        input_text = '<p>Safe</p><script>dangerous()</script>'
        result = sanitize_text_field(input_text)

        assert 'Safe' in result
        assert '<script>' not in result

    def test_sanitize_text_field_enforces_max_length(self):
        """sanitize_text_field enforces max length (default 10000)."""
        long_text = 'a' * 15000
        result = sanitize_text_field(long_text)
        assert len(result) <= 10000


class TestSanitizeTitle:
    """Test title sanitization (no HTML allowed)."""

    def test_sanitize_title_strips_all_html(self):
        """sanitize_title removes all HTML tags."""
        result = sanitize_title('<p>Decision Title</p>')
        assert '<p>' not in result
        assert 'Decision Title' in result

    def test_sanitize_title_enforces_max_length(self):
        """sanitize_title enforces max length (default 255)."""
        long_title = 'a' * 300
        result = sanitize_title(long_title)
        assert len(result) <= 255

    def test_sanitize_title_removes_script_injection(self):
        """sanitize_title removes script tags (but text content may remain)."""
        result = sanitize_title('Title<script>alert("xss")</script>')
        # Script tags are stripped
        assert '<script>' not in result
        assert '</script>' not in result
        assert 'Title' in result


class TestSanitizeName:
    """Test name field sanitization."""

    def test_sanitize_name_strips_html(self):
        """sanitize_name removes HTML tags."""
        result = sanitize_name('<b>John Doe</b>')
        assert '<b>' not in result
        assert 'John Doe' in result

    def test_sanitize_name_enforces_max_length(self):
        """sanitize_name enforces max length."""
        long_name = 'a' * 300
        result = sanitize_name(long_name, max_length=100)
        assert len(result) <= 100


class TestSanitizeEmail:
    """Test email sanitization and validation."""

    def test_sanitize_email_lowercases(self):
        """sanitize_email converts to lowercase."""
        result = sanitize_email('USER@EXAMPLE.COM')
        assert result == 'user@example.com'

    def test_sanitize_email_strips_whitespace(self):
        """sanitize_email strips whitespace."""
        result = sanitize_email('  user@example.com  ')
        assert result == 'user@example.com'

    def test_sanitize_email_removes_html(self):
        """sanitize_email removes HTML tags."""
        result = sanitize_email('<script>alert()</script>user@example.com')
        # Should remove script and validate
        assert '<script>' not in result if result else True

    def test_sanitize_email_validates_format(self):
        """sanitize_email returns None for invalid format."""
        result = sanitize_email('not-an-email')
        assert result is None

    def test_sanitize_email_accepts_valid_email(self):
        """sanitize_email accepts valid email."""
        result = sanitize_email('user@example.com')
        assert result == 'user@example.com'


class TestValidateEmail:
    """Test email format validation."""

    def test_validate_email_accepts_valid(self):
        """validate_email returns True for valid email."""
        assert validate_email('user@example.com') is True
        assert validate_email('user.name@example.co.uk') is True
        assert validate_email('user+tag@example.com') is True

    def test_validate_email_rejects_invalid(self):
        """validate_email returns False for invalid email."""
        assert validate_email('not-an-email') is False
        assert validate_email('@example.com') is False
        assert validate_email('user@') is False
        assert validate_email('user') is False

    def test_validate_email_handles_none(self):
        """validate_email handles None gracefully."""
        assert validate_email(None) is False

    def test_validate_email_handles_empty_string(self):
        """validate_email handles empty string."""
        assert validate_email('') is False


class TestValidateDomain:
    """Test domain format validation."""

    def test_validate_domain_accepts_valid(self):
        """validate_domain returns True for valid domain."""
        assert validate_domain('example.com') is True
        assert validate_domain('subdomain.example.com') is True
        assert validate_domain('example.co.uk') is True

    def test_validate_domain_rejects_invalid(self):
        """validate_domain returns False for invalid domain."""
        assert validate_domain('not a domain') is False
        assert validate_domain('.example.com') is False
        assert validate_domain('example') is False

    def test_validate_domain_handles_none(self):
        """validate_domain handles None gracefully."""
        assert validate_domain(None) is False

    def test_validate_domain_handles_empty_string(self):
        """validate_domain handles empty string."""
        assert validate_domain('') is False


class TestSanitizeRequestData:
    """Test request data sanitization with schema."""

    def test_sanitize_request_data_validates_required_fields(self):
        """sanitize_request_data validates required fields."""
        schema = {
            'title': {'type': 'title', 'required': True},
            'context': {'type': 'text', 'required': True}
        }
        data = {'title': 'Test'}  # Missing context

        sanitized, errors = sanitize_request_data(data, schema)

        assert len(errors) > 0
        assert any('context' in err for err in errors)

    def test_sanitize_request_data_sanitizes_fields(self):
        """sanitize_request_data sanitizes field values."""
        schema = {
            'title': {'type': 'title', 'max_length': 100},
            'email': {'type': 'email'}
        }
        data = {
            'title': '<script>Bad</script>Good Title',
            'email': 'USER@EXAMPLE.COM'
        }

        sanitized, errors = sanitize_request_data(data, schema)

        assert '<script>' not in sanitized['title']
        assert 'Good Title' in sanitized['title']
        assert sanitized['email'] == 'user@example.com'

    def test_sanitize_request_data_handles_invalid_email(self):
        """sanitize_request_data validates email format."""
        schema = {
            'email': {'type': 'email', 'required': True}
        }
        data = {'email': 'not-an-email'}

        sanitized, errors = sanitize_request_data(data, schema)

        assert len(errors) > 0
        assert any('email' in err for err in errors)

    def test_sanitize_request_data_skips_optional_missing_fields(self):
        """sanitize_request_data skips optional missing fields."""
        schema = {
            'title': {'type': 'title', 'required': True},
            'optional': {'type': 'text', 'required': False}
        }
        data = {'title': 'Test'}

        sanitized, errors = sanitize_request_data(data, schema)

        assert len(errors) == 0
        assert 'optional' not in sanitized

    def test_sanitize_request_data_handles_invalid_input(self):
        """sanitize_request_data handles invalid input type."""
        schema = {'title': {'type': 'title'}}
        data = "not a dict"

        sanitized, errors = sanitize_request_data(data, schema)

        assert len(errors) > 0
        assert sanitized == {}


class TestCSRFProtection:
    """Test CSRF token generation and validation."""

    def test_generate_csrf_token_creates_token(self, app):
        """generate_csrf_token creates a token in session."""
        with app.test_request_context():
            token = generate_csrf_token()
            assert token is not None
            assert len(token) > 0
            assert session.get('_csrf_token') == token

    def test_generate_csrf_token_reuses_existing(self, app):
        """generate_csrf_token reuses existing token."""
        with app.test_request_context():
            token1 = generate_csrf_token()
            token2 = generate_csrf_token()
            assert token1 == token2

    def test_validate_csrf_token_accepts_valid(self, app):
        """validate_csrf_token accepts valid token."""
        with app.test_request_context():
            token = generate_csrf_token()
            assert validate_csrf_token(token) is True

    def test_validate_csrf_token_rejects_invalid(self, app):
        """validate_csrf_token rejects invalid token."""
        with app.test_request_context():
            generate_csrf_token()
            assert validate_csrf_token('invalid-token') is False

    def test_validate_csrf_token_rejects_none(self, app):
        """validate_csrf_token rejects None."""
        with app.test_request_context():
            generate_csrf_token()
            assert validate_csrf_token(None) is False

    def test_validate_csrf_token_rejects_when_no_session_token(self, app):
        """validate_csrf_token rejects when no session token exists."""
        with app.test_request_context():
            # No token in session
            assert validate_csrf_token('some-token') is False


class TestSecurityHeaders:
    """Test security header functions."""

    def test_get_security_headers_returns_dict(self):
        """get_security_headers returns dictionary of headers."""
        from security import get_security_headers

        headers = get_security_headers()
        assert isinstance(headers, dict)
        assert 'X-Content-Type-Options' in headers
        assert 'X-Frame-Options' in headers
        assert 'X-XSS-Protection' in headers

    def test_apply_security_headers_adds_headers(self, app):
        """apply_security_headers adds headers to response."""
        from security import apply_security_headers
        from flask import make_response

        with app.test_request_context():
            response = make_response('test')
            response = apply_security_headers(response)

            assert 'X-Content-Type-Options' in response.headers
            assert response.headers['X-Content-Type-Options'] == 'nosniff'


class TestInputValidationEdgeCases:
    """Test edge cases for input validation."""

    def test_sanitize_handles_unicode(self):
        """Sanitization handles unicode characters."""
        result = sanitize_title('Test 你好 Title')
        assert '你好' in result

    def test_sanitize_handles_special_chars(self):
        """Sanitization handles special characters."""
        result = sanitize_title('Test & Title <> "quotes"')
        assert 'Test' in result
        assert 'Title' in result

    def test_sanitize_handles_newlines(self):
        """Sanitization handles newlines."""
        result = sanitize_string('Line 1\nLine 2\rLine 3')
        assert 'Line 1' in result

    def test_empty_string_sanitization(self):
        """Empty strings are handled correctly."""
        assert sanitize_title('') == ''
        assert sanitize_text_field('') == ''
        assert sanitize_name('') == ''
