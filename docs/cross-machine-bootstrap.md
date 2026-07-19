# Cross-machine bootstrap

## New machine

1. Install Git, `uv`, and Codex CLI 0.144.5 or newer.
2. Clone this repository to a stable path.
3. Choose an existing host overlay or create one:

   ```bash
   ./bin/codex-harness host init laptop
   git add sources/config/hosts/laptop.toml
   git commit -m "config: add laptop Codex overlay"
   ```

4. Preview and install:

   ```bash
   ./install.sh --host laptop
   ```

5. Ensure `$HOME/.local/bin` is on `PATH`, then restart Codex so global guidance, profiles, agents, rules, and skills are rediscovered.

## Tracked and local settings

Commit `sources/config/hosts/NAME.toml` when a non-secret preference should follow that machine identity across rebuilds. Put machine-local, non-secret values in `sources/config/hosts/NAME.local.toml`; Git ignores these files. Never put credentials in either layer.

The repository path is not embedded in the manifest. Every source is resolved relative to the current clone, so another machine can use a different clone location.

## Updates and rollback

Use the safe update sequence in `docs/operations.md`. Each apply creates a receipt automatically. If a new revision behaves incorrectly, restore the reported snapshot ID:

```bash
codex-harness restore SNAPSHOT_ID --yes
```

If the repository is being removed from the machine, run `codex-harness unlink --yes` first. This keeps runtime-owned Codex state and unmanaged skills intact.
