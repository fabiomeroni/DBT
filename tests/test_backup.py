"""
Direct tests of backup.py (no server): which files are kept, the fingerprint of their state, the archive (manifest, readme), the reminder, when a snapshot
is due, and the disposal of snapshots that are a month old.   Run alone with:  python tests/test_backup.py
"""
import datetime as dt
import hashlib
import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backup as B

ok = bad = 0
def check(name, got, want):
    global ok, bad
    if got == want: ok += 1
    else:
        bad += 1; print(f"✗ {name}\n    got : {got!r}\n    want: {want!r}")

NOW = dt.datetime(2026, 11, 13, 14, 30, 0)
with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    def w(rel, text='x', b=False):
        p = root / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(text if b else text.encode('utf-8')); return p
    w('project/dictionary.xml', '<d/>'); w('project/grammar/s1.md', '## S1'); w('project/glossary/predicate.md', '## P'); w('project/texts/glosses/a.json', '{}')
    w('project/images/map.png', b'\x89PNG\x00\x01', b=True); w('project/references.json', '[]'); w('uploads/dictionary.xml', '<up/>'); w('uploads/dictionary_settings.json', '{}')
    w('uploads/backups/dictionary-old.xml', 'old'); w('uploads/backups/snapshots/daily-2026-01-01.zip', 'zip'); w('uploads/import/t.xml', 'tmp'); w('uploads/backup_state.json', '{}')
    w('project/grammar/s2.md.tmp', 'half'); w('project/.DS_Store', 'junk'); w('project/__pycache__/x.pyc', 'junk')
    os.symlink(root / 'project' / 'references.json', root / 'project' / 'link.json')
    paths = [str(root / 'project'), str(root / 'uploads' / 'dictionary.xml'), str(root / 'uploads' / 'dictionary_settings.json'), str(root / 'project' / 'references.json')]
    files = B.collect(str(root), paths)
    names = [n for _p, n in files]
    check('the files kept are the project folder and the uploaded dictionary and settings: with their path from the root of the site, sorted, none twice', names, ['project/dictionary.xml', 'project/glossary/predicate.md', 'project/grammar/s1.md', 'project/images/map.png', 'project/references.json', 'project/texts/glosses/a.json', 'uploads/dictionary.xml', 'uploads/dictionary_settings.json'])
    check('the backups themselves, the temporary import, the state, temporary and system files and links are not kept', [n for n in names if 'backups' in n or 'import' in n or 'state' in n or n.endswith(('.tmp', '.pyc', '.DS_Store', 'link.json'))], [])
    out = B.collect(str(root), [str(Path(d).parent / 'elsewhere-x')]) ; check('a path that does not exist keeps nothing', out, [])
    sig1 = B.signature(files)
    check('the fingerprint is the same while nothing changes', B.signature(B.collect(str(root), paths)), sig1)
    (root / 'project' / 'grammar' / 's1.md').write_text('## S1 changed, longer', encoding='utf-8')
    check('…and changes when a file is edited', B.signature(B.collect(str(root), paths)) != sig1, True)
    sig2 = B.signature(B.collect(str(root), paths)); w('project/glossary/new.md', '## N')
    check('…when a file is added', B.signature(B.collect(str(root), paths)) != sig2, True)
    # ── the archive ──
    buf = io.BytesIO(); files = B.collect(str(root), paths)
    man = B.write_archive(buf, files, {'project': 'Test project', 'kind': 'download', 'when': '2026-11-13T14:30:00'})
    z = zipfile.ZipFile(io.BytesIO(buf.getvalue())); zn = z.namelist(); top = 'dbt-backup-2026-11-13/'
    check('the archive unpacks into one folder named with the date, with every file, a manifest and a readme', all(n.startswith(top) for n in zn) and top + 'project/grammar/s1.md' in zn and top + 'uploads/dictionary.xml' in zn and top + 'manifest.json' in zn and top + 'BACKUP-README.txt' in zn and z.testzip() is None, True)
    mf = json.loads(z.read(top + 'manifest.json'))
    check('the manifest lists each file with its size and its SHA-256, and they are right', all(e['sha256'] == hashlib.sha256(z.read(top + e['path'])).hexdigest() and e['bytes'] == len(z.read(top + e['path'])) for e in mf['files']) and len(mf['files']) == len(files) == len(man), True)
    check('the contents are those of the files (a binary image too)', z.read(top + 'project/images/map.png') == b'\x89PNG\x00\x01' and z.read(top + 'project/grammar/s1.md').decode('utf-8') == '## S1 changed, longer', True)
    rd = z.read(top + 'BACKUP-README.txt').decode('utf-8')
    check('the readme says what it is, when, and how to restore', 'Test project' in rd and '2026-11-13' in rd and 'TO RESTORE' in rd and 'Restart the app' in rd and 'download' in rd, True)
    # ── the reminder ──
    sig = 'abc'
    check('nothing downloaded yet: never', B.status({}, sig, NOW), {'lastBackup': None, 'daysAgo': None, 'changedSince': True, 'level': 'never'})
    st = lambda days, s='abc': {'lastDownloadAt': (NOW - dt.timedelta(days=days)).isoformat(), 'lastDownloadSig': s}
    check('downloaded today, or nothing changed since: ok, whatever the age', (B.status(st(0), sig, NOW)['level'], B.status(st(90, 'abc'), 'abc', NOW)['level'], B.status(st(90, 'abc'), 'abc', NOW)['changedSince']), ('ok', 'ok', False))
    check('edits since: ok for less than a week, due from a week, old from a month', [B.status(st(d_, 'old'), 'new', NOW)['level'] for d_ in (0, 6, 7, 29, 30, 200)], ['ok', 'ok', 'due', 'due', 'old', 'old'])
    check('the age is in days of the calendar (yesterday evening is 1 day)', B.status({'lastDownloadAt': dt.datetime(2026, 11, 12, 23, 59).isoformat(), 'lastDownloadSig': 'x'}, 'y', NOW)['daysAgo'], 1)
    check('a damaged state is the same as no state', B.status({'lastDownloadAt': 'garbage'}, sig, NOW)['level'], 'never')
    # ── when a snapshot is due ──
    check('a snapshot is due when there is none and there is data', B.due({}, 'a', NOW), True)
    check('not due within 24 hours of the last one, even if things changed', B.due({'lastSnapshotAt': (NOW - dt.timedelta(hours=23)).isoformat(), 'lastSnapshotSig': 'old'}, 'new', NOW), False)
    check('not due after a day if nothing changed since the last one: the day is skipped', B.due({'lastSnapshotAt': (NOW - dt.timedelta(days=3)).isoformat(), 'lastSnapshotSig': 'same'}, 'same', NOW), False)
    check('due after a day if something changed', B.due({'lastSnapshotAt': (NOW - dt.timedelta(hours=25)).isoformat(), 'lastSnapshotSig': 'old'}, 'new', NOW), True)
    # ── taking and listing snapshots ──
    up = str(root / 'uploads')
    n1 = B.take_snapshot(up, files, {'project': 'T'}, NOW); n2 = B.take_snapshot(up, files, {'project': 'T'}, NOW)
    check('a snapshot is named with its date; a second one on the same day gets the hour and minute (nothing is overwritten)', (n1, n2), ('daily-2026-11-13.zip', 'daily-2026-11-13-1430.zip'))
    check('a snapshot is the same archive as the download, marked as a daily snapshot, and no temporary file is left', zipfile.ZipFile(os.path.join(up, 'backups', 'snapshots', n1)).read(top + 'BACKUP-README.txt').decode().count('daily snapshot') == 1 and not [f for f in os.listdir(os.path.join(up, 'backups', 'snapshots')) if f.endswith('.tmp')], True)
    sd = os.path.join(up, 'backups', 'snapshots')
    for name in ('daily-2026-10-14.zip', 'daily-2026-10-15.zip', 'daily-2026-09-01.zip', 'daily-2026-13-45.zip', 'readme.txt', 'daily-2026-10-01-extra.zip'):
        Path(sd, name).write_bytes(b'x' * 100)
    ls = B.list_snapshots(up, NOW)
    check('the snapshots are listed newest first, by the date in their name (the day, then the hour of a second one)', [s['name'] for s in ls][:2], ['daily-2026-11-13-1430.zip', 'daily-2026-11-13.zip'])
    check('what is not a snapshot (another file, an impossible date, a name with something added) is ignored: exactly these are listed', sorted(s['name'] for s in ls), sorted(['daily-2026-11-13.zip', 'daily-2026-11-13-1430.zip', 'daily-2026-10-15.zip', 'daily-2026-10-14.zip', 'daily-2026-09-01.zip', 'daily-2026-01-01.zip']))
    el = {s['name']: (s['ageDays'], s['eligible']) for s in ls}
    check('a snapshot can be disposed of from its 30th day: 29 days old no, 30 days old yes, older yes, new no', (el['daily-2026-10-15.zip'], el['daily-2026-10-14.zip'], el['daily-2026-09-01.zip'], el['daily-2026-11-13.zip']), ((29, False), (30, True), (73, True), (0, False)))
    removed, refused = B.dispose(up, ['daily-2026-10-15.zip', 'daily-2026-10-14.zip', '../state.json', '..\\x', 'readme.txt', 'nonesuch.zip', 5, 'daily-2026-13-45.zip'], NOW)
    check('disposing removes only the snapshots that are a month old: a younger one, a path, another file, a name that does not exist or is not a name are refused with the reason', ([r['name'] for r in removed], {r['name']: r['reason'] for r in refused}), (['daily-2026-10-14.zip'], {'daily-2026-10-15.zip': 'not a month old yet', '../state.json': 'not a snapshot', '..\\x': 'not a snapshot', 'readme.txt': 'not a snapshot', 'nonesuch.zip': 'not a snapshot', '5': 'not a snapshot', 'daily-2026-13-45.zip': 'not a snapshot'}))
    check('…and what was refused is untouched, and the file of the snapshot removed is gone', (os.path.exists(os.path.join(sd, 'daily-2026-10-15.zip')), os.path.exists(os.path.join(sd, 'daily-2026-10-14.zip')), os.path.exists(os.path.join(sd, 'readme.txt')), os.path.exists(os.path.join(up, 'backup_state.json'))), (True, False, True, True))
    B.save_state(up, {'lastDownloadAt': 'x', 'lastDownloadSig': 'y'})
    check('the state is kept in uploads and read back; a state that is not there or is damaged is empty', (B.load_state(up), B.load_state(str(root / 'nowhere'))), ({'lastDownloadAt': 'x', 'lastDownloadSig': 'y'}, {}))
    Path(up, B.STATE_NAME).write_text('{not json', encoding='utf-8'); check('a damaged state file does not break anything', B.load_state(up), {})
print(f"\n{ok} passed, {bad} failed")
sys.exit(1 if bad else 0)
