# G4c - Evennia account command boundary

**Purpose:** The Ox game should not retain the stock account-level actions that bypass its world-owned population, radio or authority mechanics merely because Evennia provides them.

## Change

Replace stock `evennia.commands.default.cmdset_account.AccountCmdSet` with `commands.account_cmdsets.AccountCmdSet`. The Ox account set explicitly allows:

- `look` (out-of-character account view)
- `ic` / `ooc` (existing authenticated character puppet/unpuppet)
- `option` (account settings)
- `quit`, `password`
- `help`

Remove ordinary account command exposure for self-authoring/deleting characters, global paging/channels, global `who`, in-game Python, raw examination, and server-wide maintenance commands. Recruitment and employment, if introduced, will have world-authored identities and contractual work rather than `charcreate` self-service. Actor-to-actor ship communication must remain subject to the Ox hail, radio and local interaction boundaries.

This is a command-*availability* change, not engine deletion. Preserve Evennia's default session/unlogged-in cmdsets, account authentication, WebSocket transport, character puppet permissions, its database, and developer access via the **local** server/shell operator. The G3f captain's actual physical authority and G4b character skill values do not change.

## Verification

- Model-free account allowlist test rejects all stock self-service and administrative account actions.
- Keep character command allowlist tests from G4a.
- Keep G4b character profile persistence tests.
- Re-run real Evennia WebSocket login and six-character captain CI, and both legacy three/five-crew regressions. The human operator's local `evennia shell` and server launch commands must still function.

No further upstream engine modules should be deleted until their real dependency graph is established.
