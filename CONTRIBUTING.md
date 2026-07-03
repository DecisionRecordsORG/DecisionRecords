# Contributing to Decision Records

Thank you for your interest in contributing to Decision Records! This document provides guidelines and information for contributors.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment. Be kind, constructive, and professional in all interactions.

## How to Contribute

### Reporting Bugs

1. Check existing [issues](https://github.com/decisionrecords/decision-records/issues) to avoid duplicates
2. Create a new issue with:
   - Clear, descriptive title
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, browser, version)

### Suggesting Features

1. Check existing issues and discussions for similar ideas
2. Create a feature request issue with:
   - Use case description
   - Proposed solution
   - Alternative approaches considered

### Submitting Code

1. **Fork** the repository
2. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** following our coding standards
4. **Test** your changes thoroughly
5. **Commit** with clear messages:
   ```bash
   git commit -m "Add feature: brief description"
   ```
6. **Push** to your fork
7. **Open a Pull Request** against the `main` branch

## Development Setup

### Prerequisites

- Python 3.11+
- uv
- Node.js 18+
- npm 9+

### Local Development

```bash
# Clone your fork
git clone https://github.com/YOUR-USERNAME/decision-records.git
cd decision-records

# Create Python virtual environment and install dependencies
uv venv --python 3.12
uv pip install -r requirements.txt pytest pytest-cov

# Install frontend dependencies
cd frontend
npm ci
cd ..
# Optional Enterprise setup when private ee/ is checked out
uv pip install -r ee/requirements.txt
ln -sfn ../../frontend/node_modules ee/frontend/node_modules
# Run development server
# Terminal 1: Backend
FLASK_ENV=development python run_local.py

# Terminal 2: Frontend
cd frontend
npm start
```

Access the app at http://localhost:4200

### Running Tests

```bash
# Backend tests
uv run pytest tests/ -v

# Enterprise backend tests when ee/ is checked out
DECISION_RECORDS_EDITION=enterprise AZURE_KEYVAULT_URL= uv run pytest tests/ -q --tb=short

# Community/Enterprise boundary check
uv run python scripts/check_ce_boundary.py

# Open-source artifact boundary check
uv run python scripts/check_public_artifacts.py --mode staged

# Commit-time QA checks
uv run python scripts/qa_check.py --mode commit

# Full local QA before release/deploy
uv run python scripts/qa_check.py --mode full

# Frontend tests
cd frontend
npm test

# E2E tests
npx playwright test
```

### Git Hook Setup

Enable the versioned pre-commit hook once per checkout:

```bash
git config core.hooksPath .githooks
```

The hook runs fast staged QA before commits. It can be bypassed with `SKIP_COMMIT_QA=1 git commit` only for emergencies.

The hook also blocks production infrastructure snapshots, exact private Azure
resource identifiers, and high-confidence secret material from the public
repository. Put Enterprise infrastructure source and generated snapshots under
the private `ee/infra` boundary.

Verify the hook wiring and the private-artifact rejection path with:

```bash
uv run python scripts/verify_git_hooks.py
```

### Git Safety With Enterprise Submodule

- The public repository and `ee/` are separate Git repositories. Check both statuses before committing.
- If `ee` is on detached `HEAD`, switch to a named branch before making or keeping changes.
- Commit and push private `ee` changes first, then update the public parent submodule pointer.
- Do not put production infra snapshots, exact Azure resource names, or commercial module code in the public tree.
- Do not commit generated files such as `ee/infra/aca/main.json` or local symlinks such as `ee/frontend/node_modules`.
- Do not use destructive Git cleanup commands unless the intended revert/reset is explicit.

## Coding Standards

### Python

- Follow PEP 8 style guide
- Use type hints where practical
- Document functions with docstrings
- Keep functions focused and small

### TypeScript/Angular

- Follow Angular style guide
- Use strict TypeScript settings
- Prefer standalone components
- Use dependency injection

### Git Commits

- Use clear, descriptive commit messages
- Start with a verb: "Add", "Fix", "Update", "Remove"
- Reference issues when applicable: "Fix #123: ..."

## What You Can Contribute

### Community Edition (Open Source)

Contributions to the core platform are welcome:

- Bug fixes
- Documentation improvements
- UI/UX enhancements
- Performance optimizations
- Accessibility improvements
- Test coverage
- New core features (discuss first)

### What Belongs in /ee (Enterprise)

The following are Enterprise Edition features and should NOT be contributed to the open source codebase:

- Slack integration
- Microsoft Teams integration
- Google OAuth
- AI-powered features
- PostHog analytics
- Azure-specific code
- Marketing pages

If you're interested in contributing to Enterprise features, please contact us.

## Pull Request Guidelines

### Before Submitting

- [ ] Code compiles without errors
- [ ] Community/Enterprise boundary check passes
- [ ] Commit-time QA passes
- [ ] Tests pass locally
- [ ] Code follows style guidelines
- [ ] Documentation updated if needed
- [ ] Commit messages are clear

### PR Description

Include:
- What the PR does
- Why it's needed
- How it was tested
- Screenshots for UI changes

### Review Process

1. Maintainers will review your PR
2. Address any feedback
3. Once approved, a maintainer will merge

## License

By contributing, you agree that your contributions will be licensed under the same [BSL 1.1 License](LICENSE) that covers the project.

## Questions?

- Open a [GitHub Discussion](https://github.com/decisionrecords/decision-records/discussions)
- Check the [documentation](docs/)

Thank you for contributing!
