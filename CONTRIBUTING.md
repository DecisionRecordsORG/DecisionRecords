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
- Node.js 18+
- npm 9+

### Local Development

```bash
# Clone your fork
git clone https://github.com/YOUR-USERNAME/decision-records.git
cd decision-records

# Create Python virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm ci
cd ..

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
.venv/bin/python -m pytest tests/ -v

# Frontend tests
cd frontend
npm test

# E2E tests
npx playwright test
```

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
