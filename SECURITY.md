# Security Policy

PhantomKey is a security tool. Vulnerabilities in it are taken seriously and handled with priority.

## Supported versions

PhantomKey is in pre-release. Until v1.0, only the **latest released version** receives security updates.

| Version | Supported |
|---|---|
| 0.1.x   | ✅ |
| < 0.1.0 | ❌ |

After v1.0, the policy will move to "latest minor + previous minor."

---

## Reporting a vulnerability

**Do not file public GitHub issues for security bugs.** Use one of the following private channels:

1. **GitHub Security Advisory** (preferred) — [Open a private advisory](https://github.com/ritviksalim/phantomkey/security/advisories/new). This is the fastest path; it lets us collaborate on a fix and CVE assignment in a private fork.
2. **Email** — `ritviksalim@gmail.com` with subject line `PhantomKey Security`. PGP key available on request.

### What to include

A useful report contains:

- **A clear description** of the vulnerability and its impact.
- **Reproduction steps** — exact commands, vault state, agent prompts, or config required to trigger the issue.
- **Affected version(s)** — output of `phantomkey --version` or commit hash.
- **Environment** — OS, Python version, MCP client (Claude Desktop / Cursor / Cline / other).
- **Suggested fix or mitigation**, if you have one.
- **Whether you have already disclosed this to anyone else** (other vendors, your employer's security team, etc.).
- **Whether you would like public credit** when the fix ships.

If a proof-of-concept involves real credentials, please use **disposable test credentials**, not your own.

---

## Response timeline

| When | What |
|---|---|
| Within **48 hours** | Acknowledgement that we received the report and are investigating |
| Within **5 business days** | Initial assessment: confirmed / not reproducible / out of scope, plus a triage severity |
| Within **30 days** for high/critical | Fix developed and released, or a documented mitigation if a full fix is not yet possible |
| Within **90 days** for medium/low | Fix shipped in a normal release |

If we do not meet a stated deadline, we will tell you why and give a revised one. We will not silently sit on reports.

---

## Disclosure policy

PhantomKey follows **coordinated disclosure**:

1. We work with the reporter privately to confirm and fix the issue.
2. A fixed release is published.
3. Within **7 days** of the fix release, we publish a security advisory describing the issue, the impact, and credit to the reporter (unless they request otherwise).
4. Reporters are asked to refrain from public disclosure until the advisory is published.

If a vulnerability is being actively exploited in the wild, the timeline compresses — we will publish mitigations and advisories as fast as we can verify them.

---

## Scope

### In scope

- The PhantomKey vault, CLI, and MCP server in this repository.
- The encryption, key derivation, and recovery mechanisms.
- The blind-injection executor and response sanitizer.
- The audit log integrity guarantees.
- The MCP tool surface and any way an agent could escalate beyond intended boundaries.
- Supply-chain integrity of published artifacts (PyPI wheel, GitHub release binaries).

### Out of scope

- **Vulnerabilities in dependencies** that are not exploitable in PhantomKey's actual usage. (Report these upstream; we will pick up the fixed version on the normal release cycle.)
- **Social engineering** of the project owner or contributors.
- **Physical attacks** on your local machine, including cold-boot attacks.
- **Side-channel attacks requiring local kernel privileges.** A root-level attacker on the host machine can read the unlocked vault from process memory; this is a documented limitation, not a vulnerability.
- **Denial of service** against your own local vault.
- **The general fact that an agent with access to PhantomKey can use your real credentials to call APIs.** PhantomKey hides the *value* of secrets from the LLM, not the *capability* to use them. Agents you grant access to can still take actions with those credentials. Use the access-control features (when shipped) and your own agent sandboxing.
- **Vulnerabilities in third-party MCP clients** (Claude Desktop, Cursor, Cline, etc.). Report those to their respective vendors.

If you are unsure whether something is in scope, **report it** — we would rather decline an out-of-scope report than miss a real one.

---

## Security model summary

For the full threat model, see [`docs/threat-model.md`](docs/threat-model.md). High-level:

- **Vault at rest:** AES-256-GCM with a Scrypt-derived key from your master password. The vault file is integrity-protected.
- **Vault in memory:** unlocked vault keys live in process memory while the CLI or MCP server is running. A root-level attacker on the host machine can extract them. We do not currently use OS-level memory protection (e.g., `mlock`, secure enclaves); this is on the roadmap.
- **Recovery:** vault is recoverable with a 12-word phrase set at init time. Recovery phrase is shown once and never stored. A vault initialized with `--no-recovery` is unrecoverable on master password loss, by design.
- **Blind injection:** placeholders in templates (`{{cred.name.field}}`) are resolved by the executor, not the agent. The executor performs the HTTP request itself and sanitizes the response of any secret values before returning it.
- **MCP boundary:** the MCP server exposes seven tools; six are metadata-only and one (`phantomkey_exec`) is the only path for a secret to leave the vault, and only inside an outbound HTTP request — never to the agent.
- **Audit log:** every credential read, write, and exec is logged to a local append-only log.

---

## Past advisories

None yet. As advisories are published, they will be listed here and at <https://github.com/ritviksalim/phantomkey/security/advisories>.

---

## Acknowledgements

We credit researchers who report valid security issues, with permission. (Hall of fame to be added with the first valid report.)

---

## Bug bounty

PhantomKey does not currently run a paid bug bounty program. As the project matures and the cloud product launches, a bounty program may be introduced — if so, it will be announced here.
