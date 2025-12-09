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
__version__ = "1.3.0"

# Build metadata
__build_date__ = "2025-12-09"
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
