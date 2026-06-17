"""
auto_sync.py — Hourly pull all locally-cloned Viper repos + log to telemetry.db.
Runs as Task Scheduler job: Viper\AutoSync every 60 minutes.

Usage:
    python auto_sync.py              # sync all repos
    python auto_sync.py --dry-run    # show what would be synced
    python auto_sync.py --report     # show last sync results from telemetry.db
"""
import os, sys, subprocess, sqlite3, json
from datetime import datetime

VIPER   = r"C:\Viper"
PROJS   = os.path.join(VIPER, "projects")
TELE_DB = os.path.join(VIPER, "databases", "telemetry", "telemetry.db")
LOG     = os.path.join(VIPER, "logs", f"auto-sync-{datetime.now():%Y%m%d}.log")
GIT     = r"C:\Program Files\Git\bin\git.exe"


def _log(msg):
    ts   = datetime.now().isoformat(timespec='seconds')
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _tele(results: list[dict]):
    try:
        con = sqlite3.connect(TELE_DB)
        payload = json.dumps({
            "synced": sum(1 for r in results if r["status"] == "OK"),
            "skipped": sum(1 for r in results if r["status"] == "SKIP"),
            "failed": sum(1 for r in results if r["status"] == "FAIL"),
            "repos": [r["name"] for r in results],
        })
        con.execute(
            "INSERT INTO agent_events(agent_id, event_type, payload, project) VALUES (?,?,?,?)",
            ("auto-sync", "sync-complete", payload, "Gitautoworks")
        )
        con.commit(); con.close()
    except Exception:
        pass


def sync_repo(path: str, name: str, dry: bool = False) -> dict:
    result = {"name": name, "path": path, "status": "SKIP", "detail": ""}

    if not os.path.isdir(os.path.join(path, ".git")):
        result["detail"] = "no git"
        return result

    # Check if remote exists
    r = subprocess.run([GIT, "-C", path, "remote", "get-url", "origin"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        result["detail"] = "no remote"
        return result

    if dry:
        result["status"] = "DRY"
        result["detail"] = "would pull"
        return result

    # Fetch + fast-forward pull
    r = subprocess.run(
        [GIT, "-C", path, "pull", "--ff-only", "--quiet"],
        capture_output=True, text=True, timeout=30
    )
    if r.returncode == 0:
        result["status"] = "OK"
        detail = r.stdout.strip() or "already up to date"
        result["detail"] = detail[:80]
    else:
        err = (r.stderr or r.stdout).strip()
        if "diverged" in err or "conflict" in err:
            result["status"] = "DIVERGED"
        else:
            result["status"] = "FAIL"
        result["detail"] = err[:80]

    return result


def sync_all(dry: bool = False) -> list[dict]:
    _log(f"=== AUTO-SYNC {'(DRY) ' if dry else ''}=== {datetime.now():%Y-%m-%d %H:%M}")
    results = []
    if not os.path.isdir(PROJS):
        _log(f"Projects dir not found: {PROJS}")
        return results

    for name in sorted(os.listdir(PROJS)):
        path = os.path.join(PROJS, name)
        if not os.path.isdir(path):
            continue
        r = sync_repo(path, name, dry)
        results.append(r)
        icon = {"OK": "OK", "SKIP": "--", "DRY": "~~", "FAIL": "XX", "DIVERGED": "!!"}.get(r["status"], "??")
        _log(f"  [{icon}] {name:<30} {r['detail'][:60]}")

    ok   = sum(1 for r in results if r["status"] == "OK")
    skip = sum(1 for r in results if r["status"] == "SKIP")
    fail = sum(1 for r in results if r["status"] in ("FAIL", "DIVERGED"))
    _log(f"=== DONE: {ok} synced, {skip} skipped, {fail} failed ===")

    if not dry:
        _tele(results)

    return results


def report():
    try:
        con  = sqlite3.connect(TELE_DB)
        rows = con.execute(
            "SELECT payload, created_at FROM agent_events "
            "WHERE agent_id='auto-sync' ORDER BY created_at DESC LIMIT 5"
        ).fetchall()
        con.close()
        if not rows:
            print("No sync history found.")
            return
        print(f"\n=== LAST {len(rows)} SYNC RUNS ===\n")
        for payload, ts in rows:
            d = json.loads(payload)
            print(f"  [{ts[:19]}] synced={d.get('synced',0)} skipped={d.get('skipped',0)} failed={d.get('failed',0)}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    if "--report" in sys.argv:
        report()
    else:
        dry = "--dry-run" in sys.argv
        sync_all(dry=dry)
