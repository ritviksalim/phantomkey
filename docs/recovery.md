# Vault Recovery

Last updated: 2026-05-28

PhantomKey vaults are encrypted with a key derived from your master password using Scrypt. If you forget the master password, the encryption key cannot be reconstructed from the vault file alone — there is no master key escrow, no support backdoor, and no cloud copy. The **recovery phrase** (or recovery key) is the only path back into a vault whose master password has been lost.

This document covers how recovery works, how to use it, what it does not protect against, and how to store the recovery secret safely.

## The 12-word recovery phrase

When you run `phantomkey init` without `--no-recovery`, PhantomKey generates a 12-word phrase, displays it exactly once, and asks you to confirm three randomly chosen words to prove you wrote it down. The phrase is the default recovery strategy (`PhraseRecovery`).

Internally, the phrase unlocks a separately-encrypted copy of the vault's master encryption key. When you recover, PhantomKey uses the phrase to decrypt that copy, then re-encrypts it under a new master password you choose.

### Restoring on a new machine

1. [Install PhantomKey](install.md) on the new machine.
2. Copy your vault file (`~/.phantomkey/vault.pk` by default, or whatever path `PHANTOMKEY_VAULT_DIR` pointed to) to the same location on the new machine. The vault file is encrypted — it is safe to move over any channel where you trust the integrity of the file, but treat it like any encrypted backup.
3. Run:

   ```bash
   phantomkey recover
   ```

4. When prompted, enter your 12-word recovery phrase, then set a new master password. PhantomKey re-encrypts the vault's master key under the new password.
5. Verify:

   ```bash
   phantomkey status
   ```

> The CLI command is `phantomkey recover`, not `phantomkey init --restore`. `init` is for creating a new vault; `recover` is for resetting the master password on an existing vault file.

If the vault file is missing on the new machine, `phantomkey recover` will refuse to run — you need the encrypted vault file **and** the recovery phrase. The phrase by itself does not contain your credentials.

## The recovery-key alternative

If you would rather not memorize or transcribe a 12-word phrase, PhantomKey supports a `KeyRecovery` strategy that uses a single long random recovery key instead. The flow is otherwise identical — `phantomkey recover` detects which strategy the vault was created with and prompts for the matching input.

> **TODO:** Confirm with maintainer — the exact CLI flag or interactive prompt for selecting `KeyRecovery` at `phantomkey init` time. The strategy is implemented in `phantomkey.vault.recovery.KeyRecovery` and is dispatched correctly during `phantomkey recover`, but the documented `init` flow only shows the default phrase strategy.

## What you CAN'T recover

Be honest with yourself about the failure modes before you start storing real credentials:

- **Lost master password + lost recovery phrase = unrecoverable vault.** The vault file is AES-256-GCM ciphertext. Without one of the two unlock paths, the credentials inside it are gone. PhantomKey cannot reset, override, or regenerate them.
- **Vaults created with `--no-recovery` cannot be recovered at all.** If you initialized with `phantomkey init --no-recovery`, the recovery phrase was never generated and there is no second unlock path. Losing the master password means losing the vault.
- **There is no cloud copy.** PhantomKey v0.1 is local-only. Nothing about your vault, master password, or recovery phrase is ever transmitted to PhantomKey servers or any third party.
- **There is no support backdoor.** The maintainers cannot help you recover a vault. They do not have your master password, your recovery phrase, or any escrow copy of your encryption key. A request for "support recovery" is a phishing attempt — refuse it.
- **A corrupted vault file is not recoverable from the phrase alone.** The recovery phrase unlocks the master key; it does not reconstruct credential contents. Back up the vault file itself separately from the recovery phrase.

If any of these scenarios would be catastrophic for you, treat the recovery phrase with the same seriousness you would treat a hardware wallet seed phrase.

## Best practices for storing the phrase

The recovery phrase is bearer authentication: anyone who has it and has your vault file can decrypt your credentials. Store it accordingly.

**Do:**

- **Write it on paper or metal.** A paper card in a fireproof safe is a reasonable baseline. A stamped steel plate (the kind sold for cryptocurrency seed phrases) survives fire and flood.
- **Use split-secret across two physical locations.** Write words 1–6 on one card and 7–12 on another, stored in different places (home safe + safe deposit box, for example). An attacker needs both halves; a single-location disaster destroys only one.
- **Consider a hardware wallet or dedicated offline device.** Devices designed for cryptocurrency seed phrases (Ledger, Trezor, Cryptosteel) work for any 12-word phrase.
- **Store one copy with someone you trust legally**, such as in an estate-planning document with your attorney — useful for inheritance and for catastrophic personal incidents.

**Do not:**

- **Do not store the phrase in cloud notes** (Apple Notes synced to iCloud, Google Keep, Notion, Evernote, OneNote). A breach of that account compromises your vault.
- **Do not store it in another password manager**, especially one that lives on the same machine as PhantomKey. That collapses the two unlock paths into one.
- **Do not photograph it.** Photos sync to cloud backups by default and are indexed by OCR on most platforms.
- **Do not email or message it to yourself.** Mail providers retain message history; sync clients copy it to every device.
- **Do not type it into any website**, including anything claiming to be PhantomKey. PhantomKey never asks for your recovery phrase outside of the local `phantomkey recover` CLI command.

## See also

- [Install](install.md) — set up PhantomKey on a new machine before running `phantomkey recover`.
- [Quickstart](quickstart.md) — the `init` step that generates the recovery phrase.
- [Architecture](architecture.md) — how the vault, master key, and recovery key are layered.
- [Threat model](threat-model.md) — full list of what PhantomKey does and does not defend against.
- [FAQ](faq.md) — common recovery questions.
