# Contributing to inkmap

## Prerequisites

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- [just](https://github.com/casey/just)
- Optional: [direnv](https://direnv.net/)

## Getting Started

```sh
git clone https://github.com/urmzd/inkmap.git
cd inkmap
just init
```

## Development

| Command | Action |
|---------|--------|
| `just test` | Run the tests |
| `just lint` | Run the linter |
| `just fmt` | Format the code |
| `just typecheck` | Run the type checker |
| `just check` | Format, lint, and test (the quality gate) |
| `just run <args>` | Run the CLI |

Run `just check` before you open a pull request.

## Commit Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/).
The release tool reads the commit messages to set the version.

```text
feat: add a new capability
fix: correct a bug
docs: change documentation only
```

Other types: `perf`, `refactor`, `test`, `build`, `ci`, `chore`, `style`, `revert`.

## Pull Requests

1. Fork the repository.
2. Create a branch from `main`.
3. Make your change and add tests.
4. Run `just check`.
5. Open a pull request. Fill in the template.

## Code Style

- Ruff formats and lints the code. Line length is 100.
- Add type hints to public functions.
- Keep functions short and focused.
- Write a test for each new behavior.

## Security

Do not report security problems in public issues. See [SECURITY.md](SECURITY.md).
