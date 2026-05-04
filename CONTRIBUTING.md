# Contributing to PhantomKey

Thank you for considering a contribution. PhantomKey is a security tool, so contributions are held to a high bar — but we want them, and we want the contribution path to be smooth.

---

## Before you start

### 1. Sign the CLA

All contributors must sign the [Contributor License Agreement](CLA.md). It's a one-time, one-click process via [CLA Assistant](https://cla-assistant.io/) — when you open your first PR, the bot will comment with a link.

The CLA grants PhantomKey the right to license, sublicense, and re-license your contribution, including under future open-source or proprietary commercial licenses. PhantomKey currently uses a **source-available license with a free Personal Use grant** ([`LICENSE`](LICENSE)) — not a recognized open-source license. The CLA is what gives the project the optionality to evolve the license over time (toward fuller open-source or toward tighter commercial terms) without re-collecting consent from every past contributor. If that's a dealbreaker for you, please open a discussion first; we're happy to talk it through.

### 2. Find the right kind of contribution

Good first contributions:
- Fix a bug from the [open issues](https://github.com/ritviksalim/phantomkey/issues)
- Improve documentation, examples, or error messages
- Add tests for an under-covered area
- Add a new credential type with sanitization rules
- Add an executor for a new protocol (gRPC, GraphQL, etc.)

Please **open an issue first** for:
- New features that change the public CLI or MCP surface
- Changes to the encryption, key-derivation, or sanitization logic
- Anything that touches the threat model

The reason: a feature that lands on `main` without alignment can't be removed without breaking users. A 10-minute discussion in an issue is cheaper than a deprecation later.

### 3. Read the threat model

If your change touches `vault/`, `executor/`, `mcp/`, or `auth/`, read [`docs/threat-model.md`](docs/threat-model.md) first. PhantomKey makes specific guarantees and explicit non-guarantees — please don't accidentally weaken either.

---

## Development setup

### Requirements

- Python 3.11+
- `pip` or `uv`
- Git

### Clone and install

```bash
git clone https://github.com/ritviksalim/phantomkey.git
cd phantomkey
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

The `[dev]` extra installs `pytest`, `pytest-asyncio`, `respx`, and `pytest-cov`.

### Run the test suite

```bash
pytest
```

With coverage:

```bash
pytest --cov=phantomkey --cov-report=term-missing
```

### Run the CLI from source

```bash
phantomkey --help
```

### Run the MCP server from source

```bash
PHANTOMKEY_MASTER_KEY="your-test-password" python -m phantomkey.mcp.server
```

> ⚠️ **Use a test vault for development.** Set `PHANTOMKEY_VAULT_DIR=/tmp/phantomkey-dev` so you don't risk corrupting your real vault during development.

---

## Coding standards

### Test-Driven Development is required

PhantomKey is developed strict TDD: **write the test first, watch it fail, then write the implementation.** PRs that add code without tests will be asked to add tests before merge. PRs that fix bugs without a regression test will be asked to add one.

This is non-negotiable for a security tool. The cost of a silent regression in the encryption or sanitization layer is too high to skip the safety net.

### Style

- Follow PEP 8.
- Type hints on all public functions.
- `ruff` and `mypy` clean (CI enforces this — see `.github/workflows/ci.yml`).
- No new dependencies without discussion. Each dependency is a supply-chain risk; the bar is high.

### Commit messages

- Short imperative subject line, ≤72 characters: `Fix sanitizer to redact bearer tokens in 4xx responses`
- A body when the *why* is non-obvious. Skip the body for trivial changes.
- Reference issues with `Fixes #123` or `Refs #123` when applicable.

### Branching

- Branch from `main`.
- Use a topic prefix: `fix/`, `feat/`, `docs/`, `refactor/`, `test/`, `chore/`.
- Keep branches small. One logical change per PR.

---

## Pull requests

### What a good PR looks like

- A clear title describing the change in user-visible terms.
- A description that answers: **what changed, why, what alternatives were considered, and how to verify it works.**
- Tests covering the change.
- Updated docs if the behavior is user-visible.
- A note in `CHANGELOG.md` under the `## [Unreleased]` section.

### What CI checks

- Test suite passes on Python 3.11, 3.12, 3.13 (Linux + macOS).
- `ruff check` and `ruff format --check` pass.
- `mypy` passes.
- Coverage does not regress.
- CLA Assistant confirms you've signed.

### Review process

PhantomKey is currently maintained by a single maintainer ([@ritviksalim](https://github.com/ritviksalim)). Reviews are usually within a week. Expect:

- Feedback on the *threat-model implications* of any security-relevant change.
- Feedback on whether the test coverage is adequate.
- Feedback on whether the change belongs in the source-available core (this repo, free Personal Use tier) or in the proprietary cloud product (paid commercial tier). If it sounds like the latter, the maintainer will say so and you can decide whether to redirect or pass.

PRs that pass review are merged via squash-merge to keep `main` history linear.

---

## Reporting bugs

Open an issue using the bug-report template. Include:
- PhantomKey version (`phantomkey --version`)
- Python version, OS
- MCP client (Claude Desktop / Cursor / Cline / other) if relevant
- Minimal reproduction
- What you expected vs. what happened

For **security-sensitive** bugs, **do not file a public issue.** Follow [`SECURITY.md`](SECURITY.md) instead.

---

## Reporting security vulnerabilities

See [`SECURITY.md`](SECURITY.md). Use a private channel — GitHub Security Advisory or email — never a public issue.

---

## Suggesting features

Open a feature-request issue. Useful framing:
- **What problem are you trying to solve?** (Not "what feature do you want?" — start with the underlying need.)
- **What does the ideal user experience look like?**
- **What alternatives have you considered?**
- **Is this a fit for the source-available core (free Personal Use tier), or a paid commercial / cloud feature?**

The last question matters: PhantomKey ships in two tiers. Feature requests that are fundamentally team/sync/dashboard-shaped — or that target use within an organization — will likely land in the proprietary commercial product rather than this repo.

---

## Code of Conduct

Be civil, generous, and direct. Disagree with ideas, not people. Assume good faith and ask clarifying questions before assuming malice. We don't have a separate `CODE_OF_CONDUCT.md` yet — this paragraph is the policy, and the project owner enforces it. As the project grows, we will adopt the [Contributor Covenant](https://www.contributor-covenant.org/).

---

## License

By contributing, you agree that your contributions will be licensed under the project's license (see [`LICENSE`](LICENSE)) and that you have signed the [CLA](CLA.md).

---

## Questions?

- General: open a [Discussion](https://github.com/ritviksalim/phantomkey/discussions)
- Bugs: open an [Issue](https://github.com/ritviksalim/phantomkey/issues)
- Security: see [`SECURITY.md`](SECURITY.md)
- Direct: ritviksalim@gmail.com
