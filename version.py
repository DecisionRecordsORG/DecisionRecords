"""
Application version management.

Version format: MAJOR.MINOR.PATCH
- MAJOR: Breaking changes or significant new features
- MINOR: New features, backward compatible
- PATCH: Bug fixes and small improvements

The version is automatically updated via git hooks on commit.
"""

import os
import json
from datetime import datetime

# Application version - automatically updated by git pre-commit hook
__version__ = "2.0.23"

# Build metadata
__build_date__ = "2026-02-06"
__git_commit__ = None  # Populated at runtime


def get_version():
    """Get the current application version."""
    return __version__


def get_build_info():
    """Get complete build information."""
    git_commit = __git_commit__

    # Try to get git commit from environment or git command
    if not git_commit:
        git_commit = os.environ.get('GIT_COMMIT', None)

    if not git_commit:
        try:
            import subprocess
            result = subprocess.run(
                ['git', 'rev-parse', '--short', 'HEAD'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                git_commit = result.stdout.strip()
        except Exception:
            git_commit = 'unknown'

    return {
        'version': __version__,
        'build_date': __build_date__,
        'git_commit': git_commit,
        'environment': os.environ.get('ENVIRONMENT', 'development')
    }


def get_version_string():
    """Get formatted version string for display."""
    info = get_build_info()
    if info['git_commit'] and info['git_commit'] != 'unknown':
        return f"v{info['version']} ({info['git_commit']})"
    return f"v{info['version']}"


def parse_version(version_str):
    """Parse version string into tuple for comparison."""
    # Remove 'v' prefix if present
    version_str = version_str.lstrip('v')
    try:
        parts = version_str.split('.')
        return tuple(int(p) for p in parts[:3])
    except (ValueError, AttributeError):
        return (0, 0, 0)


def compare_versions(current, latest):
    """
    Compare two version strings.
    Returns:
        -1 if current < latest (update available)
         0 if current == latest (up to date)
         1 if current > latest (ahead of latest)
    """
    current_tuple = parse_version(current)
    latest_tuple = parse_version(latest)

    if current_tuple < latest_tuple:
        return -1
    elif current_tuple > latest_tuple:
        return 1
    return 0


def check_for_updates(timeout=5):
    """
    Check GitHub releases for newer version.
    Returns dict with update information.
    """
    import urllib.request
    import ssl

    result = {
        'current_version': __version__,
        'latest_version': None,
        'update_available': False,
        'release_url': None,
        'release_notes': None,
        'error': None
    }

    try:
        # GitHub API endpoint for latest release
        url = 'https://api.github.com/repos/DecisionRecordsORG/DecisionRecords/releases/latest'

        req = urllib.request.Request(
            url,
            headers={
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': f'DecisionRecords/{__version__}'
            }
        )

        # Create SSL context
        context = ssl.create_default_context()

        with urllib.request.urlopen(req, timeout=timeout, context=context) as response:
            data = json.loads(response.read().decode('utf-8'))

            latest_version = data.get('tag_name', '').lstrip('v')
            result['latest_version'] = latest_version
            result['release_url'] = data.get('html_url')
            result['release_notes'] = data.get('body', '')[:500]  # First 500 chars

            comparison = compare_versions(__version__, latest_version)
            result['update_available'] = comparison < 0

    except urllib.error.HTTPError as e:
        if e.code == 404:
            result['error'] = 'No releases found'
        else:
            result['error'] = f'GitHub API error: {e.code}'
    except urllib.error.URLError as e:
        result['error'] = f'Network error: {str(e.reason)}'
    except json.JSONDecodeError:
        result['error'] = 'Invalid response from GitHub'
    except Exception as e:
        result['error'] = f'Check failed: {str(e)}'

    return result
