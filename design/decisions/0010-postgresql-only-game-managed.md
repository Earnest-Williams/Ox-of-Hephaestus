# ADR 0010 — PostgreSQL only, run by the game

**Status:** Accepted (1 November 2026).

## Context

Ox is a single-player game. An agent system will reach Evennia through one
API, and unused code will be removed. Until now the world ran on SQLite
locally and in 126 of 127 Ox workflows, while the guarantees that keep the
world consistent were written for, and tested only on, PostgreSQL:

- the journal takes `pg_advisory_xact_lock` so event sequence numbers follow
  commit order (PR #82), with the P-01 → captain ticket → journal lock order
  of PR #83;
- 56 `select_for_update` call sites rely on real row locks, which SQLite
  ignores;
- Evennia serves Django views from a thread pool of up to 20 threads, so an
  HTTP API inside Evennia writes concurrently with the physics tick, the case
  Evennia's documentation says SQLite handles badly.

MySQL/MariaDB was never tested by Ox after ADR 0004, would silently skip the
journal lock, and offers Ox nothing. A lighter "drop-in" was examined: PGlite
is single-connection (its multiplexer is explicitly not guaranteed), and the
alternatives are either heavier (distributed PostgreSQL-compatible engines),
non-transactional (analytical engines) or not PostgreSQL (SQLite
descendants). Measured on PostgreSQL 18.6 tuned for one player: about 19 MB
of memory when idle, a 41 MB empty data folder and a 0.2 s restart.

## Decision

1. **PostgreSQL is the only supported database.** SQLite and MySQL/MariaDB
   testing is removed. A Django system check (`ox.E001`) and the journal
   refuse any other backend instead of silently losing guarantees.
2. **The game runs its own private cluster.** There is no service to
   install, no role or password to create and no config to edit:
   - data in `game/server/pgdata/`, socket in `game/server/pgdata.sock/`
     (a short temporary path if that would exceed the Unix socket limit),
     log in `game/server/pgdata.log`;
   - `listen_addresses = ''`: nothing listens on the network; local
     password-free authentication, so only the owning OS user connects;
   - single-player tuning: 40 connections, 16 MB shared buffers,
     `wal_level = minimal`, no WAL senders.
3. **Lifecycle.** The Django backend `server.conf.oxpg` connects first and,
   only if refused, initialises the folder, starts the server and creates
   the database, then retries once. A file lock makes this safe from the
   launcher, Portal, Server and test runner at once. Evennia's cold stop
   shuts the database down after the reactor stops (Evennia writes state
   after the hook itself); a reload keeps it running.
4. **Programs.** `OX_PG_BIN`, else the system's (PATH, then Debian/Ubuntu
   and PGDG folders, highest major first), else the optional
   `embedded-postgres` wheel, run in place. One-time install on Fedora:
   `sudo dnf install postgresql-server`; no service is enabled.
5. **Versions.** A data folder opens only under the PostgreSQL major version
   that created it; otherwise startup stops with dump/restore instructions.
6. **Disposable databases.** CI probes select their own database in the same
   cluster with `OX_PG_DATABASE` (`ox_contention_ci`, `ox_g19_restart`) and
   refuse any other name. Django tests use `test_<name>`.

## Alternatives not selected

- SQLite with WAL: workable only if every write stays on Evennia's main
  thread, which the planned API would not guarantee.
- A system PostgreSQL service or container: real setup work for a
  single-player game.
- Making `embedded-postgres` the default: it pins the version, but is two
  months old, alpha and has one maintainer. It remains a supported fallback.

## Consequences

- `psycopg[binary]` is a core dependency; `settings_postgres_ci.py`, the
  `connection.vendor` branch and the inherited SQLite/MySQL CI jobs are gone.
- GitHub's Ubuntu runners already ship PostgreSQL, so workflows need no
  service container; each job initialises a fresh cluster (about 1 s).
- Fedora upgrades can move the PostgreSQL major version. Move a saved ship
  with `pg_dump` under the old version and restore under the new one, or pin
  `OX_PG_BIN`.
- Every query is a round trip, so fixture-heavy tests are slower than on
  SQLite (building the installed ship: 92,781 queries, about 3x). Test
  databases turn autovacuum off, since per-test rollbacks otherwise leave
  zero-row statistics, and installed-ship suites clone a prebuilt ship
  (`world.ship_snapshot`, `--prebuilt-ship`) instead of building it per test.
- The AI handler's per-actor SQLite evidence index is a disposable cache
  owned by the handler, not world state, and is unaffected.

## Operating

From `game/`: `python -m server.conf.oxpg status | start | stop | where`.
