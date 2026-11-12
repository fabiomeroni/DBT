"""
Backups of what the author edits in the browser (it lives only on the server).

One archive (a zip) holds everything: the dictionary, the grammar, the glossary, the references, the texts and their glosses, the images, the pages and the
settings. The author downloads it (the backup that protects against the loss of the server), and once a day, when the site is used and something has
changed, the server keeps a snapshot of the same kind in uploads/backups/snapshots (the safety net against mistakes: a deleted entry, a bad import).
Snapshots are never removed by themselves: the author can dispose of those that are a month old or more.

This module knows no web framework and no particular project: it is given the files to keep.
"""
import datetime
import hashlib
import json
import os
import re
import tempfile
import zipfile

DISPOSE_AFTER_DAYS = 30                                    # a snapshot can be disposed of once it is a month old
SNAPSHOT_RE = re.compile(r'daily-(\d{4})-(\d{2})-(\d{2})(?:-(\d{4}))?\.zip')
STATE_NAME = 'backup_state.json'
_SKIP_DIRS = {'__pycache__', '.git'}
_SKIP_FILES = {'.DS_Store', 'Thumbs.db'}


# ── which files ──────────────────────────────────────────────────────────────────────────────────
def collect(root, paths):
    """[(absolute path, name in the archive)] for the files and folders given (regular files only, no temporary file, no link). The name is the path
    from the root of the site, with /; a path outside the root goes under external/. Nothing is listed twice."""
    root = os.path.abspath(root)
    seen, out = set(), []

    def add(p):
        ap = os.path.abspath(p)
        if ap in seen or os.path.islink(ap) or not os.path.isfile(ap):
            return
        name = os.path.basename(ap)
        if name in _SKIP_FILES or name.endswith('.tmp') or name.endswith('.pyc'):
            return
        seen.add(ap)
        rel = os.path.relpath(ap, root).replace(os.sep, '/')
        out.append((ap, ('external/' + ap.lstrip('/').replace(os.sep, '/')) if rel.startswith('..') else rel))

    for p in paths:
        if not p:
            continue
        if os.path.isdir(p):
            for r, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS and not os.path.islink(os.path.join(r, d)))
                for f in sorted(files):
                    add(os.path.join(r, f))
        else:
            add(p)
    return sorted(out, key=lambda x: x[1])


def signature(files):
    """A short fingerprint of the state of the files (names, sizes, dates of change): it changes when anything is edited, added or removed."""
    h = hashlib.sha1()
    for ap, name in files:
        try:
            st = os.stat(ap)
        except OSError:
            continue
        h.update(f'{name}\0{st.st_size}\0{st.st_mtime_ns}\n'.encode('utf-8'))
    return h.hexdigest()


# ── the archive ──────────────────────────────────────────────────────────────────────────────────
def _readme(meta, count, total):
    return (f"DBT backup: {meta.get('project', '')}\n"
            f"Made on {meta['when']} (server time), as a {meta['kind']}.\n"
            f"{count} files, {total / 1024:.0f} KB before compression.\n\n"
            "WHAT IS IN IT\n"
            "  project/  the dictionary, the grammar, the glossary, the references, the texts and their glosses, the images, the pages, the project settings\n"
            "  uploads/  the dictionary that was uploaded or imported, and the dictionary settings\n"
            "  manifest.json  every file with its size and its SHA-256, to check that nothing is damaged\n\n"
            "TO RESTORE\n"
            "  1. Keep a copy of the folders `project` and `uploads` of the server as they are now.\n"
            "  2. Copy the `project` and `uploads` folders of this archive over those of the server (the files of the archive replace those of the same name).\n"
            "  3. Restart the app.\n"
            "  To bring back only one thing (one grammar section, one glossary entry, the dictionary), copy just that file.\n")


def write_archive(fileobj, files, meta):
    """Write the zip into `fileobj`. meta = {'project', 'kind', 'when'}. Returns the manifest: [{'path', 'bytes', 'sha256'}]."""
    top = 'dbt-backup-' + meta['when'][:10] + '/'
    manifest, total = [], 0
    with zipfile.ZipFile(fileobj, 'w', zipfile.ZIP_DEFLATED) as z:
        for ap, name in files:
            try:
                with open(ap, 'rb') as f:
                    data = f.read()
            except OSError:
                continue                                                   # a file that went away while the archive was made
            z.writestr(top + name, data)
            manifest.append({'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
            total += len(data)
        z.writestr(top + 'manifest.json', json.dumps({'made': meta['when'], 'kind': meta['kind'], 'project': meta.get('project', ''), 'files': manifest}, ensure_ascii=False, indent=1))
        z.writestr(top + 'BACKUP-README.txt', _readme(meta, len(manifest), total))
    return manifest


# ── the state: when the last download and the last snapshot were made, and what the files looked like then ──
def load_state(uploads):
    try:
        with open(os.path.join(uploads, STATE_NAME), encoding='utf-8') as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(uploads, state):
    os.makedirs(uploads, exist_ok=True)
    tmp = os.path.join(uploads, STATE_NAME + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=1)
    os.replace(tmp, os.path.join(uploads, STATE_NAME))


def _parse(iso):
    try:
        return datetime.datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None


def status(state, sig, now):
    """What the reminder beside the Backup button says: {'lastBackup', 'daysAgo', 'changedSince', 'level'}. Level: ok (backed up, or nothing changed since),
    due (edits since, a week or more), old (edits since, a month or more), never (nothing was ever downloaded)."""
    last = _parse(state.get('lastDownloadAt'))
    if last is None:
        return {'lastBackup': None, 'daysAgo': None, 'changedSince': True, 'level': 'never'}
    days = max(0, (now.date() - last.date()).days)
    changed = state.get('lastDownloadSig') != sig
    level = 'ok' if not changed else ('old' if days >= DISPOSE_AFTER_DAYS else 'due' if days >= 7 else 'ok')
    return {'lastBackup': last.isoformat(timespec='seconds'), 'daysAgo': days, 'changedSince': changed, 'level': level}


# ── the daily snapshots ──────────────────────────────────────────────────────────────────────────
def snapshot_dir(uploads):
    return os.path.join(uploads, 'backups', 'snapshots')


def due(state, sig, now):
    """A snapshot is due if the last one is more than a day old and something changed since it (or there is none yet)."""
    last = _parse(state.get('lastSnapshotAt'))
    if last is not None and (now - last) < datetime.timedelta(hours=24):
        return False
    return state.get('lastSnapshotSig') != sig


def snapshot_name(uploads, now):
    d = snapshot_dir(uploads)
    name = f"daily-{now.strftime('%Y-%m-%d')}.zip"
    return name if not os.path.exists(os.path.join(d, name)) else f"daily-{now.strftime('%Y-%m-%d-%H%M')}.zip"


def take_snapshot(uploads, files, meta, now):
    """Write a snapshot (the same archive as the download) and return its name."""
    d = snapshot_dir(uploads)
    os.makedirs(d, exist_ok=True)
    name = snapshot_name(uploads, now)
    fd, tmp = tempfile.mkstemp(prefix='.snap-', suffix='.tmp', dir=d)
    try:
        with os.fdopen(fd, 'wb') as f:
            write_archive(f, files, dict(meta, kind='daily snapshot', when=now.isoformat(timespec='seconds')))
        os.replace(tmp, os.path.join(d, name))
    except BaseException:
        try: os.remove(tmp)
        except OSError: pass
        raise
    return name


def _snapshot_date(name):
    m = SNAPSHOT_RE.fullmatch(name)
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def list_snapshots(uploads, now):
    """[{'name', 'date', 'bytes', 'ageDays', 'eligible'}], newest first. The age is that of the date in the name; a snapshot can be disposed of
    (eligible) once it is DISPOSE_AFTER_DAYS days old. Files that are not snapshots are ignored."""
    d = snapshot_dir(uploads)
    out = []
    try:
        names = os.listdir(d)
    except OSError:
        return out
    for n in names:
        day = _snapshot_date(n)
        p = os.path.join(d, n)
        if day is None or not os.path.isfile(p):
            continue
        age = (now.date() - day).days
        out.append({'name': n, 'date': day.isoformat(), 'bytes': os.path.getsize(p), 'ageDays': age, 'eligible': age >= DISPOSE_AFTER_DAYS})
    out.sort(key=lambda s: (s['date'], SNAPSHOT_RE.fullmatch(s['name']).group(4) or '0000'), reverse=True)        # the day, then the hour of a second snapshot
    return out


def dispose(uploads, names, now):
    """Remove snapshots that are a month old or more. Returns (removed [{'name','bytes'}], refused [{'name','reason'}]). Only names of real snapshots are
    accepted, and the age is judged here, never taken from the caller."""
    have = {s['name']: s for s in list_snapshots(uploads, now)}
    removed, refused = [], []
    for n in names:
        s = have.get(n) if isinstance(n, str) else None
        if s is None:
            refused.append({'name': str(n)[:80], 'reason': 'not a snapshot'}); continue
        if not s['eligible']:
            refused.append({'name': n, 'reason': 'not a month old yet'}); continue
        try:
            os.remove(os.path.join(snapshot_dir(uploads), n))
            removed.append({'name': n, 'bytes': s['bytes']})
        except OSError as e:
            refused.append({'name': n, 'reason': str(e)})
    return removed, refused
