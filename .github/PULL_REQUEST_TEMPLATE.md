<!--
Thank you for contributing to PhantomKey.

Before opening this PR, please confirm:
  1. You have signed the CLA (CLA Assistant will check on first PR).
  2. You have read CONTRIBUTING.md.
  3. If this PR touches vault/, executor/, mcp/, or auth/, you have read docs/threat-model.md.
-->

## Summary

<!-- One or two sentences. What changes for the user? -->

## Why

<!-- The motivation. Link an issue if there is one (Fixes #123 / Refs #123). -->

## What changed

<!-- A bulleted breakdown of the changes. Public-API changes, internal refactors,
     test-only changes, doc-only changes — call them out clearly. -->

-

## Threat-model implications

<!-- Required if this PR touches vault/, executor/, mcp/, auth/, audit/, or any
     security-relevant code path. Otherwise write "N/A".

     Answer:
     - Does this change what PhantomKey defends against?
     - Does this expand the attack surface (e.g., new MCP tool, new executor protocol)?
     - Does this weaken any existing guarantee?
     - Should SECURITY.md or docs/threat-model.md be updated to match? -->

N/A

## Open-core scope

<!-- Required for new features. Otherwise delete this section.

     Is this a fit for the open-source core, or does it belong in the
     proprietary cloud product? See CONTRIBUTING.md for the open-core boundary. -->

- [ ] Open-source core (this repo)
- [ ] Belongs in the proprietary cloud product (please discuss before implementing)

## How to verify

<!-- Steps a reviewer (or future-you) can run to confirm this works.
     Include: commands, expected output, vault state if relevant. -->

```bash
# Example:
PHANTOMKEY_VAULT_DIR=/tmp/test phantomkey init --no-recovery
phantomkey add ...
```

## Checklist

- [ ] Tests added or updated (TDD: red → green → refactor)
- [ ] Coverage does not regress
- [ ] `ruff check` and `ruff format --check` pass
- [ ] `mypy` passes
- [ ] User-visible changes documented in `README.md` and/or `docs/`
- [ ] Entry added to `CHANGELOG.md` under `## [Unreleased]`
- [ ] CLA signed (CLA Assistant will confirm)
- [ ] No new dependencies, OR new dependency justified in the description above
- [ ] No secrets, real credentials, or production data in the diff or test fixtures

## Breaking changes

<!-- If this PR breaks the public CLI, MCP tool surface, vault file format, or
     any other public contract, describe the break, the migration path, and
     why it can't be done backward-compatibly. Otherwise write "None". -->

None

## Notes for the reviewer

<!-- Anything else the reviewer should know — design alternatives considered,
     open questions, follow-up work intentionally deferred, etc. -->
