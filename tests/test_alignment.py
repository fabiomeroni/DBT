"""
Direct tests of alignment.js, the rules for editing the alignment of a sentence (insert a column anywhere, delete one, move one word of one language
to another place and shift the words that follow). The code is run by node: no page.   Run alone with:  python tests/test_alignment.py
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ok = bad = 0
def check(name, got, want):
    global ok, bad
    if got == want: ok += 1
    else:
        bad += 1; print(f"✗ {name}\n    got : {got!r}\n    want: {want!r}")

def run(calls):
    """calls: [(function, state, args...)] -> the results and the states, from node."""
    script = "const A = require(%s); const out = []; for (const [fn, st, ...args] of JSON.parse(process.argv[1])) { const r = A[fn](st, ...args); out.push({r, st}); } console.log(JSON.stringify(out));" % json.dumps(str(ROOT / "alignment.js"))
    p = subprocess.run(["node", "-e", script, json.dumps(calls)], capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        print(p.stderr[:400]); sys.exit(2)
    return json.loads(p.stdout)

def chain(state, calls):
    """The same state goes through all the calls, one after the other: (the results, the final state)."""
    script = "const A = require(%s); const st = JSON.parse(process.argv[1]); const r = []; for (const [fn, ...args] of JSON.parse(process.argv[2])) r.push(A[fn](st, ...args)); console.log(JSON.stringify({r, st}));" % json.dumps(str(ROOT / "alignment.js"))
    p = subprocess.run(["node", "-e", script, json.dumps(state), json.dumps(calls)], capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        print(p.stderr[:400]); sys.exit(2)
    o = json.loads(p.stdout); return o["r"], o["st"]

S = lambda a, b=None, g=None: {"tokens": {"num": list(a), **({"drg": list(b)} if b is not None else {})}, "glosses": list(g if g is not None else [""] * len(a)), "n": len(a)}
def mv(row, frm, to, other=None, gl=None):
    st = S(row, other, gl); r, s = run([["moveToken", st, "num", frm, to]])[0]["r"], run([["moveToken", S(row, other, gl), "num", frm, to]])[0]["st"]
    return r, s

# ── moving a word ──
r, s = mv(["a", "b", "", "d"], 0, 2)
check('a word dropped on an empty place goes there and leaves its old place empty', (r["moved"], s["tokens"]["num"], s["n"]), (True, ["", "b", "a", "d"], 4))
r, s = mv(["a", "b", "c", ""], 0, 1)
r, s = mv(["a", "b", "c", "d"], 3, 1)
check('moving a word from the right to an occupied place: the words from there on go right until the place the word left, which takes up the shift (no column)', (r, s["tokens"]["num"], s["n"]), ({"moved": True, "shifted": 2, "created": False}, ["a", "d", "b", "c"], 4))
r, s = mv(["a", "b", "c", "d"], 0, 2)
check('moving a word to the right onto an occupied place at the end of a full row: what follows goes right and a column is created for it', (r, s["tokens"]["num"], s["n"]), ({"moved": True, "shifted": 2, "created": True}, ["", "b", "a", "c", "d"], 5))
r, s = mv(["a", "b", "", "d"], 3, 0)
check('the shift goes on only as far as the first empty place: after it nothing moves', (r["shifted"], s["tokens"]["num"]), (2, ["d", "a", "b", ""]))
r, s = mv(["a", "b", "", "d", "e"], 4, 0)
check('…and what is after the empty place that took up the shift does not move; a column is created only if no empty place is found', (r["created"], s["tokens"]["num"], s["n"]), (False, ["e", "a", "b", "d", ""], 5))
r, s = mv(["a", "b", "c"], 2, 0)
check('a word moved to the first place of a row where it was the last: the others go right into the place it left', (r, s["tokens"]["num"]), ({"moved": True, "shifted": 2, "created": False}, ["c", "a", "b"]))
r, s = mv(["a", "b", "c"], 0, 2)
check('the last place of a full row: the word that was there is pushed into a new column', (r["created"], s["tokens"]["num"]), (True, ["", "b", "a", "c"]))
r, s = mv(["a", "b", "c"], 0, 2, other=["x", "y", "z"], gl=["G1", "G2", "G3"])
check('only that word of that language moves: the glosses and the other languages keep their places, but the new column is empty in all of them', (s["tokens"]["num"], s["tokens"]["drg"], s["glosses"], s["n"]), (["", "b", "a", "c"], ["x", "y", "z", ""], ["G1", "G2", "G3", ""], 4))
for name, (frm, to) in {'nothing': (1, 1), 'from an empty place': (2, 0), 'to a place out of the row': (0, 9), 'from a place out of the row': (7, 0), 'with no number': (None, 0), 'a negative place': (0, -1)}.items():
    r, s = mv(["a", "b", "", "d"], frm, to)
    check(f'a drop that makes no sense changes nothing ({name})', (r["moved"], s["tokens"]["num"], s["n"]), (False, ["a", "b", "", "d"], 4))
st = S(["a", "b"]); res = run([["moveToken", st, "nolang", 0, 1]])[0]
check('an unknown language is refused', (res["r"]["moved"], res["st"]["tokens"]["num"]), (False, ["a", "b"]))
r, s = mv(["a", "—", " ", "d"], 0, 1)
check('a dash or spaces is an empty place: a word dropped there just takes it', (r, s["tokens"]["num"]), ({"moved": True, "shifted": 0, "created": False}, ["", "a", " ", "d"]))
r, s = mv(["a", "b", "c", "d"], 1, 3)
r, s = mv(["a", "b", "c", "d"], 1, 3)
check('moving to the right onto the last occupied place: the word that was there is pushed into a new column', (s["tokens"]["num"], r["created"]), (["a", "", "c", "b", "d"], True))
# ── columns ──
res, fin = chain(S(["a", "b", "c"], ["x", "y", "z"], ["G1", "G2", "G3"]), [["insertColumn", 0], ["insertColumn", 2], ["insertColumn", 99], ["insertColumn", -3]])
check('a column is inserted before the first, in the middle, after the last (a place beyond the end means the end, a negative one the start); every language and the glosses get an empty place', (res, fin["tokens"]["num"], fin["tokens"]["drg"], fin["glosses"], fin["n"]), ([0, 2, 5, 0], ["", "", "a", "", "b", "c", ""], ["", "", "x", "", "y", "z", ""], ["", "", "G1", "", "G2", "G3", ""], 7))
r = run([["insertColumn", S(["a", "b", "c"], ["x", "y", "z"], ["G1", "G2", "G3"]), 1]])[0]["st"]
check('a column inserted at 1 pushes the others right, in every row', (r["tokens"]["num"], r["tokens"]["drg"], r["glosses"], r["n"]), (["a", "", "b", "c"], ["x", "", "y", "z"], ["G1", "", "G2", "G3"], 4))
r = run([["insertColumn", S(["a", "b"], ["x"], ["G1"]), 0]])[0]["st"]
check('rows of different length are made equal before inserting', (r["tokens"]["num"], r["tokens"]["drg"], r["glosses"], r["n"]), (["", "a", "b"], ["", "x", ""], ["", "G1", ""], 3))
o = run([["deleteColumn", S(["a", "b", "c"], ["x", "y", "z"], ["G1", "G2", "G3"]), 1]])[0]
check('a column is deleted from every row and from the glosses', (o["r"], o["st"]["tokens"]["num"], o["st"]["tokens"]["drg"], o["st"]["glosses"], o["st"]["n"]), (True, ["a", "c"], ["x", "z"], ["G1", "G3"], 2))
o = run([["deleteColumn", S(["a"]), 0], ["deleteColumn", S(["a", "b"]), 5], ["deleteColumn", S(["a", "b"]), None]])
check('the last column cannot be deleted, nor one that is not there', [x["r"] for x in o], [False, False, False])
# ── a sequence, as an author would do it ──
res, fin = chain(S(["Talōw", "mi", "gil"], ["Rorwor", "mi", "gil"], ["morning", "PRF", "go"]), [["insertColumn", 1], ["moveToken", "drg", 2, 1], ["moveToken", "num", 0, 2]])
check('as an author would do it: insert a column, drag a word of one language into it (an empty place), then another word onto an occupied place: what follows goes right and a column is created', (fin["tokens"]["num"], fin["tokens"]["drg"], fin["glosses"], fin["n"], [x["created"] for x in res[1:]]), (["", "", "Talōw", "mi", "gil"], ["Rorwor", "mi", "", "gil", ""], ["morning", "", "PRF", "go", ""], 5, [False, True]))
print(f"\n{ok} passed, {bad} failed")
sys.exit(1 if bad else 0)
