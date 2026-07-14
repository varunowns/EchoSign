# GitHub Repository Setup

## Initial Setup

```bash
git init
git add .
git commit -m "Initial commit: EchoSign full stack"
git branch -M main
git remote add origin https://github.com/varunowns/EchoSign.git
git push -u origin main
```

## Branches

- `main` - Production-ready code
- `develop` - Development branch
- `feature/*` - Feature branches
- `bugfix/*` - Bug fix branches

## Contributing

1. Create feature branch: `git checkout -b feature/your-feature`
2. Commit changes: `git commit -m "Add your feature"`
3. Push to branch: `git push origin feature/your-feature`
4. Open Pull Request on GitHub

## Commit Message Format

```
type(scope): subject

body

footer
```

Types: feat, fix, docs, style, refactor, perf, test, chore
