"""Direct tests of fnsplit.py (the rules of splitting a fieldnotes sentence). Run: python3 tests/test_fnsplit.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lxml import etree
import fnsplit

CODES = ["num", "drg", "kro", "olr", "lkn"]
XML = """<database>
\t<tiGroup>
\t\t<ti>T</ti>
\t\t<rfGroup>
\t\t\t<rf>x:1</rf>
\t\t\t<bslGroup>
\t\t\t\t<bsl>Hello</bsl>
\t\t\t\t<mtp>mtp form</mtp>
\t\t\t\t<num>n1</num>
\t\t\t\t<drg>d1</drg>
\t\t\t\t<kro>k1</kro>
\t\t\t\t<olr>o1</olr>
\t\t\t\t<lkn>l1</lkn>
\t\t\t</bslGroup>
\t\t</rfGroup>
\t\t<rfGroup>
\t\t\t<rf>x:2</rf>
\t\t\t<bslGroup><bsl>Bye</bsl><num>n2</num></bslGroup>
\t\t</rfGroup>
\t</tiGroup>
</database>"""
fails = 0
def check(name, ok, detail=""):
    global fails
    print(("  ok  " if ok else "  FAIL ") + name + ("" if ok else f"  {detail}"))
    fails += 0 if ok else 1

def fresh():
    root = etree.fromstring(XML.encode()); return root, root.find("tiGroup")

root, tg = fresh()
ids = fnsplit.split_sentence(root, tg, "x:1", [["num", "drg"], ["kro", "olr", "lkn"]], CODES)
rfs = [r.text for r in root.iter("rf")]
check("ids are the old id + a, b, in place", ids == ["x:1a", "x:1b"] and rfs == ["x:1a", "x:1b", "x:2"], str(rfs))
a, b = [tg.findall("rfGroup")[i] for i in (0, 1)]
tags = lambda g: [e.tag for e in g.find("bslGroup")]
check("each part keeps the prompt and its own languages", tags(a)[:1] == ["bsl"] and [t for t in tags(a) if t in CODES] == ["num", "drg"] and [t for t in tags(b) if t in CODES] == ["kro", "olr", "lkn"] and b.findtext("bslGroup/bsl") == "Hello")
check("a language of another project (mtp) stays with the first group only", "mtp" in tags(a) and "mtp" not in tags(b), f"{tags(a)} {tags(b)}")
check("the other sentence is untouched", tg.findall("rfGroup")[2].findtext("rf") == "x:2" and tg.findall("rfGroup")[2].findtext("bslGroup/num") == "n2")
out = etree.tostring(root, encoding="unicode")
check("the result is still well-formed, one element per line like the source", etree.fromstring(out.encode()) is not None and "\\n\\n" not in out and "<kro>k1</kro>" in out)
for bad in ([["num"]], [["num"], ["drg"]], [["num", "drg"], ["kro", "olr", "lkn", "num"]], [["num", "drg"], [], ["kro", "olr", "lkn"]]):
    r2, t2 = fresh()
    try: fnsplit.split_sentence(r2, t2, "x:1", bad, CODES); ok = False
    except fnsplit.SplitError: ok = True
    check(f"refused: {bad}", ok)
r2, t2 = fresh()
try: fnsplit.split_sentence(r2, t2, "nope", [["num", "drg"], ["kro", "olr", "lkn"]], CODES); ok = False
except fnsplit.SplitError: ok = True
check("an unknown sentence is refused", ok)
r2, t2 = fresh(); fnsplit.split_sentence(r2, t2, "x:1", [["num"], ["drg", "kro", "olr", "lkn"]], CODES)
ids2 = fnsplit.split_sentence(r2, t2, "x:1b", [["drg"], ["kro", "olr", "lkn"]], CODES)
check("a part can be split again (x:1ba, x:1bb)", ids2 == ["x:1ba", "x:1bb"])
r2, t2 = fresh()
r2.find(".//rfGroup[2]/rf").text = "x:1b"
try: fnsplit.split_sentence(r2, t2, "x:1", [["num", "drg"], ["kro", "olr", "lkn"]], CODES); ok = False
except fnsplit.SplitError: ok = True
check("an id already used is refused", ok)

g = {"tokens": {"num": ["a", "b", "—", ""], "drg": ["a2", "", "c2", ""], "kro": ["", "", "", "k"], "olr": ["", "o", "", ""], "lkn": ["", "", "", ""]},
     "glosses": ["g0", "g1", "g2", "g3"], "translation": "T", "confirmed": True}
ga = fnsplit.split_gloss(g, ["num", "drg"], CODES, True)
gb = fnsplit.split_gloss(g, ["kro", "olr", "lkn"], CODES, False)
check("the gloss is cut: languages of the part, only columns where one has a word", set(ga["tokens"]) == {"num", "drg"} and ga["tokens"]["num"] == ["a", "b", "—"] and ga["glosses"] == ["g0", "g1", "g2"], str(ga))
check("…the other part gets its columns (olr at 1, kro at 3)", gb["tokens"]["olr"] == ["o", ""] and gb["tokens"]["kro"] == ["", "k"] and gb["glosses"] == ["g1", "g3"], str(gb))
check("…the translation is kept, confirmation is reset, the original is not changed", ga["translation"] == "T" and gb["confirmed"] is False and g["confirmed"] is True and len(g["tokens"]["num"]) == 4)
print("\n" + ("all passed" if not fails else f"{fails} failed")); sys.exit(1 if fails else 0)
