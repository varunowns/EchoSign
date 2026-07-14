# Contributing to EchoSign

Thank you for your interest in contributing to EchoSign! Here's how to get started.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/EchoSign.git`
3. Create a branch: `git checkout -b feature/your-feature`
4. Install dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   cd ../frontend
   npm install
   ```

## Development Workflow

### Backend (Python)
- Code style: Follow PEP 8
- Add docstrings to functions and classes
- Run tests: `python test_integration.py`
- Keep dependencies in `backend/requirements.txt` updated

### Frontend (React)
- Code style: Follow Airbnb JavaScript style guide
- Use functional components and hooks
- Test before committing
- Update `frontend/package.json` with new dependencies

## Making Changes

1. Make your changes in your feature branch
2. Add/update tests as needed
3. Update documentation if you changed behavior
4. Commit with clear message: `git commit -m "type(scope): description"`

### Commit Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation update
- `style`: Code style changes
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `test`: Adding/updating tests
- `chore`: Build/dependency updates

## Submitting Changes

1. Push to your fork: `git push origin feature/your-feature`
2. Open a Pull Request with a clear description
3. Wait for review and address feedback
4. Once approved, your PR will be merged

## Code Review Guidelines

All submissions require review. Reviews focus on:
- Code quality and style
- Test coverage
- Documentation
- Performance implications
- Security considerations

## Reporting Bugs

Use GitHub Issues to report bugs. Include:
- Detailed description of the bug
- Steps to reproduce
- Expected vs actual behavior
- Screenshots if applicable
- System information

## Questions?

- Open a GitHub Discussion
- Check existing issues for similar questions
- Review documentation in the README

## Code of Conduct

Be respectful, inclusive, and constructive. We're all here to build something great together!

---

Happy contributing! 🎉
