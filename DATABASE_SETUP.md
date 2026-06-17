# MySQL Setup (with MySQL Workbench)

How to turn on the MySQL persistence that's already wired into the backend. The app does the
heavy lifting (it **auto-creates the tables**); you only need a running server, a database, and
matching credentials in `config.yaml`.

> ⚠️ **MySQL Workbench is only a GUI client — it is NOT the database server.** It connects to a
> MySQL **Server** that must be installed and running separately. On Windows the easiest path is
> the **MySQL Installer**, which installs MySQL Server *and* Workbench together.

---

## Step 1 — Confirm MySQL Server is running

- Windows: open **Services** and check that `MySQL80` (or similar) is *Running*, **or** open
  Workbench and confirm the local connection (usually `localhost:3306`) opens without error.
- If Workbench opens the connection, the server is up. Note the **port** (default `3306`) and the
  **username** you log in with (default `root`).

## Step 2 — Create the database (schema)

In Workbench, open a SQL tab on your local connection and run:

```sql
CREATE DATABASE IF NOT EXISTS eyedtrack_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

That's all the SQL you need — **do not create tables by hand.** On first connect the app creates
them automatically: `monitoring_sessions`, `driver_behaviors`, `alert_logs`, `performance_metrics`.

## Step 3 — (Recommended) create a dedicated user

Using `root` works, but a scoped user is cleaner:

```sql
CREATE USER 'eyedtrack'@'localhost' IDENTIFIED BY 'ChangeMe123!';
GRANT ALL PRIVILEGES ON eyedtrack_db.* TO 'eyedtrack'@'localhost';
FLUSH PRIVILEGES;
```

## Step 4 — Match credentials in `config.yaml`

Edit the `integration.database` block so it matches how you log into Workbench:

```yaml
integration:
  database:
    enabled: true            # <-- flip this to true
    type: "mysql"
    host: "localhost"
    port: 3306               # match your server's port
    database: "eyedtrack_db"
    username: "eyedtrack_app" # or "root"
    password: ""             # leave blank — provide it via the env var below (keeps secrets out of git)
    pool_size: 5
    max_overflow: 10
    pool_timeout: 30
    pool_recycle: 3600
```

The app builds the SQLAlchemy URL `mysql+pymysql://username:password@host:port/database` from these
values — the **same server** Workbench connects to.

### Keep the password out of `config.yaml` (recommended)

`config.yaml` is tracked by git, so the password is read from an **environment variable** instead.
`config_loader` checks these and any that are set override the file:

| Env var | Overrides |
|---------|-----------|
| `EYEDTRACK_DB_PASSWORD` | `password` |
| `EYEDTRACK_DB_USER` | `username` |
| `EYEDTRACK_DB_HOST` | `host` |
| `EYEDTRACK_DB_PORT` | `port` |
| `EYEDTRACK_DB_NAME` | `database` |

Set the password in PowerShell **before** running the server:

```powershell
# Just this terminal session:
$env:EYEDTRACK_DB_PASSWORD = "xSheele11"

# OR persist for future terminals (re-open the terminal afterward):
setx EYEDTRACK_DB_PASSWORD "xSheele11"
```

> With `$env:`, the variable lives only in the current window — run `main.py` in that same window.
> With `setx`, it applies to **new** windows only, not the one you typed it in.

## Step 5 — Install the Python dependencies

```bash
py -3.14 -m pip install -r requirements.txt
```

This pulls in `SQLAlchemy` and `PyMySQL` (the `mysql+pymysql` driver).

## Step 6 — Run and confirm

```bash
py -3.14 main.py
```

On startup, look for:

- ✅ `MySQL persistence enabled (db session session_YYYYMMDD_HHMMSS)` → connected.
- ⚠️ `MySQL persistence disabled — DatabaseManager init failed: <reason>` → the server still runs
  on file logging only; **read the reason** (wrong password, server down, db missing, auth plugin).

## Step 7 — Verify the data lands

In Workbench, refresh the **SCHEMAS** panel → `eyedtrack_db` now has four tables. Then trigger a
risky behavior (drowsy / yawn / look away) and query:

```sql
SELECT timestamp, behavior, confidence, ear, mar, head_pose
FROM eyedtrack_db.driver_behaviors
ORDER BY timestamp DESC
LIMIT 50;
```

Or hit the new REST endpoints (served by `database_integration.py`):

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/db/health` | Is persistence active? Which session is logging? |
| GET | `/api/db/behaviors/recent?hours=24&limit=100` | Recent behavior rows |
| GET | `/api/db/dashboard/summary?hours=24` | Aggregated risk score + breakdown |
| GET | `/api/db/session/summary` | Counts for the current monitoring session |
| POST | `/api/db/cleanup?days=30` | Delete rows older than N days |

---

## Common gotchas

- **"Workbench connects but the app doesn't."** They must use the *same* host / port / user /
  password. If Workbench uses a non-default port or a different account, mirror it in `config.yaml`.
- **MySQL 8 auth plugin error** (`caching_sha2_password` / "RSA public key" / auth failures):
  either `py -3.14 -m pip install cryptography`, **or** switch the user to native auth:
  ```sql
  ALTER USER 'eyedtrack'@'localhost' IDENTIFIED WITH mysql_native_password BY 'ChangeMe123!';
  FLUSH PRIVILEGES;
  ```
- **Empty password.** Only set `password: ""` if the account genuinely has no password. Fresh MySQL 8
  installs almost always set a root password during setup.
- **`eyedtrack.db` at the repo root is a leftover SQLite file — ignore/delete it.** This stack uses
  MySQL, not SQLite.
- **Row volume.** Logging is per-frame while a (debounced) behavior persists, so a long drowsy
  episode writes many rows — expected for an audit trail. Use `/api/db/cleanup` to prune later.
- **Keep secrets out of git.** `config.yaml` is tracked, so avoid committing a real DB password.
  Consider a local-only override or environment variable before going to production.
