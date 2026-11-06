#!/usr/bin/env python3
"""
DBT regression harness.

It starts the site on a PRIVATE COPY of the repository with clean data (your real uploads, edits
and settings are never touched), then checks three things:

  visual      a screenshot of every page, at two screen widths, as a visitor and as the author,
              compared pixel by pixel with the recorded baseline
  api         what the server returns (dictionary, texts, grammar, LaTeX ...), compared with the baseline
  functional  the features themselves, used like a person would use them: editing and saving entries,
              glossing and confirming texts, citing in the grammar, exporting, changing the settings

    python tests/run_tests.py                      run everything against the baseline
    python tests/run_tests.py --update-baseline    record the current behaviour as the baseline
    python tests/run_tests.py --only functional    run one suite (visual | api | functional)

Needs:  pip install -r tests/requirements-test.txt  &&  playwright install chromium
Screenshots depend on the fonts of the machine, so a baseline belongs to the machine that recorded it.
"""
import argparse, hashlib, html as html_lib, json, os, re, shutil, socket, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
from lxml import etree

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
BASELINE, OUTPUT = HERE / "baseline", HERE / "output"
PASSWORD = "dbt-test-password"

# ───────────────────────── reporting ─────────────────────────
RESULTS = []          # (suite, name, ok, detail)

def check(suite, name, ok, detail=""):
    RESULTS.append((suite, name, bool(ok), detail))
    print(f"  {'✓' if ok else '✗'} {name}" + (f"   [{detail}]" if detail and not ok else ""), flush=True)
    return bool(ok)

def section(title):
    print(f"\n── {title} " + "─" * max(0, 70 - len(title)), flush=True)

# ───────────────────────── the site, on a private copy ─────────────────────────
SITE_URLS = []

class Site:
    def __init__(self, project_override=None, orthography_override=None, pages_override=None, drop_pages=False,
                 setup_mode=False, env_unset=(), extra_env=None, prepare=None, expect_failure=False):
        self.work = Path(tempfile.mkdtemp(prefix="dbt-test-"))
        self.dir = self.work / "site"
        shutil.copytree(ROOT, self.dir, ignore=shutil.ignore_patterns(
            "uploads", "instance", "tests", ".git", "__pycache__", "*.pyc", "venv", ".venv", "node_modules"))
        (self.dir / "uploads").mkdir(exist_ok=True)
        if project_override is not None:
            self.file("project/project.json").write_text(json.dumps(project_override, ensure_ascii=False, indent=2), encoding="utf-8")
        if setup_mode:                                   # a fresh clone: no project yet, so the first-run setup is offered
            shutil.rmtree(self.dir / "project", ignore_errors=True)
        if drop_pages:
            shutil.rmtree(self.dir / "project" / "pages", ignore_errors=True)
        if pages_override is not None:
            for name, content in pages_override.items():
                self.file(f"project/pages/{name}.json").write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        if orthography_override is not None:
            self.file("project/orthography.json").write_text(json.dumps(orthography_override, ensure_ascii=False, indent=2), encoding="utf-8")
        if prepare is not None:                          # shape the folder before the server first sees it
            prepare(self.dir)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0)); self.port = s.getsockname()[1]
        self.env = dict(os.environ, AUTHOR_PASSWORD=PASSWORD, PORT=str(self.port), DBT_DEBUG="0", PYTHONUNBUFFERED="1")
        for k in env_unset: self.env.pop(k, None)
        self.env.update(extra_env or {})
        self.url = f"http://127.0.0.1:{self.port}/"
        SITE_URLS.append(self.url)
        self.started = self._launch(expect_failure)

    def _launch(self, expect_failure=False):
        """Start the server and wait for it. With expect_failure, return False when it stops by itself."""
        self.log = open(self.work / "server.log", "a")
        self.proc = subprocess.Popen([sys.executable, "app.py"], cwd=self.dir, env=self.env, stdout=self.log, stderr=subprocess.STDOUT)
        for _ in range(100):
            try:
                urllib.request.urlopen(self.url, timeout=1); return True
            except Exception:
                if self.proc.poll() is not None: break
                time.sleep(0.3)
        if expect_failure and self.proc.poll() is not None:
            return False
        raise RuntimeError("the site did not start:\n" + (self.work / "server.log").read_text())

    def log_text(self):
        return (self.work / "server.log").read_text(encoding="utf-8")

    def restart(self):
        """Stop the server and start it again on the same folder."""
        self.proc.terminate()
        try: self.proc.wait(5)
        except Exception: self.proc.kill()
        mark = len(self.log_text())
        self._launch()
        return self.log_text()[mark:]                    # what the new run printed

    def setup_code(self):
        m = re.search(r"Setup code \(asked there\):\s+(\S+)", (self.work / "server.log").read_text(encoding="utf-8"))
        return m.group(1) if m else ""

    def wait_restart(self, timeout=40):
        """After the setup the server restarts itself: wait until the new one answers."""
        t0 = time.time()
        while time.time() - t0 < timeout:
            time.sleep(0.7)
            try:
                if urllib.request.urlopen(self.url + "api/auth/status", timeout=2).status == 200: return True
            except Exception: pass
        return False

    def stop(self):
        self.proc.terminate()
        try: self.proc.wait(5)
        except Exception: self.proc.kill()
        shutil.rmtree(self.work, ignore_errors=True)

    def file(self, rel):  return self.dir / rel
    def read(self, rel):  return (self.dir / rel).read_text(encoding="utf-8")
    def json(self, rel):
        try: return json.loads(self.read(rel))
        except Exception: return {}

# ───────────────────────── browser helpers ─────────────────────────
def noise(msg):
    return "fonts.g" in msg or "ERR_NAME" in msg or "ERR_INTERNET" in msg or "Failed to load resource" in msg

def new_context(browser, site, width=1280, author=False, height=900):
    ctx = browser.new_context(viewport={"width": width, "height": height})
    # never depend on the outside world (web fonts, CDNs): anything that is not the site itself is refused at once
    own = site.url
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(own) else route.abort())
    if author:
        r = ctx.request.post(site.url + "api/auth/login", data=json.dumps({"password": PASSWORD}), headers={"Content-Type": "application/json"})
        assert r.ok, "author login failed"
    return ctx

def watch(page, errors):
    page.on("pageerror", lambda e: errors.append("PAGEERROR: " + str(e)))
    page.on("console", lambda m: errors.append("console: " + m.text) if m.type == "error" and not noise(m.text) else None)
    page.on("dialog", lambda d: d.accept())
    def bad_response(r):
        if r.status >= 400 and not r.url.endswith("/favicon.ico") and any(r.url.startswith(u) for u in SITE_URLS):
            errors.append(f"HTTP {r.status} {r.url}")
    page.on("response", bad_response)

def open_page(page, site, path, selector=None, wait=1500):
    page.goto(site.url + path, wait_until="domcontentloaded")
    if selector:
        try: page.wait_for_selector(selector, timeout=10000)
        except Exception: pass
    page.wait_for_timeout(wait)

# Flags that make Chromium draw the same pixels every time (no GPU, no sub-pixel text positioning or
# LCD anti-aliasing, no threaded compositing): screenshots must not vary from one run to the next.
CHROMIUM_ARGS = ["--disable-gpu", "--disable-lcd-text", "--font-render-hinting=none", "--disable-font-subpixel-positioning",
                 "--force-color-profile=srgb", "--disable-skia-runtime-opts"]

FREEZE = ("*{animation:none!important;transition:none!important;caret-color:transparent!important}"
          "html{scrollbar-width:none!important} ::-webkit-scrollbar{display:none!important}")

# ───────────────────────── 1. visual suite ─────────────────────────
VISITOR_PAGES = [
    ("home",              "index.html",                      None),
    ("about",             "about.html",                      None),
    ("grammar",           "grammar.html",                    "#sections-container .grammar-section"),
    ("dictionary-koro",   "dictionary.html?lang=Koro",       "#dict-content .entry"),
    ("dictionary-nume",   "dictionary.html?lang=Nume",       "#dict-content .entry"),
    ("texts-recordings",  "texts.html",                      "#texts-grid .text-card"),
    ("viewer-fieldnotes", "transcription.html?fieldnotes=1&index=0&title=D01", ".tx-phrase"),
    ("viewer-papers",     "transcription.html?papers=1&index=0&title=Examples+from+papers", ".tx-phrase"),
    ("viewer-recording",  "transcription.html?key=crdo-WWO_FARFADETS.xml&title=Farfadets&lang=wwo", ".tx-phrase"),
    ("references",        "references.html",                 ".ref-entry"),
]
AUTHOR_PAGES = [
    ("author-grammar",           "grammar.html",                    "#sections-container .grammar-section"),
    ("author-dictionary-koro",   "dictionary.html?lang=Koro",       "#dict-content .entry"),
    ("author-viewer-fieldnotes", "transcription.html?fieldnotes=1&index=0&title=D01", ".tx-phrase"),
    ("author-viewer-recording",  "transcription.html?key=crdo-WWO_FARFADETS.xml&title=Farfadets&lang=wwo", ".tx-phrase"),
    ("author-references",        "references.html",                 ".ref-entry"),
]

def settle(page, quiet_ms=900, timeout_ms=15000):
    """Wait until the page is truly quiet: no network activity, and neither its content nor its height
    changes for quiet_ms (pages fill themselves in step by step: sections, dictionary links, wrapping)."""
    try: page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception: pass
    last, still, waited = None, 0, 0
    while waited < timeout_ms:
        state = page.evaluate("() => document.body.innerHTML.length + '|' + document.documentElement.scrollHeight + '|' + document.documentElement.scrollWidth")
        still = still + 150 if state == last else 0
        if still >= quiet_ms: return
        last = state; page.wait_for_timeout(150); waited += 150

SHOT_HEIGHT = 2400

def screenshot(page, path, max_height=SHOT_HEIGHT):
    page.add_style_tag(content=FREEZE)
    settle(page)
    # let fonts and the layout settle: two animation frames after the fonts are ready
    page.evaluate("document.fonts.ready.then(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))))")
    page.wait_for_timeout(300)
    page.evaluate("document.activeElement && document.activeElement.blur && document.activeElement.blur()")
    h = min(page.evaluate("Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)"), max_height)
    w = page.viewport_size["width"]
    page.screenshot(path=str(path), full_page=False, clip={"x": 0, "y": 0, "width": w, "height": h})

def compare_png(cur, base, tolerance):
    from PIL import Image, ImageChops
    a, b = Image.open(cur).convert("RGB"), Image.open(base).convert("RGB")
    if a.size != b.size:
        return False, f"size changed {b.size} -> {a.size}", None
    diff = ImageChops.difference(a, b)
    if diff.getbbox() is None:
        return True, "identical", None
    mask = diff.convert("L").point(lambda v: 255 if v else 0)
    n = mask.histogram()[255]
    frac = n / (a.size[0] * a.size[1])
    return frac <= tolerance, f"{n} pixels differ ({frac:.3%}), region {diff.getbbox()}", mask

def visual_one(browser, site, args, name, path, selector, width, author, shots=None):
    # a tall viewport from the start: a full-page screenshot would resize it at the last moment and re-flow the page
    ctx = new_context(browser, site, width, author, height=SHOT_HEIGHT)
    page = ctx.new_page(); errs = []; watch(page, errs)
    open_page(page, site, path, selector, wait=1800)
    if shots: shots(page)
    out = OUTPUT / "visual" / f"{name}@{width}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    screenshot(page, out)
    ctx.close()
    base = BASELINE / "visual" / out.name
    if args.update_baseline:
        base.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(out, base)
        check("visual", f"{name} @{width}px  (baseline recorded)", not errs, "; ".join(errs[:1]))
        return
    if not base.exists():
        check("visual", f"{name} @{width}px", False, "no baseline yet: run with --update-baseline"); return
    ok, detail, mask = compare_png(out, base, args.tolerance)
    if mask is not None and not ok:
        (OUTPUT / "diff").mkdir(parents=True, exist_ok=True); mask.save(OUTPUT / "diff" / out.name)
    check("visual", f"{name} @{width}px", ok and not errs, detail if not errs else "; ".join(errs[:1]))

def suite_visual(browser, site, args):
    section("visual: every page, pixel by pixel")
    for name, path, sel in VISITOR_PAGES:
        for width in (1280, 600):
            visual_one(browser, site, args, name, path, sel, width, False)
    # the Texts page has two tabs
    def click_fieldnotes_tab(page):
        page.click('.tab-btn[data-tab="fieldnotes"]'); page.wait_for_timeout(1500)
    for width in (1280, 600):
        visual_one(browser, site, args, "texts-fieldnotes", "texts.html", "#texts-grid .text-card", width, False, click_fieldnotes_tab)
    for name, path, sel in AUTHOR_PAGES:
        visual_one(browser, site, args, name, path, sel, 1280, True)
    def open_settings(page):
        page.click("#settings-btn"); page.wait_for_timeout(1200)
    visual_one(browser, site, args, "author-settings-dialog", "dictionary.html?lang=Koro", "#dict-content .entry", 1280, True, open_settings)
    def open_edit(page):
        page.locator('[id="ea-know"] >> text=Edit').click(); page.wait_for_timeout(900)
    visual_one(browser, site, args, "author-edit-entry-dialog", "dictionary.html?lang=Koro", "#dict-content .entry", 1280, True, open_edit)
    def open_reference_form(page):
        page.click('[data-edit="francois2026b"]'); page.wait_for_selector("#ref-modal.visible"); page.wait_for_function("document.getElementById('rf-prev-text').textContent.includes('2026b')"); page.wait_for_timeout(600)
    visual_one(browser, site, args, "author-reference-form", "references.html", ".ref-entry", 1280, True, open_reference_form)

# ───────────────────────── 2. API suite ─────────────────────────
PUBLIC_API = [
    ("auth-status-visitor", "api/auth/status"),
    ("dictionary-xml", "api/dictionary/xml"),
    ("dictionary-entries", "api/dictionary/entries"),
    ("dictionary-examples-initial", "api/dictionary/examples"),
    ("dictionary-proposed-initial", "api/dictionary/proposed"),
    ("transcriptions-list", "api/transcriptions/list"),
    ("transcription-farfadets", "api/transcription/crdo-WWO_FARFADETS.xml"),
    ("fieldnotes-groups", "api/fieldnotes/groups"),
    ("fieldnotes-group-0", "api/fieldnotes/group/0"),
    ("fieldnotes-text-0", "api/fieldnotes/tx/0"),
    ("papers-groups", "api/papers/groups"),
    ("papers-text-0", "api/papers/tx/0"),
    ("grammar-list", "api/grammar"),
    ("grammar-s1", "api/grammar/s1"),
    ("colors-js", "colors.js"),
    ("project-js", "project.js"),
    ("references", "api/references"),
    ("references-bibtex", "api/references/export/bibtex"),
    ("references-endnote", "api/references/export/endnote"),
]
AUTHOR_API = [
    ("dictionary-settings", "api/dictionary/settings"),
    ("dictionary-orthography-preview", "api/dictionary/orthography"),
    ("latex-export", "api/grammar/export/latex"),
]

def canonical(text, content_type):
    if "json" in (content_type or ""):
        try: return json.dumps(json.loads(text), indent=1, sort_keys=True, ensure_ascii=False)
        except Exception: pass
    return text

def suite_api(browser, site, args):
    section("api: what the server returns")
    anon = new_context(browser, site, author=False); auth = new_context(browser, site, author=True)
    for ctx, items in ((anon, PUBLIC_API), (auth, AUTHOR_API)):
        for name, path in items:
            r = ctx.request.get(site.url + path)
            if r.status != 200:
                check("api", f"{name}", False, f"HTTP {r.status}"); continue
            text = canonical(r.text(), r.headers.get("content-type"))
            out = OUTPUT / "api" / f"{name}.txt"; out.parent.mkdir(parents=True, exist_ok=True); out.write_text(text, encoding="utf-8")
            base = BASELINE / "api" / out.name
            if args.update_baseline:
                base.parent.mkdir(parents=True, exist_ok=True); base.write_text(text, encoding="utf-8"); check("api", f"{name}  (baseline recorded)", True)
            elif not base.exists():
                if args.record_missing:
                    base.parent.mkdir(parents=True, exist_ok=True); base.write_text(text, encoding="utf-8"); check("api", f"{name}  (new: baseline recorded)", True)
                else:
                    check("api", name, False, "no baseline yet")
            else:
                same = base.read_text(encoding="utf-8") == text
                check("api", name, same, "" if same else f"differs from the baseline (see {out})")
    # what a visitor must NOT be able to do
    for method, path in (("get", "api/dictionary/settings"), ("post", "api/dictionary/entry"), ("get", "api/dictionary/orthography")):
        r = getattr(anon.request, method)(site.url + path)
        check("api", f"visitor refused: {method.upper()} /{path}", r.status in (401, 403), f"HTTP {r.status}")
    r = anon.request.get(site.url + "api/grammar/export/latex")        # public on purpose: the grammar itself is public
    check("api", "the LaTeX export is public, like the grammar", r.status == 200, f"HTTP {r.status}")
    anon.close(); auth.close()

# ───────────────────────── 3. functional suite ─────────────────────────
def entry_sig(site, eid):
    from lxml import etree
    root = etree.parse(str(site.file("project/dictionary.xml"))).getroot()
    el = root.find(f'.//EntréeLexicale[@identifiant="{eid}"]')
    return None if el is None else hashlib.md5(etree.tostring(el, method="c14n")).hexdigest()

def entry_el(site, eid):
    from lxml import etree
    return etree.parse(str(site.file("project/dictionary.xml"))).getroot().find(f'.//EntréeLexicale[@identifiant="{eid}"]')

def rgb(h):
    h = h.lstrip("#"); return f"rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})"

def suite_functional(browser, site, args):
    S = "functional"
    errors = []
    ctx = new_context(browser, site, 1280, author=True); page = ctx.new_page(); watch(page, errors)
    api, H = ctx.request, {"Content-Type": "application/json"}

    section("functional: the dictionary")
    open_page(page, site, "dictionary.html?lang=Koro", "#dict-content .entry", 1500)
    ids = page.locator("#dict-content .entry").evaluate_all("els => els.map(e => e.id)")
    check(S, "the eight original entries are there", len(ids) == 8, f"{len(ids)} entries")
    bad = []
    for eid in ids:
        before = entry_sig(site, eid)
        page.locator(f'[id="ea-{eid}"] >> text=Edit').click(); page.wait_for_timeout(350)
        page.click("#em-submit"); page.wait_for_timeout(500)
        if entry_sig(site, eid) != before: bad.append(eid)
    check(S, "open + save every entry without a change leaves it byte-identical", not bad, str(bad))
    know = entry_el(site, "know")
    check(S, "the entries got their phonetic forms at start-up (the originals confirmed)",
          know is not None and know.find('Lemme/FormePhonétique[@langue="kro"]') is not None
          and know.find('Lemme/FormePhonétique[@langue="kro"]').text == "rɔŋ" and know.find('Lemme/FormePhonétique[@langue="kro"]').get("statut") is None)
    hw = page.locator('[id="know"] .entry-headword').inner_text(); ipa = page.locator('[id="know"] .entry-ipa').inner_text()
    check(S, "the headword is shown with its IPA in [ ]", (hw, ipa) == ("ron̄", "[rɔŋ]"), f"{hw!r} {ipa!r}")

    # add an entry: senses, IPA suggestion, the author's own IPA, homonym
    page.click("#add-entry-btn"); page.wait_for_timeout(300)
    page.fill("#ef-kro", "tuqa"); page.wait_for_timeout(900)
    check(S, "typing an orthographic form suggests its IPA", page.input_value("#ef-ipa-kro") == "tuk͡pʷa", page.input_value("#ef-ipa-kro"))
    page.fill("#ef-pos", "n."); page.locator(".em-sense").first.locator('[data-f="definition"]').fill("a test word")
    page.click("#em-submit"); page.wait_for_timeout(1500)
    el = entry_el(site, "tuqa")
    fp = None if el is None else el.find('Lemme/FormePhonétique[@langue="kro"]')
    check(S, "the new entry is saved with a provisional (auto) IPA", fp is not None and fp.text == "tuk͡pʷa" and fp.get("statut") == "auto")
    page.locator('[id="tuqa"] .ipa-badge').click(); page.wait_for_timeout(700)
    fp = entry_el(site, "tuqa").find('Lemme/FormePhonétique[@langue="kro"]')
    check(S, "clicking the ? confirms the IPA", fp.get("statut") is None)
    page.locator('[id="ea-tuqa"] >> text=Delete').click(); page.wait_for_timeout(1200)
    check(S, "an entry can be deleted", entry_el(site, "tuqa") is None)

    # settings
    page.reload(wait_until="domcontentloaded"); page.wait_for_timeout(1500)
    page.click("#settings-btn"); page.wait_for_timeout(900)
    rows = page.locator("#st-rows tr")
    sounds = lambda o: [rows.nth(i).locator('[data-f="ipa"]').input_value() for i in range(rows.count()) if rows.nth(i).locator('[data-f="orth"]').input_value() == o]
    check(S, "settings: the orthography table is the author's (q = k͡pʷ only, m̄ = ŋʷ only)", sounds("q") == ["k͡pʷ"] and sounds("m\u0304") == ["ŋʷ"], f"{sounds('q')} {sounds('m' + chr(0x304))}")
    page.fill("#st-try-orth", "tuqa"); page.fill("#st-try-ipa-in", "ŋʷa"); page.wait_for_timeout(700)
    check(S, "settings: the try-it box converts both ways", page.inner_text("#st-try-ipa") == "[tuk͡pʷa]" and page.inner_text("#st-try-orth-out") == "m̄a")
    check(S, "settings: five language colours in east-to-west order", page.locator(".st-color label").all_inner_texts() == ["Nume", "Dorig", "Koro", "Olrat", "Lakon"])
    page.locator('.st-color input[data-hex][data-c="num"]').fill("#0066cc"); page.click("#st-save"); page.wait_for_timeout(2500)
    page.goto(site.url + "about.html", wait_until="domcontentloaded"); page.wait_for_timeout(800)
    got = page.locator(".lang-section h3").first.evaluate("e => getComputedStyle(e).color")
    check(S, "a colour chosen in the settings is used on other pages", got == rgb("#0066cc"), got)
    page.goto(site.url + "dictionary.html?lang=Koro", wait_until="domcontentloaded"); page.wait_for_timeout(1500)
    page.click("#settings-btn"); page.wait_for_timeout(800); page.click("#st-colors-reset"); page.click("#st-save"); page.wait_for_timeout(2500)
    page.goto(site.url + "about.html", wait_until="domcontentloaded"); page.wait_for_timeout(800)
    got = page.locator(".lang-section h3").first.evaluate("e => getComputedStyle(e).color")
    check(S, "'Default colours' restores them", got == rgb("#2e5c8a"), got)
    r = api.post(site.url + "api/dictionary/settings", headers=H, data=json.dumps({"correspondences": api.get(site.url + "api/dictionary/settings").json()["correspondences"], "colors": {"num": "red"}}))
    check(S, "a colour that is not #rrggbb is refused", r.status == 400, f"HTTP {r.status}")
    page.goto(site.url + "dictionary.html?lang=Koro", wait_until="domcontentloaded"); page.wait_for_timeout(1500)
    page.click("#ortho-btn"); page.wait_for_timeout(900)
    check(S, "the IPA→orthography tool finds nothing left to convert", "Nothing to convert" in page.inner_text("#ortho-desc"), page.inner_text("#ortho-desc")[:60])

    section("functional: texts (fieldnotes, recordings, papers)")
    def gloss_first_plain_box(pg, sid, word):
        ph = pg.locator(f'[id="{sid}"]')
        box = ph.locator("input.fn-col-gloss:visible").first
        col = box.evaluate("e => [...e.closest('tr').children].indexOf(e.closest('td')) - 1")
        box.fill(word); box.press("Tab"); pg.wait_for_timeout(1000)
        return ph, col

    # fieldnotes
    sid = "d01.Road:09"
    open_page(page, site, "transcription.html?fieldnotes=1&index=0&title=D01", ".tx-phrase", 2000)
    ph, col = gloss_first_plain_box(page, sid, "first")
    st = site.json("project/texts/glosses/fieldnotes_0.json").get(sid, {})
    check(S, "fieldnotes: a gloss typed in a column is saved there", (st.get("glosses") or [""] * 99)[col] == "first", str(st.get("glosses"))[:60])
    check(S, "fieldnotes: all five languages are saved with the sentence", sorted((st.get("tokens") or {}).keys()) == ["drg", "kro", "lkn", "num", "olr"])
    page.locator(f'[id="{sid}"] .gloss-badge').click(); page.wait_for_timeout(1300)
    check(S, "fieldnotes: the badge turns ? into ✓ right after the first gloss", page.locator(f'[id="{sid}"] .gloss-badge').inner_text() == "✓")
    t = page.locator(f'[id="{sid}"] .tx-transl-input'); t.fill("Edited translation."); t.press("Tab"); page.wait_for_timeout(900)
    page.locator(f'[id="{sid}"] .fn-edit-btn').click(); page.wait_for_timeout(400)
    cells = page.locator(f'[id="{sid}"] .fn-editor input[data-lang]'); n_before = cells.count()
    cells.first.fill("EDITED"); page.locator(f'[id="{sid}"] .fn-editor .fn-editor-actions .primary').click(); page.wait_for_timeout(1200)
    st = site.json("project/texts/glosses/fieldnotes_0.json").get(sid, {})
    check(S, "fieldnotes: the alignment editor edits and saves", st.get("tokens", {}).get("num", [""])[0] == "EDITED" and n_before >= 2)
    check(S, "fieldnotes: the translation survives glossing and realigning", st.get("translation") == "Edited translation.", str(st.get("translation")))
    page.set_viewport_size({"width": 600, "height": 900}); page.reload(wait_until="domcontentloaded"); page.wait_for_timeout(2300)
    over = page.evaluate("""() => [...document.querySelectorAll('.tx-phrase')].filter(p => { const f = p.querySelector('.fn-interlinear'); return f && f.scrollWidth > f.clientWidth + 1; }).length
                              + (document.documentElement.scrollWidth > window.innerWidth + 1 ? 1000 : 0)""")
    check(S, "fieldnotes: long sentences wrap on a narrow screen (no sideways scrolling)", over == 0, f"{over}")
    page.set_viewport_size({"width": 1280, "height": 900})

    # a recording
    rid = "en_fr_Drg_Farfadets_02"
    open_page(page, site, "transcription.html?key=crdo-WWO_FARFADETS.xml&title=Farfadets&lang=wwo", ".tx-phrase", 2000)
    code = page.locator(f'[id="{rid}"] td.fn-form-cell').first.get_attribute("data-lang")
    check(S, "recording: words carry the dictionary's language code (wwo → drg)", code == "drg", str(code))
    ph, col = gloss_first_plain_box(page, rid, "testgloss")
    word = page.locator(f'[id="{rid}"] td.fn-form-cell').nth(col).inner_text()
    stored = site.json("project/texts/glosses/crdo-WWO_FARFADETS_xml.json").get(rid, {})
    check(S, "recording: glosses are saved in the shared format {code: tokens}", isinstance(stored.get("tokens"), dict) and (stored.get("glosses") or [""] * 99)[col] == "testgloss")
    page.locator(f'[id="{rid}"] .gloss-badge').click(); page.wait_for_timeout(1400)
    prop = api.get(site.url + "api/dictionary/proposed").json()
    forms = [v.get("forms", {}) for v in prop.values()]
    check(S, "recording: confirming proposes the word to the dictionary, in the right language", any(f.get("drg") == word for f in forms), f"{word!r} in {forms[:2]}")
    page.goto(site.url + "dictionary.html?lang=Dorig", wait_until="domcontentloaded"); page.wait_for_timeout(2000)
    ghost = page.locator(".entry.proposed", has_text="testgloss")
    check(S, "dictionary: the proposed entry is shown", ghost.count() >= 1)
    ghost.first.locator("text=Add to dictionary").click(); page.wait_for_timeout(2200)
    from lxml import etree
    added = [e for e in etree.parse(str(site.file("project/dictionary.xml"))).getroot().findall(".//EntréeLexicale") if e.get("identifiant", "").startswith("proposed_")]
    ok = bool(added) and added[0].find('Lemme/ReprésentationDeForme[@langue="drg"]') is not None and added[0].find('Lemme/FormePhonétique[@langue="drg"]') is not None
    check(S, "dictionary: 'Add to dictionary' creates the entry with its IPA", ok)

    # the paper example feeds the dictionary
    open_page(page, site, "transcription.html?papers=1&index=0&title=Examples+from+papers", ".tx-phrase", 2000)
    page.locator(".gloss-badge").first.click(); page.wait_for_timeout(1500)
    ex = api.get(site.url + "api/dictionary/examples").json()
    check(S, "papers: confirming the example attaches it to the eight dictionary entries",
          all(k in ex for k in ("3pl", "nondum1", "know", "properly", "nondum2", "art", "speech", "poss")), str(sorted(ex)))
    page.goto(site.url + "dictionary.html?lang=Koro", wait_until="domcontentloaded"); page.wait_for_timeout(2000)
    lab = page.locator('[id="know"] .example-label').all_inner_texts()
    check(S, "dictionary: the example is labelled with the text it comes from", any("PAPER" in l.upper() for l in lab), str(lab))

    section("functional: the grammar and the export")
    src = ("## Test\n\n{{cite: fieldnotes#0#d01.Road:09}}\n\n{{cite: papers#negation_example_01}}\n\n"
           "{{cite: crdo-WWO_FARFADETS.xml#en_fr_Drg_Farfadets_02}}\n\n{{entry: nondum1}}\n")
    r = api.post(site.url + "api/grammar/zz_regression", headers=H, data=json.dumps({"source": src}))
    html = r.json().get("html", "") if r.ok else ""
    check(S, "grammar: fieldnotes, paper and recording citations render as aligned tables", html.count("cite-fn-table") >= 3, f"{html.count('cite-fn-table')} tables")
    check(S, "grammar: a citation uses the edited translation", "Edited translation." in html)
    check(S, "grammar: a citation of a recording shows the gloss the author typed", "testgloss" in html)
    check(S, "grammar: the entry chip shows the entry's forms in the five languages", "vitis" in html and "sowse" in html)
    tex = api.get(site.url + "api/grammar/export/latex").text()
    check(S, "LaTeX export: the five language colours are defined", all(f"{n}Color" in tex for n in ("Nume", "Dorig", "Koro", "Olrat", "Lakon")))
    check(S, "LaTeX export: citations come out as glossed tables", "tabular" in tex and "testgloss" in tex)
    api.delete(site.url + "api/grammar/zz_regression")
    check(S, "grammar: a section can be deleted", api.get(site.url + "api/grammar/zz_regression").status == 404)

    check(S, "no page raised a JavaScript error during all of the above", not errors, "; ".join(errors[:2]))
    ctx.close()


# ───────────────────────── 4. generality suite: the code knows no language ─────────────────────────
CODE_FILES = ["app.py", "security.py", "references.py", "setup.html", "auth.js", "style.css", "index.html", "about.html", "dictionary.html", "grammar.html", "texts.html", "transcription.html", "references.html"]
PROJECT_WORDS = re.compile(r"\b(Nume|Dorig|Koro|Olrat|Lakon|Gaua|Vanuatu|Banks Islands|Meroni|Fran[cç]ois)\b")
NOT_SERVED = ["app.py", "references.py", "project/references.json", "starter/references.json", "dbt_dictionary.xml", "AlexFrancois_Questionnaire_Gaua-languages.xml", "project/project.json",
              "project/orthography.json", "project/dictionary.xml", "project/fieldnotes.xml", "project/grammar/s1.md",
              "project/texts/crdo-WWO_FARFADETS.xml", "uploads/dictionary_settings.json", "tests/run_tests.py", "grammar_content/s1.md",
              ".gitignore", "requirements.txt", "transcribed_narratives/crdo-WWO_FARFADETS.xml", "%2e%2e/app.py", "../app.py"]
ALT_LANGS = [("num", "Alpha", "Al", "#112233"), ("drg", "Beta", "Be", "#445566"), ("kro", "Gamma", "Ga", "#778899"),
             ("olr", "Delta", "De", "#aa00aa"), ("lkn", "Epsilon", "Ep", "#00aa66")]

def suite_generality(browser, site, args):
    S = "generality"
    section("generality: the code knows no language, the project does")
    # 1. what is served
    anon = new_context(browser, site, author=False); api = anon.request
    bad = [p for p in NOT_SERVED if api.get(site.url + p).status != 404]
    check(S, "source code and data files are not served (app.py, XML, JSON, uploads, project, tests ...)", not bad, str(bad))
    pages = ["index.html", "about.html", "dictionary.html", "grammar.html", "texts.html", "transcription.html", "references.html"]
    assets = ["style.css", "auth.js", "images/gaua_map.png", "etymograph_icon.png"]
    check(S, "the site's pages and images are served", all(api.get(site.url + p).status == 200 for p in pages + assets))
    left = [p for p in pages if "{{project." in api.get(site.url + p).text()]
    check(S, "no project marker is left unexpanded in any page", not left, str(left))
    proj = json.loads((ROOT / "project" / "project.json").read_text(encoding="utf-8"))
    home = api.get(site.url + "index.html").text()
    check(S, "the title, brand and top-bar label come from the project", proj["homeTitle"] in home and f"◬ {proj['name']}" in home and proj["nav"]["home"] in home)
    pj = api.get(site.url + "project.js").text()
    check(S, "/project.js lists the project's languages", all(f'"{l["code"]}"' in pj and l["name"] in pj for l in proj["languages"]))
    r = api.get(site.url + "gaua.html", max_redirects=0)
    check(S, "the old page name still works: /gaua.html redirects to /about.html", r.status == 301 and r.headers.get("location", "").endswith("/about.html"), f"{r.status} {r.headers.get('location')}")
    anon.close()
    pg = new_context(browser, site, 1280).new_page(); perrs = []; watch(pg, perrs)
    open_page(pg, site, "index.html", ".lang-strip", 1000)
    cells = pg.locator(".lang-strip .lang-cell")
    check(S, "home: the language strip is generated from the project's languages", cells.count() == len(proj["languages"]) and [c for c in cells.evaluate_all("els => els.map(e => e.getAttribute('href'))")] == [f"about.html#{l['name'].lower()}" for l in proj["languages"]])
    check(S, "home: the map section, the three cards and the footer come from the project", pg.locator(".map-section .map-desc").count() == 2 and pg.locator(".dbt-card").count() == 3 and "Documentation:" in pg.locator("footer").inner_text())
    open_page(pg, site, "about.html", ".lang-section", 1000)
    check(S, "about: one section per language, a table of contents with a line for each", pg.locator(".lang-section").count() == len(proj["languages"]) and pg.locator(".about-toc li.sub").count() == len(proj["languages"]) and pg.locator(".about-toc li:not(.sub)").count() == 4)
    check(S, "about: the infobox and the four sections come from the project", pg.locator(".infobox tr").count() == 7 and pg.locator(".about-main h2").count() == 4)
    check(S, "home and about: no JavaScript or loading error", not perrs, "; ".join(perrs[:2]))
    pg.context.close()
    # 2. no Gaua wording left in the code
    dirty = {}
    for f in CODE_FILES:
        hits = PROJECT_WORDS.findall((ROOT / f).read_text(encoding="utf-8"))
        if hits: dirty[f] = sorted(set(h if isinstance(h, str) else h[0] for h in hits))
    check(S, "no language or project name appears in the code (app.py, every page, css)", not dirty, str(dirty))

    # 3. a different project, on the same code
    alt = json.loads(json.dumps(proj))
    alt["name"], alt["titleSuffix"], alt["homeTitle"] = "Alt DBT", "Alt DBT Languages", "Alt Trilogy: a test project"
    alt["nav"] = {"home": "Alt home label", "about": "Alt about label", "dictionary": "Alt Lexicon · {n} Tongues", "grammar": "Alt Grammar · {n} Tongues", "texts": "Alt Corpus"}
    alt["languages"] = [dict(l, name=n, abbr=a, color=c) for l, (code, n, a, c) in zip(proj["languages"], ALT_LANGS)]
    alt["headwordLanguage"] = "drg"
    alt["recordings"] = {"author": "A. Tester", "year": "1999"}
    alt["latex"] = {"title": "Alt Grammar", "subtitle": "Nowhere", "author": "Alt Author"}
    alt["footer"] = "Alt footer text"
    alt_pages = {
        "home": {"byline": "Alt byline", "intro": ["Alt intro: {languages.count} tongues, {languages.list}."],
                 "cards": {"grammar": "Alt grammar card", "texts": "Alt texts card", "dictionary": "Alt dictionary card"},
                 "map": {"title": "Alt map title", "text": ["Alt map paragraph"], "credit": "Alt map credit", "image": "etymograph_icon.png", "imageAlt": "Alt map", "moreLabel": "More about Alt →"}},
        "about": {"tabTitle": "About Alt", "title": "Alt page title", "subtitle": "Alt page subtitle", "sidebarImage": "etymograph_icon.png", "sidebarImageAlt": "Alt",
                  "infobox": {"caption": "Alt at a glance", "rows": [["Row", "Value"]]},
                  "sections": [{"id": "first", "title": "Alt first section", "tocLabel": "First", "infobox": True, "text": ["Alt first paragraph."]},
                               {"id": "tongues", "title": "Alt tongues", "text": ["Alt tongues paragraph."], "languageSections": True}],
                  "languages": {"num": {"badge": "~1 speaker", "meta": ["Alt meta one", "Alt meta two"], "text": ["Alt language paragraph."]}}}}
    asite = Site(project_override=alt, orthography_override={"name": "Alt orthography", "longVowelDoubling": False, "rows": []}, pages_override=alt_pages)
    try:
        ctx = new_context(browser, asite, 1280, author=True); page = ctx.new_page(); errs = []; watch(page, errs); api = ctx.request
        d = api.get(asite.url + "dictionary.html").text()
        check(S, "other project: the page title and brand follow the project", "Comparative Dictionary — Alt DBT Languages" in d and "◬ Alt DBT" in d and "Alt Lexicon · 5 Tongues" in d)
        open_page(page, asite, "dictionary.html", "#dict-content .entry", 1500)
        pills = page.locator(".hw-lang-pill").all_inner_texts()
        check(S, "other project: the language buttons carry its names", [p.strip().lower() for p in pills] == [n.lower() for _, n, _, _ in ALT_LANGS], str(pills))
        bg = page.locator(".hw-lang-pill").first.evaluate("e => getComputedStyle(e).backgroundColor")
        check(S, "other project: …and its colours", bg == rgb("#112233"), bg)
        from lxml import etree
        stored_drg = etree.parse(str(asite.file("project/dictionary.xml"))).getroot().find('.//EntréeLexicale[@identifiant="know"]/Lemme/ReprésentationDeForme[@langue="drg"]').text
        check(S, "other project: the dictionary opens on the project's headword language (Beta)", page.locator('[id="know"] .entry-headword').inner_text() == stored_drg, stored_drg)
        page.locator('[id="ea-know"] >> text=Edit').click(); page.wait_for_timeout(500)
        labels = page.locator("#em-lang-grid label").all_inner_texts()
        check(S, "other project: the entry editor has a row per language of the project", labels == [n for _, n, _, _ in ALT_LANGS], str(labels))
        page.click("#em-cancel")
        open_page(page, asite, "grammar.html", "#sections-container .grammar-section", 1800)
        abbr = page.locator("#s1 .cite-fn-table").first.locator(".cite-fn-abbr").all_inner_texts()
        check(S, "other project: grammar citations use its abbreviations", abbr == [a for _, _, a, _ in ALT_LANGS], str(abbr))
        open_page(page, asite, "texts.html", "#texts-grid .text-card", 1500)
        opts = page.locator("#filter-lang option").all_inner_texts()
        check(S, "other project: the Texts filter lists its languages", opts[1:] == [n for _, n, _, _ in ALT_LANGS], str(opts))
        card = page.locator(".text-card").first.inner_text()
        check(S, "other project: a recording shows its credit", "A. Tester" in card and "1999" in card, card.replace("\n", " ")[:80])
        open_page(page, asite, "transcription.html?key=crdo-WWO_FARFADETS.xml&title=Farfadets&lang=wwo", ".tx-phrase", 1800)
        meta = page.locator(".tx-meta").inner_text().replace("\n", " ")
        check(S, "other project: the viewer shows the language name and credit", "beta" in meta.lower() and "recorded 1999 · a. tester" in meta.lower(), meta)
        open_page(page, asite, "transcription.html?fieldnotes=1&index=0&title=D01", ".tx-phrase", 1800)
        rows = page.locator('[id="d01.Road:09"] .fn-lang-abbr').all_inner_texts()
        check(S, "other project: fieldnotes rows are labelled with its abbreviations (on every line of a wrapped sentence)",
              rows[:5] == [a for _, _, a, _ in ALT_LANGS] and len(rows) % 5 == 0, str(rows))
        tex = api.get(asite.url + "api/grammar/export/latex").text()
        check(S, "other project: the LaTeX export carries its title, author and colours",
              "{Alt Grammar" in tex and "Alt Author" in tex and "\\definecolor{AlphaColor}{HTML}{112233}" in tex and "NumeColor" not in tex)
        open_page(page, asite, "index.html", ".lang-strip", 1000)
        home_txt = page.locator("body").inner_text()
        check(S, "other project: its home page shows its own wording (byline, intro with the language list, cards, map, footer)",
              all(x.lower() in home_txt.lower() for x in ("Alt byline", "Alt intro: five tongues, Alpha, Beta, Gamma, Delta, and Epsilon.", "Alt grammar card", "Alt map title", "Alt map credit", "More about Alt", "Alt footer text")), home_txt[:120].replace("\n", " "))
        check(S, "other project: …and its language strip", page.locator(".lang-strip .lname").all_inner_texts() == [n for _, n, _, _ in ALT_LANGS] and page.locator(".lang-strip a").first.get_attribute("href") == "about.html#alpha")
        open_page(page, asite, "about.html", ".lang-section", 1000)
        check(S, "other project: its about page: title, sections, table of contents, language sections",
              page.title() == "About Alt — Alt DBT Languages" and page.locator("h1.page-title").inner_text() == "Alt page title" and page.locator(".infobox tr").count() == 1
              and page.locator(".about-toc li:not(.sub)").all_inner_texts() == ["First", "Alt tongues"] and page.locator(".lang-section").count() == 5)
        check(S, "other project: a language with content shows its badge and notes, one without shows just its links",
              page.locator("#alpha .speaker-badge").inner_text() == "~1 speaker" and page.locator("#alpha .lang-meta span").count() == 2 and page.locator("#beta .lang-meta").count() == 0 and page.locator("#beta .lang-link").count() == 3)
        served = " ".join(api.get(asite.url + p).text() for p in ("index.html", "about.html", "dictionary.html", "grammar.html", "texts.html", "transcription.html"))
        left = sorted(set(PROJECT_WORDS.findall(served)))
        check(S, "other project: no trace of the first project's names in any page it serves, home and about included", not left, str(left))
        check(S, "other project: no JavaScript or loading error on any of those pages", not errs, "; ".join(errs[:2]))
        ctx.close()
    finally:
        asite.stop()


# ───────────────────────── 5. languages suite: one language, eight languages, a language added later ─────────────────────────
EXTRA_LANGS = [{"code": "aaa", "name": "Zeta", "abbr": "Ze", "color": "#ff0000", "aliases": []},
               {"code": "bbb", "name": "Eta", "abbr": "Et", "color": "#00aa00", "aliases": []},
               {"code": "ccc", "name": "Theta", "abbr": "Th", "color": "#0000ff", "aliases": []}]

def variant(langs, **extra):
    proj = json.loads((ROOT / "project" / "project.json").read_text(encoding="utf-8"))
    proj["languages"] = langs
    proj["headwordLanguage"] = langs[0]["code"]
    proj.update(extra)
    return proj

def first_plain_gloss(page, sid, word):
    ph = page.locator(f'[id="{sid}"]')
    box = ph.locator("input.fn-col-gloss:visible").first
    col = box.evaluate("e => [...e.closest('tr').children].indexOf(e.closest('td')) - 1")
    box.fill(word); box.press("Tab"); page.wait_for_timeout(1000)
    return col

def suite_languages(browser, args):
    from lxml import etree
    S = "languages"
    base = json.loads((ROOT / "project" / "project.json").read_text(encoding="utf-8"))
    five = base["languages"]
    xml_langs = lambda s, eid: {n.get("langue"): n.text for n in etree.parse(str(s.file("project/dictionary.xml"))).getroot().find(f'.//EntréeLexicale[@identifiant="{eid}"]').findall("Lemme/ReprésentationDeForme")}

    # ── a project with ONE language ──
    section("languages: a project with a single language")
    one_lang = [dict(l) for l in five if l["code"] == "kro"]
    nav = dict(base["nav"], dictionary="Lexicon · {languages}")
    site = Site(project_override=variant(one_lang, nav=nav)); errs = []
    try:
        ctx = new_context(browser, site, 1280, author=True); page = ctx.new_page(); watch(page, errs); api = ctx.request
        open_page(page, site, "dictionary.html", "#dict-content .entry", 1500)
        check(S, "one language: the dictionary opens with its entries", page.locator("#dict-content .entry").count() == 8)
        check(S, "one language: the nav label says '1 Language' (singular)", "Lexicon · 1 Language<" in api.get(site.url + "dictionary.html").text())
        check(S, "one language: there are no language buttons to choose between", not page.locator(".sidebar-head").is_visible())
        check(S, "one language: no row of other languages' forms under a headword", page.locator(".entry-equivs").count() == 0)
        page.locator('[id="ea-know"] >> text=Edit').click(); page.wait_for_timeout(500)
        check(S, "one language: the entry editor has a single language row", page.locator("#em-lang-grid label").count() == 1)
        page.click("#em-cancel")
        page.click("#add-entry-btn"); page.wait_for_timeout(300)
        page.fill("#ef-kro", "zzz"); page.wait_for_timeout(700); page.fill("#ef-pos", "n."); page.locator(".em-sense").first.locator('[data-f="definition"]').fill("one-language test")
        page.click("#em-submit"); page.wait_for_timeout(1500)
        check(S, "one language: an entry can be added", xml_langs(site, "zzz") == {"kro": "zzz"}, str(xml_langs(site, "zzz")) if True else "")
        open_page(page, site, "transcription.html?fieldnotes=1&index=0&title=D01", ".tx-phrase", 1800)
        labels = page.locator('[id="d01.Road:09"] .fn-lang-abbr').all_inner_texts()
        check(S, "one language: the text view shows one row per line and no language label", len(labels) >= 1 and all(l == "" for l in labels), str(labels))
        col = first_plain_gloss(page, "d01.Road:09", "onelang")
        st = site.json("project/texts/glosses/fieldnotes_0.json").get("d01.Road:09", {})
        check(S, "one language: a gloss is saved with that single language only", list((st.get("tokens") or {}).keys()) == ["kro"] and st["glosses"][col] == "onelang", str(list((st.get("tokens") or {}).keys())))
        page.locator('[id="d01.Road:09"] .gloss-badge').click(); page.wait_for_timeout(1200)
        keys = list(site.json("project/texts/confirmed_glosses.json").keys())
        check(S, "one language: confirmed glosses are keyed with one slot", bool(keys) and all("|" not in k for k in keys), str(keys[:2]))
        html = api.post(site.url + "api/grammar/zz_one", headers={"Content-Type": "application/json"}, data=json.dumps({"source": "{{cite: fieldnotes#0#d01.Road:09}}"})).json().get("html", "")
        abbr = re.findall(r'cite-fn-abbr[^>]*>([^<]*)<', html)
        check(S, "one language: a grammar citation has one row and no language label", len(abbr) == 1 and abbr[0] == "", str(abbr))
        api.delete(site.url + "api/grammar/zz_one")
        open_page(page, site, "grammar.html", "#sections-container .grammar-section", 1500)
        check(S, "one language: the grammar has no language toggles", not page.locator(".lang-pills-wrap").first.is_visible())
        open_page(page, site, "texts.html", "#texts-grid .text-card", 1500)
        check(S, "one language: the Texts page has no language filter", not page.locator(".filter-row-lang").is_visible())
        open_page(page, site, "about.html", ".lang-section", 1000)
        check(S, "one language: the about page has one language section and one line under Languages in the contents", page.locator(".lang-section").count() == 1 and page.locator(".about-toc li.sub").count() == 1)
        open_page(page, site, "index.html", ".lang-strip", 1000)
        check(S, "one language: the home page's language strip has one cell", page.locator(".lang-strip .lang-cell").count() == 1)
        tex = api.get(site.url + "api/grammar/export/latex").text()
        check(S, "one language: the LaTeX export defines one colour", tex.count("\\definecolor") == 1, str(tex.count("\\definecolor")))
        check(S, "one language: no JavaScript or loading error", not errs, "; ".join(errs[:2]))
        ctx.close()
    finally:
        site.stop()

    # ── a project with EIGHT languages ──
    section("languages: a project with eight languages")
    eight = [dict(l) for l in five] + EXTRA_LANGS
    site = Site(project_override=variant(eight)); errs = []
    try:
        ctx = new_context(browser, site, 1280, author=True); page = ctx.new_page(); watch(page, errs); api = ctx.request
        open_page(page, site, "dictionary.html", "#dict-content .entry", 1500)
        check(S, "eight languages: eight language buttons", page.locator(".hw-lang-pill").count() == 8)
        check(S, "eight languages: seven other forms under a headword", page.locator('[id="know"] .entry-equivs .lang-badge-link').count() == 7, str(page.locator('[id="know"] .entry-equivs .lang-badge-link').count()))
        page.locator('[id="ea-know"] >> text=Edit').click(); page.wait_for_timeout(500)
        check(S, "eight languages: eight rows in the entry editor", page.locator("#em-lang-grid label").count() == 8)
        page.click("#em-cancel")
        page.click("#add-entry-btn"); page.wait_for_timeout(300)
        page.fill("#ef-ccc", "zzzc"); page.fill("#ef-pos", "n."); page.locator(".em-sense").first.locator('[data-f="definition"]').fill("eighth-language test")
        page.click("#em-submit"); page.wait_for_timeout(1500)
        check(S, "eight languages: an entry with a form only in the eighth language is saved", xml_langs(site, "zzzc") == {"ccc": "zzzc"}, str(xml_langs(site, "zzzc")) if True else "")
        page.click("#settings-btn"); page.wait_for_timeout(900)
        check(S, "eight languages: eight colour choices in the Settings", page.locator(".st-color").count() == 8)
        page.click("#st-cancel")
        open_page(page, site, "transcription.html?fieldnotes=1&index=0&title=D01", ".tx-phrase", 1800)
        labels = page.locator('[id="d01.Road:09"] .fn-lang-abbr').all_inner_texts()
        check(S, "eight languages: the text view shows eight rows, labelled, on every line", len(labels) % 8 == 0 and labels[:8] == [l["abbr"] for l in eight], str(labels[:9]))
        col = first_plain_gloss(page, "d01.Road:09", "eightgloss")
        page.locator('[id="d01.Road:09"] .gloss-badge').click(); page.wait_for_timeout(1300)
        keys = list(site.json("project/texts/confirmed_glosses.json").keys())
        check(S, "eight languages: confirmed glosses are keyed with eight slots", bool(keys) and all(len(k.split("|")) == 8 for k in keys), str([len(k.split("|")) for k in keys]))
        html = api.post(site.url + "api/grammar/zz_eight", headers={"Content-Type": "application/json"}, data=json.dumps({"source": "{{cite: fieldnotes#0#d01.Road:09}}"})).json().get("html", "")
        abbr = re.findall(r'cite-fn-abbr[^>]*>([^<]*)<', html)
        check(S, "eight languages: a grammar citation has eight labelled rows", abbr == [l["abbr"] for l in eight], str(abbr))
        api.delete(site.url + "api/grammar/zz_eight")
        tex = api.get(site.url + "api/grammar/export/latex").text()
        check(S, "eight languages: the LaTeX export defines eight colours", tex.count("\\definecolor") == 8, str(tex.count("\\definecolor")))
        open_page(page, site, "about.html", ".lang-section", 1000)
        check(S, "eight languages: eight sections on the about page, and eight lines in its contents", page.locator(".lang-section").count() == 8 and page.locator(".about-toc li.sub").count() == 8)
        open_page(page, site, "index.html", ".lang-strip", 1000)
        check(S, "eight languages: eight cells in the home page's language strip", page.locator(".lang-strip .lang-cell").count() == 8)
        page.set_viewport_size({"width": 600, "height": 900})
        over = []
        for name, path, sel in (("dictionary", "dictionary.html", "#dict-content .entry"), ("text view", "transcription.html?fieldnotes=1&index=0&title=D01", ".tx-phrase"), ):
            open_page(page, site, path, sel, 1800)
            over += [name for _ in [0] if page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")]
        check(S, "eight languages: nothing scrolls sideways on a narrow screen", not over, str(over))
        open_page(page, site, "index.html", ".lang-strip", 1000)
        check(S, "eight languages: the home page's language strip fits a narrow screen", page.evaluate("(() => { const s = document.querySelector('.lang-strip'); return s.scrollWidth <= s.clientWidth + 1; })()"))
        check(S, "eight languages: no JavaScript or loading error", not errs, "; ".join(errs[:2]))
        ctx.close()
    finally:
        site.stop()

    # ── a project whose codes and names share nothing with the first one, with awkward characters ──
    section("languages: other codes, other names (an apostrophe, a hyphen, an ampersand)")
    odd = [{"code": "x1", "name": "Ma'a", "abbr": "Ma", "color": "#aa3300", "aliases": []},
           {"code": "lt-2", "name": "Lo-Toga", "abbr": "LT", "color": "#0033aa", "aliases": []},
           {"code": "ab_3", "name": "A&B", "abbr": "A&B", "color": "#00aa33", "aliases": []}]
    site = Site(project_override=variant(odd)); errs = []
    try:
        ctx = new_context(browser, site, 1280, author=True); page = ctx.new_page(); watch(page, errs); api = ctx.request
        open_page(page, site, "dictionary.html", "#dict-content .entry", 1500)
        pills = page.locator(".hw-lang-pill").all_inner_texts()
        check(S, "odd names: the language buttons show the names as written", [p.strip().lower() for p in pills] == ["ma'a", "lo-toga", "a&b"], str(pills))
        for nm in ("Lo-Toga", "A&B", "Ma'a"):
            page.locator(".hw-lang-pill", has_text=nm).first.click(); page.wait_for_timeout(500)
        check(S, "odd names: every language can be chosen as the headword language", "active" in (page.locator(".hw-lang-pill", has_text="Ma'a").first.get_attribute("class") or ""))
        page.click("#add-entry-btn"); page.wait_for_timeout(300)
        page.fill("#ef-lt-2", "toga"); page.fill("#ef-pos", "n."); page.locator(".em-sense").first.locator('[data-f="definition"]').fill("odd-code test")
        page.click("#em-submit"); page.wait_for_timeout(1500)
        check(S, "odd names: an entry in a language with a hyphenated code is saved", xml_langs(site, "toga") == {"lt-2": "toga"}, str(xml_langs(site, "toga")) if True else "")
        page.reload(wait_until="domcontentloaded"); page.wait_for_timeout(1500)
        page.locator('[id="ea-toga"] >> text=Edit').click(); page.wait_for_timeout(500)
        check(S, "odd names: the editor shows the saved form in the right row", page.input_value("#ef-lt-2") == "toga")
        page.click("#em-cancel")
        page.click("#settings-btn"); page.wait_for_timeout(900)
        check(S, "odd names: the Settings list the three languages", page.locator(".st-color label").all_inner_texts() == ["Ma'a", "Lo-Toga", "A&B"])
        page.click("#st-cancel")
        for name, path, sel in (("grammar", "grammar.html", "#sections-container .grammar-section"), ("texts", "texts.html", "#texts-grid .text-card"),
                                ("fieldnotes view", "transcription.html?fieldnotes=1&index=0&title=D01", ".tx-phrase"),
                                ("recording view", "transcription.html?key=crdo-WWO_FARFADETS.xml&title=Farfadets&lang=wwo", ".tx-phrase")):
            open_page(page, site, path, sel, 1500)
        open_page(page, site, "texts.html", "#texts-grid .text-card", 1200)
        opts = page.locator("#filter-lang option").all_inner_texts()
        check(S, "odd names: the Texts filter lists them", opts[1:] == ["Ma'a", "Lo-Toga", "A&B"], str(opts))
        r = api.post(site.url + "api/grammar/zz_odd", headers={"Content-Type": "application/json"}, data=json.dumps({"source": "{{cite: fieldnotes#0#d01.Road:09}}\n\n{{entry: know}}"}))
        check(S, "odd names: a citation and an entry chip render without a server error", r.status == 200, f"HTTP {r.status}")
        tex = api.get(site.url + "api/grammar/export/latex")
        body = tex.text().split("\\begin{document}")[-1] if tex.status == 200 else ""
        check(S, "odd names: the LaTeX export defines a colour for each language", tex.status == 200 and tex.text().count("\\definecolor") == 3, f"HTTP {tex.status}")
        check(S, "odd names: an ampersand in a language abbreviation is escaped in LaTeX (A\\&B, never a raw &)", "A\\&B" in body and not re.search(r"(?<!\\)A&B", body))
        api.delete(site.url + "api/grammar/zz_odd")
        check(S, "odd names: no JavaScript or loading error on any page", not errs, "; ".join(errs[:3]))
        ctx.close()
    finally:
        site.stop()

    # ── a project that has not written its home and about pages (yet) ──
    section("languages: a project without page content")
    site = Site(project_override=variant([dict(l) for l in five], footer=""), drop_pages=True); errs = []
    try:
        ctx = new_context(browser, site, 1280, author=False); page = ctx.new_page(); watch(page, errs); api = ctx.request
        open_page(page, site, "index.html", ".lang-strip", 1000)
        hrefs = page.locator(".lang-strip a").evaluate_all("els => els.map(e => e.getAttribute('href'))")
        check(S, "no page content: the home page still works, without a map section or footer", page.locator(".map-section").count() == 0 and page.locator("footer").count() == 0 and page.locator(".dbt-card").count() == 3)
        check(S, "no page content: the language strip points to the dictionary", hrefs == [f"dictionary.html?lang={l['name']}" for l in five], str(hrefs[:2]))
        check(S, "no page content: there is no about page", api.get(site.url + "about.html").status == 404 and api.get(site.url + "gaua.html").status in (301, 404))
        check(S, "no page content: no JavaScript or loading error", not errs, "; ".join(errs[:2]))
        ctx.close()
    finally:
        site.stop()

    # ── a language added later: column keys stored under five slots ──
    section("languages: a language added after data was stored")
    six = [dict(l) for l in five] + EXTRA_LANGS[:1]
    site = Site(project_override=variant(six)); errs = []
    try:
        (site.dir / "project" / "texts" / "confirmed_glosses.json").write_text(json.dumps({"A|B|c|d|e": ["OLD"]}), encoding="utf-8")
        ctx = new_context(browser, site, 1280, author=True); page = ctx.new_page(); watch(page, errs)
        open_page(page, site, "transcription.html?fieldnotes=1&index=0&title=D01", ".tx-phrase", 1800)
        keys = page.evaluate("Object.keys(textsConcordance)")
        check(S, "a language added later: keys stored under five slots are read with six (and lower-cased)", "a|b|c|d|e|" in keys, str(keys[:3]))
        check(S, "a language added later: no JavaScript or loading error", not errs, "; ".join(errs[:2]))
        ctx.close()
    finally:
        site.stop()


# ───────────────────────── 6. security suite: the password and the keys ─────────────────────────
def _login(api, site, pw):
    return api.post(site.url + "api/auth/login", data=json.dumps({"password": pw}), headers={"Content-Type": "application/json"})

def suite_security(browser, site, args):
    S = "security"
    section("security: the password and the keys")
    needles = ["gaua" + "2026", "dev-secret" + "-change"]
    hits = {}
    for f in ROOT.rglob("*"):
        rel = f.relative_to(ROOT)
        if not f.is_file() or any(p in ("tests", ".git", "instance", "uploads", "__pycache__", "venv", ".venv") for p in rel.parts): continue
        try: txt = f.read_text(encoding="utf-8")
        except Exception: continue
        found = [n for n in needles if n in txt]
        if found: hits[str(rel)] = found
    check(S, "no password and no signing key is written in any file of the project", not hits, str(hits))
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    check(S, ".gitignore keeps instance/ (the secrets) and uploads/ out of git", "instance/" in gi and "uploads/" in gi)

    anon = new_context(browser, site, author=False); api = anon.request
    bad = [p for p in ("security.py", "setup.html", "setup", "instance/author.json", "starter/project.json", "starter/dictionary.xml") if api.get(site.url + p).status != 404]
    check(S, "the secrets, the security code, the starter files and the setup page are not served once the DBT is set up", not bad, str(bad))
    check(S, "login: a wrong password is refused", _login(api, site, "not the password").status == 401)
    check(S, "login: the password that was once published is refused", _login(api, site, "gaua" + "2026").status == 401)
    check(S, "login: the right password is accepted", _login(api, site, PASSWORD).status == 200)
    anon.close()

    # too many wrong passwords
    s2 = Site()
    try:
        c = new_context(browser, s2, author=False); a = c.request
        codes = [_login(a, s2, f"wrong-{i}").status for i in range(5)]
        r = _login(a, s2, PASSWORD)
        check(S, "login: after five wrong passwords the address is locked out, even for the right password", codes == [401] * 5 and r.status == 429, f"{codes} then {r.status}")
        check(S, "login: the refusal says how long to wait", "Try again" in r.json().get("error", ""), str(r.json()))
        c.close()
    finally:
        s2.stop()

    # changing the password: stored hashed, the file wins over the environment, a forged cookie is useless
    s3 = Site()
    try:
        c = new_context(browser, s3, author=True); a = c.request; H = {"Content-Type": "application/json"}
        chg = lambda cur, new: a.post(s3.url + "api/auth/password", data=json.dumps({"current": cur, "new": new}), headers=H)
        check(S, "password change: refused when the current password is wrong", chg("nope", "Brand-new-pass-77").status == 403)
        check(S, "password change: refused when the new one is too short", chg(PASSWORD, "short").status == 400)
        check(S, "password change: refused for the password that was once published", chg(PASSWORD, "gaua" + "2026").status == 400)
        check(S, "password change: accepted with the current password", chg(PASSWORD, "Brand-new-pass-77").status == 200)
        raw = (s3.dir / "instance" / "author.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        check(S, "the password is stored only as a hash (never in clear)", data.get("passwordHash", "").startswith(("scrypt:", "pbkdf2:")) and "Brand-new-pass-77" not in raw and PASSWORD not in raw)
        check(S, "the signing key is random, long, and kept in instance/", len(data.get("secretKey", "")) >= 64)
        c2 = new_context(browser, s3, author=False)
        check(S, "after the change the new password works and the old one does not", _login(c2.request, s3, "Brand-new-pass-77").status == 200 and _login(c2.request, s3, PASSWORD).status == 401)
        # a login cookie forged with the key that used to be written in the code
        from flask import Flask
        from flask.sessions import SecureCookieSessionInterface
        fake = Flask("forger"); fake.secret_key = "dev-secret" + "-change-in-production"
        cookie = SecureCookieSessionInterface().get_signing_serializer(fake).dumps({"author": True})
        c3 = new_context(browser, s3, author=False)
        r = c3.request.get(s3.url + "api/dictionary/settings", headers={"Cookie": f"session={cookie}"})
        check(S, "a login cookie forged with the old key in the code does not work", r.status == 401, f"HTTP {r.status}")
        c.close(); c2.close(); c3.close()
    finally:
        s3.stop()

    # no password set at all, and the command-line tool
    s4 = Site(env_unset=["AUTHOR_PASSWORD"])
    try:
        c = new_context(browser, s4, author=False); a = c.request
        r = _login(a, s4, "anything")
        check(S, "no password set: nobody can log in, and the message says what to do", r.status == 403 and "--set-password" in r.json().get("error", ""), f"{r.status} {r.json()}")
        cli = lambda text: subprocess.run([sys.executable, "app.py", "--set-password"], cwd=s4.dir, input=text, capture_output=True, text=True, timeout=60)
        check(S, "--set-password: two different passwords change nothing", (lambda r: r.returncode == 1 and not ((s4.dir / "instance" / "author.json").exists() and "passwordHash" in (s4.dir / "instance" / "author.json").read_text(encoding="utf-8")))(cli("Valid-pass-123\nOther-pass-456\n")))
        check(S, "--set-password: the published password is refused", cli("gaua" + "2026\n" + "gaua" + "2026\n").returncode == 1)
        ok = cli("Valid-pass-123\nValid-pass-123\n")
        data = json.loads((s4.dir / "instance" / "author.json").read_text(encoding="utf-8"))
        check(S, "--set-password: stores the hash of a good password", ok.returncode == 0 and "Valid-pass-123" not in json.dumps(data) and data.get("passwordHash"), ok.stdout + ok.stderr)
        check(S, "--set-password: the running server accepts it at once, without a restart", _login(a, s4, "Valid-pass-123").status == 200)
        c.close()
    finally:
        s4.stop()

    # the Settings dialog
    s5 = Site()
    try:
        c = new_context(browser, s5, 1280, author=True); page = c.new_page(); errs = []; watch(page, errs)
        open_page(page, s5, "dictionary.html?lang=Koro", "#dict-content .entry", 1500)
        page.click("#settings-btn"); page.wait_for_timeout(800)
        page.locator(".st-pw summary").click()
        def attempt(cur, new, new2):
            page.fill("#pw-current", cur); page.fill("#pw-new", new); page.fill("#pw-new2", new2); page.click("#pw-change"); page.wait_for_timeout(1200)
            return page.inner_text("#pw-msg")
        check(S, "Settings: two different new passwords are refused", "differ" in attempt(PASSWORD, "Another-pass-1", "Another-pass-2"))
        check(S, "Settings: a wrong current password is refused", "not right" in attempt("nope", "Another-pass-1", "Another-pass-1"))
        check(S, "Settings: the password can be changed from the page", "Password changed" in attempt(PASSWORD, "Another-pass-1", "Another-pass-1"))
        real = [e for e in errs if "api/auth/password" not in e]          # the 403 / 400 answers to the wrong attempts above are expected
        check(S, "Settings: no JavaScript or loading error", not real, "; ".join(real[:2]))
        c.close()
    finally:
        s5.stop()

# ───────────────────────── 7. setup suite: the first run of a new project ─────────────────────────
def suite_setup(browser, args):
    from lxml import etree
    S = "setup"
    section("setup: the first run of a new project")
    site = Site(setup_mode=True)
    try:
        code = site.setup_code()
        check(S, "the server prints a setup code in its console", len(code) >= 8, code)
        ctx = new_context(browser, site, 1280); page = ctx.new_page(); errs = []; watch(page, errs); api = ctx.request
        r = api.get(site.url, max_redirects=0)
        check(S, "before the setup, every page leads to the setup page", r.status == 302 and r.headers.get("location", "").endswith("/setup"), f"{r.status} {r.headers.get('location')}")
        check(S, "before the setup, the data is not available and other addresses lead to the setup page",
              api.get(site.url + "api/dictionary/entries").status == 503 and api.get(site.url + "dictionary.html", max_redirects=0).status == 302)
        H = {"Content-Type": "application/json"}
        post = lambda body: api.post(site.url + "api/setup", data=json.dumps(body), headers=H)
        good = dict(name="Mini DBT", mode="own", password="a-good-password-1", setupCode=code,
                    languages=[{"name": "A", "code": "aa", "abbr": "A", "color": "#112233"}])
        check(S, "setup: a wrong setup code is refused", post(dict(good, setupCode="nope")).status == 403)
        check(S, "setup: the published password is refused", post(dict(good, password="gaua" + "2026")).status == 400)
        check(S, "setup: a project needs a name", post(dict(good, name=" ")).status == 400)
        check(S, "setup: a language code must be lower case letters and digits", post(dict(good, languages=[dict(good["languages"][0], code="1Bad")])).status == 400)
        check(S, "setup: two languages cannot share a code", post(dict(good, languages=[good["languages"][0], dict(good["languages"][0], name="B")])).status == 400)
        af = site.dir / "instance" / "author.json"          # (the signing key is created at start-up; the password must not be)
        check(S, "setup: nothing is written when the request is refused", not (site.dir / "project" / "project.json").exists() and not (af.exists() and "passwordHash" in af.read_text(encoding="utf-8")))

        # the page itself, and a project with the author's own languages
        open_page(page, site, "setup", "#setup", 800)
        page.fill("#name", "Mini DBT")
        page.locator('#langs [data-f="name"]').first.fill("Mwotlap")
        first = (page.locator('#langs [data-f="abbr"]').first.input_value(), page.locator('#langs [data-f="code"]').first.input_value())
        check(S, "the setup page suggests an abbreviation and a code from the name", first == ("Mwo", "mwo"), str(first))
        page.click("#add-lang"); page.locator('#langs [data-f="name"]').nth(1).fill("Lo-Toga")
        page.click("#add-lang"); page.locator('#langs [data-f="name"]').nth(2).fill("Third")
        page.locator("#langs [data-del]").nth(2).click()
        check(S, "the setup page can add and remove languages", page.locator("#langs tr").count() == 2)
        page.click("#mode-starter"); hidden = not page.locator("#langs-box").is_visible(); page.click("#mode-own")
        check(S, "the setup page hides the language table when the example is chosen", hidden and page.locator("#langs-box").is_visible())
        page.fill("#pw", "a-good-password-1"); page.fill("#pw2", "different-password"); page.fill("#code", code); page.click("#go"); page.wait_for_timeout(600)
        check(S, "the setup page refuses two different passwords", "differ" in page.inner_text("#msg"))
        page.fill("#pw2", "a-good-password-1"); page.fill("#code", "wrong"); page.click("#go"); page.wait_for_timeout(1000)
        check(S, "the setup page shows the server's refusal of a wrong code", "setup code is not right" in page.inner_text("#msg"))
        page.fill("#code", code); page.click("#go")
        try:
            page.wait_for_url(site.url, timeout=45000); landed = True
        except Exception:
            landed = False
        check(S, "after the setup the page waits for the restart and opens the new site", landed, page.url)
        page.wait_for_timeout(1500)
        proj = json.loads((site.dir / "project" / "project.json").read_text(encoding="utf-8"))
        check(S, "the project file holds the name and the languages that were typed", proj["name"] == "Mini DBT" and [l["code"] for l in proj["languages"]] == ["mwo", "lot"] and [l["name"] for l in proj["languages"]] == ["Mwotlap", "Lo-Toga"], str(proj["languages"]))
        check(S, "the password is stored hashed, not in the project", "a-good-password-1" not in json.dumps(proj) and (site.dir / "instance" / "author.json").exists())
        check(S, "the site now carries the project's name", "◬ Mini DBT" in api.get(site.url + "index.html").text() and api.get(site.url + "setup").status == 404)
        # the author logs in and adds a first entry to the empty dictionary
        a2 = new_context(browser, site, 1280); r = _login(a2.request, site, "a-good-password-1")
        check(S, "the author can log in with the password chosen at the setup", r.status == 200)
        p2 = a2.new_page(); e2 = []; watch(p2, e2)
        open_page(p2, site, "dictionary.html", "#dict-content", 1500)
        check(S, "the dictionary starts empty, with a button per language", p2.locator(".hw-lang-pill").count() == 2 and p2.locator("#dict-content .entry").count() == 0)
        p2.click(".auth-btn.login-btn") if p2.locator(".auth-btn.login-btn").is_visible() else None
        p2.fill("#login-pw", "a-good-password-1") if p2.locator("#login-pw").is_visible() else None
        if p2.locator("#login-submit").is_visible(): p2.click("#login-submit"); p2.wait_for_timeout(900)
        p2.click("#add-entry-btn"); p2.wait_for_timeout(300)
        p2.fill("#ef-lot", "toga"); p2.fill("#ef-pos", "n."); p2.locator(".em-sense").first.locator('[data-f="definition"]').fill("first entry")
        p2.click("#em-submit"); p2.wait_for_timeout(1500)
        d = etree.parse(str(site.dir / "project" / "dictionary.xml")).getroot()
        check(S, "the first entry is saved into the project's own dictionary file", len(d.findall(".//EntréeLexicale")) == 1 and d.find('.//Lemme/ReprésentationDeForme[@langue="lot"]').text == "toga")
        rj = json.loads((site.dir / "project" / "references.json").read_text(encoding="utf-8"))
        open_page(p2, site, "references.html", "#refs-list", 800)
        check(S, "a new project gets an empty list of references, and its References page says so", rj == {"references": []} and "No references yet" in p2.locator("#refs-list").inner_text())
        real = [e for e in errs + e2 if "/api/setup" not in e and "/api/auth/status" not in e]    # the refusals and the wait for the restart are expected
        check(S, "no JavaScript or loading error", not real, "; ".join(real[:2]))
        ctx.close(); a2.close()
    finally:
        site.stop()

    # the small starter example
    site = Site(setup_mode=True)
    try:
        code = site.setup_code(); ctx = new_context(browser, site, 1280); api = ctx.request
        r = api.post(site.url + "api/setup", data=json.dumps(dict(name="Starter DBT", mode="starter", password="a-good-password-1", setupCode=code, languages=[])), headers={"Content-Type": "application/json"})
        check(S, "starter: the setup is accepted", r.status == 200 and r.json().get("restart") == "auto", str(r.text())[:100])
        check(S, "starter: the server restarts by itself", site.wait_restart())
        page = ctx.new_page(); errs = []; watch(page, errs)
        open_page(page, site, "index.html", ".lang-strip", 1000)
        check(S, "starter: the home page shows the project's name and its language", "Starter DBT" in page.title() and page.locator(".lang-strip .lname").all_inner_texts() == ["Example"])
        open_page(page, site, "dictionary.html", "#dict-content .entry", 1500)
        check(S, "starter: the dictionary has its four entries, with no automatic IPA (no table is defined)", page.locator("#dict-content .entry").count() == 4 and page.locator(".ipa-badge").count() == 0)
        open_page(page, site, "texts.html", "#texts-grid .text-card", 1500)
        card = page.locator(".text-card").first.inner_text()
        check(S, "starter: the Texts page lists the example text, in the project's language", "A first example text" in card and "Example" in card, card.replace("\n", " ")[:80])
        open_page(page, site, "transcription.html?key=example-text.xml&title=x&lang=ex", ".tx-phrase", 1500)
        check(S, "starter: the text opens with its four phrases", page.locator(".tx-phrase").count() == 4)
        open_page(page, site, "grammar.html", "#sections-container .grammar-section", 2000)
        body = page.locator("#sections-container").inner_text()
        check(S, "starter: the grammar cites the text and shows the entry", "Tamo neme" in body and "The house is good" in body and "tamo" in body.lower())
        cites = page.locator("#sections-container .source-cite").all_inner_texts()
        check(S, "starter: the grammar cites its references (with a page; narrative with two authors)", cites == ["Smith, 2020, p. 14", "Smith and Rivera (2021)"] and not page.locator("#sections-container .shortcode-error").count(), str(cites))
        open_page(page, site, "references.html", ".ref-entry", 800)
        check(S, "starter: the References page lists its two invented references in APA style", [x.strip() for x in page.locator(".ref-text").all_inner_texts()] == [
            "Smith, J. (2020). A sketch of the Example language. Example University Press.",
            "Smith, J., & Rivera, A. (2021). Reduplication in Example. Journal of Invented Languages, 12(3), 201–224. https://doi.org/10.0000/jil.2021.12.3.201"])
        a3 = new_context(browser, site, author=False)
        check(S, "starter: the password chosen at the setup works, the old published one does not", _login(a3.request, site, "a-good-password-1").status == 200 and _login(a3.request, site, "gaua" + "2026").status == 401)
        check(S, "starter: no JavaScript or loading error", not errs, "; ".join(errs[:2]))
        ctx.close(); a3.close()
    finally:
        site.stop()


# ───────────────────────── 8. migration suite: live data moves into the project folder ─────────────────────────
_LIVE_ENTRY = ('<EntréeLexicale identifiant="zzlive"><Lemme><ReprésentationDeForme langue="kro">zzlive</ReprésentationDeForme></Lemme>'
               '<ClasseGrammaticale>n.</ClasseGrammaticale><Sens identifiant="zzliveⓢ1"><NuméroDeSens>1</NuméroDeSens>'
               '<Glose langue="eng">a live entry</Glose><gloss>live</gloss></Sens></EntréeLexicale>')

def _live_state(d):
    """The folder as it is when the new code lands on a LIVE installation: the data edited in the browser is at the
    OLD places, while the shipped copies are at the NEW ones (as after a git pull)."""
    proj = d / "project"
    xml = (proj / "dictionary.xml").read_text(encoding="utf-8")
    (d / "dbt_dictionary.xml").write_text(xml.replace("</Dictionnaire>", _LIVE_ENTRY + "</Dictionnaire>"), encoding="utf-8")
    shutil.copy(proj / "fieldnotes.xml", d / "AlexFrancois_Questionnaire_Gaua-languages.xml")
    (d / "grammar_content").mkdir()
    (d / "grammar_content" / "s1.md").write_text((proj / "grammar" / "s1.md").read_text(encoding="utf-8") + "\n\nLIVE EDIT paragraph.\n", encoding="utf-8")
    (d / "grammar_content" / "live-only.md").write_text("## Live only\n\nA section written in the browser.\n", encoding="utf-8")
    tn = d / "transcribed_narratives"; (tn / "glosses").mkdir(parents=True)
    shutil.copy(proj / "texts" / "crdo-WWO_FARFADETS.xml", tn / "crdo-WWO_FARFADETS.xml")
    (tn / "Live_only.xml").write_text('<?xml version="1.0" encoding="utf-8"?>\n<TEXT xml:lang="wwo" id="live-only"><HEADER><TITLE xml:lang="en">A live text</TITLE></HEADER>'
                                      '<S id="lo1"><FORM>Tuar.</FORM><TRANSL xml:lang="en">Once.</TRANSL></S></TEXT>', encoding="utf-8")
    g = json.loads((proj / "texts" / "glosses" / "fieldnotes_0.json").read_text(encoding="utf-8"))
    g["d01.Road:01"]["glosses"][0] = "LIVEMORNING"
    (tn / "glosses" / "fieldnotes_0.json").write_text(json.dumps(g), encoding="utf-8")
    (d / "images").mkdir(); (d / "images" / "live.png").write_bytes(b"\x89PNG live")

def _only_legacy(d):
    """Only the old places hold data (the new code was pulled, but not the data folders)."""
    _live_state(d)
    proj = d / "project"
    for rel in ("dictionary.xml", "fieldnotes.xml"): (proj / rel).unlink()
    for rel in ("grammar", "texts", "images"): shutil.rmtree(proj / rel)

def _blocked(d):
    """A move that cannot be completed: the new place of the dictionary is a folder."""
    _live_state(d)
    (d / "project" / "dictionary.xml").unlink(); (d / "project" / "dictionary.xml").mkdir()

def suite_migration(browser, args):
    S = "migration"
    section("migration: live data moves into the project folder")
    OLD = ("dbt_dictionary.xml", "AlexFrancois_Questionnaire_Gaua-languages.xml", "grammar_content", "transcribed_narratives", "images")

    def check_live(site, label):
        d = site.dir / "project"
        check(S, f"{label}: the server says what it moved", "Your data now lives in the project folder" in site.log_text())
        left = [p for p in OLD if (site.dir / p).exists()]
        check(S, f"{label}: the old locations are gone", not left, str(left))
        check(S, f"{label}: the dictionary is the live one (an entry added in the browser survives)", "zzlive" in (d / "dictionary.xml").read_text(encoding="utf-8"))
        check(S, f"{label}: the live grammar edits, the section written in the browser, the live-only text, the glosses and the images are all there",
              "LIVE EDIT" in (d / "grammar" / "s1.md").read_text(encoding="utf-8") and (d / "grammar" / "live-only.md").exists()
              and (d / "texts" / "Live_only.xml").exists() and "LIVEMORNING" in (d / "texts" / "glosses" / "fieldnotes_0.json").read_text(encoding="utf-8")
              and (d / "images" / "live.png").exists() and (d / "fieldnotes.xml").exists())
        bk = list((site.dir / "uploads" / "backups").glob("legacy-layout-*"))
        check(S, f"{label}: a full backup of the old locations was made first",
              len(bk) == 1 and "zzlive" in (bk[0] / "dbt_dictionary.xml").read_text(encoding="utf-8") and (bk[0] / "grammar_content" / "live-only.md").exists()
              and (bk[0] / "transcribed_narratives" / "Live_only.xml").exists() and (bk[0] / "images" / "live.png").exists())
        mk = site.json("uploads/layout-migrated.json")
        check(S, f"{label}: the move is recorded (so that it happens only once)", len(mk.get("moved", [])) == 5, str(mk)[:80])
        ctx = new_context(browser, site, 1280); page = ctx.new_page(); errs = []; watch(page, errs); api = ctx.request
        open_page(page, site, "dictionary.html?lang=Koro", "#dict-content .entry", 1500)
        check(S, f"{label}: the dictionary shows the live entry and the others (nine entries)", page.locator("#dict-content .entry").count() == 9 and "zzlive" in page.locator("#dict-content").inner_text())
        open_page(page, site, "texts.html", "#texts-grid .text-card", 1500)
        check(S, f"{label}: the Texts page lists the live-only text", "A live text" in page.locator("#texts-grid").inner_text())
        html = api.get(site.url + "api/grammar/s1").json().get("html", "")
        check(S, f"{label}: the grammar shows the live edit and the live gloss", "LIVE EDIT" in html and 'data-gloss="LIVEMORNING"' in html)
        check(S, f"{label}: the picture saved in the browser is served", api.get(site.url + "images/live.png").status == 200)
        check(S, f"{label}: no JavaScript or loading error", not errs, "; ".join(errs[:2]))
        ctx.close()

    # 1. live data at the old places, shipped copies at the new ones (what a git pull leaves)
    site = Site(prepare=_live_state)
    try:
        check_live(site, "live data beside shipped copies")
        stale = (site.dir / "project" / "dictionary.xml").read_text(encoding="utf-8").replace(_LIVE_ENTRY, "")
        (site.dir / "dbt_dictionary.xml").write_text(stale, encoding="utf-8")          # an old file comes back (e.g. through git)
        out = site.restart()
        check(S, "a second start does not move anything again: a returning old file cannot overwrite live data",
              "Your data now lives" not in out and (site.dir / "dbt_dictionary.xml").exists() and "zzlive" in (site.dir / "project" / "dictionary.xml").read_text(encoding="utf-8"))
    finally:
        site.stop()

    # 2. only the old places hold data
    site = Site(prepare=_only_legacy)
    try:
        check_live(site, "live data only")
    finally:
        site.stop()

    # 3. a move that cannot be completed deletes nothing
    site = Site(prepare=_blocked, expect_failure=True)
    try:
        check(S, "a move that cannot be completed stops the server with a message", not site.started and "Could not move the data" in site.log_text())
        check(S, "…and deletes nothing: the live data is still where it was",
              "zzlive" in (site.dir / "dbt_dictionary.xml").read_text(encoding="utf-8") and (site.dir / "grammar_content" / "live-only.md").exists()
              and (site.dir / "transcribed_narratives" / "Live_only.xml").exists() and (site.dir / "images" / "live.png").exists())
        check(S, "…and records nothing as moved, so the next start tries again", not (site.dir / "uploads" / "layout-migrated.json").exists())
    finally:
        site.stop()


# ───────────────────────── 9. references suite: the bibliography, APA 7, citations, exports ─────────────────────────
FRANCOIS_APA = ("François, A. (2026b). Negation in Dorig. In M. Miestamo & L. Veselinova (Eds.), Negation in the world’s languages III: "
                "Papunesia, Australia, and the Americas (pp. 73–128). Language Science Press. https://doi.org/10.5281/zenodo.18234067")
_H = {"Content-Type": "application/json"}

def _jcall(api, method, url, data=None):
    kw = {"headers": _H, "data": json.dumps(data)} if data is not None else {}
    r = getattr(api, method)(url, **kw)
    try: return r.status, r.json()
    except Exception: return r.status, r.text()

def _P(f, g=""): return {"family": f, "given": g} if g else {"family": f}

# each example below is a template or example of the UTS "APA 7th referencing guide" (expected = the guide's reference-list line)
_APA_CASES = [
    ("journal article, one author", dict(type="article", authors=[_P("Alderton", "Z.")], year="2014", title="“Snapewives” and “Snapeism”: A fiction-based religion within the Harry Potter fandom", container="Religions", volume="5", issue="1", pages="219-267", doi="10.3390/rel5010219"),
     "Alderton, Z. (2014). “Snapewives” and “Snapeism”: A fiction-based religion within the Harry Potter fandom. Religions, 5(1), 219–267. https://doi.org/10.3390/rel5010219"),
    ("journal article, three authors", dict(type="article", authors=[_P("Gursoy", "A."), _P("Wickett", "K."), _P("Feinberg", "M.")], year="2018", title="Understanding tag functions in a moderated, user-generated metadata ecosystem", container="Journal of Documentation", volume="74", issue="3", pages="490-508", doi="10.1108/JD-09-2017-0134"),
     "Gursoy, A., Wickett, K., & Feinberg, M. (2018). Understanding tag functions in a moderated, user-generated metadata ecosystem. Journal of Documentation, 74(3), 490–508. https://doi.org/10.1108/JD-09-2017-0134"),
    ("edited book, two editors", dict(type="edited", authors=[_P("Burley", "J."), _P("Harris", "J.")], year="2008", title="A companion to genetics", edition="2", publisher="John Wiley & Sons"),
     "Burley, J., & Harris, J. (Eds.). (2008). A companion to genetics (2nd ed.). John Wiley & Sons."),
    ("chapter: edition, volume, pages, title ending in ?", dict(type="chapter", authors=[_P("Slee", "R.")], year="2014", title="Inclusive schooling as an apprenticeship in democracy?", editors=[_P("Florian", "L.")], container="The SAGE handbook of special education", edition="2", volume="1", pages="217-229", publisher="SAGE Publications"),
     "Slee, R. (2014). Inclusive schooling as an apprenticeship in democracy? In L. Florian (Ed.), The SAGE handbook of special education (2nd ed., Vol. 1, pp. 217–229). SAGE Publications."),
    ("doctoral dissertation from a database", dict(type="thesis", authors=[_P("Hollander", "M.")], year="2017", title="Resistance to authority: Methodological innovations and new lessons from the Milgram experiment", number="Publication No. 10289373", level="Doctoral dissertation", institution="University of Wisconsin-Madison", publisher="ProQuest Dissertations and Theses Global"),
     "Hollander, M. (2017). Resistance to authority: Methodological innovations and new lessons from the Milgram experiment (Publication No. 10289373) [Doctoral dissertation, University of Wisconsin-Madison]. ProQuest Dissertations and Theses Global."),
    ("conference paper with a date range", dict(type="conference", authors=[_P("Campbell", "K.")], year="2019", dateText="October 28-29", title="An information behaviours view of first in family students before and during university", container="Research Applications in Information and Library Studies", place="Canberra, ACT, Australia"),
     "Campbell, K. (2019, October 28–29). An information behaviours view of first in family students before and during university [Paper presentation]. Research Applications in Information and Library Studies, Canberra, ACT, Australia."),
    ("data set by an organisation, retrieved", dict(type="dataset", authors=[{"org": "Pew Research Center"}], year="2018", title="American trends panel Wave 26", accessed="October 21, 2019", url="https://www.pewsocialtrends.org/dataset/american-trends-panel-wave-26/"),
     "Pew Research Center. (2018). American trends panel Wave 26 [Data set]. Retrieved October 21, 2019, from https://www.pewsocialtrends.org/dataset/american-trends-panel-wave-26/"),
    ("unpublished manuscript", dict(type="unpublished", authors=[_P("Yoo", "J."), _P("Miyamoto", "Y."), _P("Rigotti", "A."), _P("Ryff", "C.")], year="2016", title="Linking positive affect to blood lipids: A cultural perspective", publisher="Department of Psychology, University of Wisconsin-Madison"),
     "Yoo, J., Miyamoto, Y., Rigotti, A., & Ryff, C. (2016). Linking positive affect to blood lipids: A cultural perspective [Unpublished manuscript]. Department of Psychology, University of Wisconsin-Madison."),
    ("web page, organisation (site name omitted when it is the author)", dict(type="web", authors=[{"org": "World Health Organization"}], year="2022", dateText="July 14", title="Immunization coverage", container="World Health Organization", url="https://www.who.int/news-room/fact-sheets/detail/immunization-coverage"),
     "World Health Organization. (2022, July 14). Immunization coverage. https://www.who.int/news-room/fact-sheets/detail/immunization-coverage"),
]

def suite_references(browser, args):
    S = "references"
    section("references: the bibliography in APA 7, {{source: …}} citations, BibTeX and EndNote")
    unit = subprocess.run([sys.executable, str(ROOT / "tests" / "test_references.py")], capture_output=True, text=True, timeout=120)
    last = [l for l in unit.stdout.strip().split("\n") if l][-1] if unit.stdout.strip() else unit.stderr[-200:]
    check(S, "the formatting engine passes its own direct tests (APA 7 templates, initials, year letters, order, in-text, exports)", unit.returncode == 0, last + ("" if unit.returncode == 0 else "\n" + unit.stdout[-600:]))
    site = Site()
    try:
        vis = new_context(browser, site, 1280); va = vis.request
        au = new_context(browser, site, 1280, author=True); aa = au.request

        # ── the page, the navigation and what a visitor sees ──
        pages = ["index.html", "about.html", "grammar.html", "texts.html", "dictionary.html", "transcription.html", "references.html"]
        missing = [p for p in pages if 'href="references.html"' not in va.get(site.url + p).text()]
        check(S, "every page has the References link in its top bar", not missing, str(missing))
        check(S, "no project marker is left unexpanded on the References page", "{{project." not in va.get(site.url + "references.html").text())
        pg = vis.new_page(); errs = []; watch(pg, errs)
        open_page(pg, site, "references.html", ".ref-entry", 800)
        check(S, "a visitor sees the project's reference in APA 7, exactly as the guide and the author write it", [x.strip() for x in pg.locator(".ref-text").all_inner_texts()] == [FRANCOIS_APA], pg.locator(".ref-text").first.inner_text()[:90])
        check(S, "the title of the book is in italics, the DOI is a link", pg.locator(".ref-text em").all_inner_texts() == ["Negation in the world’s languages III: Papunesia, Australia, and the Americas"] and pg.locator('.ref-text a[href="https://doi.org/10.5281/zenodo.18234067"]').count() == 1)
        check(S, "the list has a hanging indent", pg.evaluate("parseFloat(getComputedStyle(document.querySelector('.ref-text')).textIndent) < 0"))
        check(S, "a visitor has no author tools (no Add, Edit, Delete, key or hint) but can export", not any(pg.locator(s).first.is_visible() for s in ("#ref-add", "[data-edit]", "[data-del]", ".ref-meta", ".refs-hint")) and pg.locator('a[href="/api/references/export/bibtex"]').is_visible() and pg.locator('a[href="/api/references/export/endnote"]').is_visible())
        check(S, "the top-bar label comes from the project", "Bibliography" in pg.locator(".topnav-right").inner_text() and pg.title().startswith("References"))
        check(S, "the page has no JavaScript or loading error", not errs, "; ".join(errs[:2]))

        # ── the formatting, through the real server (the guide's own examples) ──
        bad = []
        for name, data, want in _APA_CASES:
            st, j = _jcall(aa, "post", site.url + "api/references/preview", data)
            got = j["view"]["text"] if st == 200 and j.get("ok") else str(j)
            if got != want: bad.append(f"{name}: {got[:90]}")
        check(S, f"{len(_APA_CASES)} templates of the APA guide are reproduced to the letter (article, edited book, chapter, thesis, conference paper, data set, manuscript, web page ...)", not bad, " | ".join(bad))
        names = ["Kalnay", "Kanamitsu", "Kistler", "Collins", "Deaven", "Gandin", "Iredell", "Saha", "White", "Woollen", "Zhu", "Chelliah", "Ebisuzaki", "Higgins", "Janowial", "Mo", "Ropelewski", "Wang", "Leetmaa", "Reynolds", "Jenne", "Joseph"]
        st, j = _jcall(aa, "post", site.url + "api/references/preview", dict(type="article", authors=[_P(n, n[0]) for n in names], year="1996", title="The NCEP/NCAR 40-year reanalysis project", container="Bulletin of the American Meteorological Society", volume="77", issue="3", pages="437-471"))
        tx = j["view"]["text"]
        check(S, "21 or more authors: the first 19, an ellipsis and the last, as the guide says", tx.startswith("Kalnay, K., ") and "Leetmaa, L., … Joseph, J. (1996)." in tx and "Reynolds" not in tx, tx[-150:-60])
        for k, (data, why) in {"title": (dict(type="book", year="2020"), "no title"), "type": (dict(title="x", year="2020"), "no type"), "year": (dict(type="book", title="x", year="soon"), "a year that is not a year"),
                               "url": (dict(type="book", title="x", year="2020", url="javascript:alert(1)"), "a script URL"), "key": (dict(type="book", title="x", year="2020", id="Bad Key!"), "a key with spaces")}.items():
            st, _ = _jcall(aa, "post", site.url + "api/references", data)
            check(S, f"a reference with {why} is refused", st == 400)

        # ── who may change the bibliography ──
        st = [_jcall(va, "post", site.url + "api/references", dict(type="book", title="x", year="2020"))[0], _jcall(va, "put", site.url + "api/references/francois2026b", dict(type="book", title="x", year="2020"))[0],
              _jcall(va, "delete", site.url + "api/references/francois2026b")[0], _jcall(va, "post", site.url + "api/references/preview", dict(type="book", title="x", year="2020"))[0]]
        check(S, "a visitor cannot add, change, delete or preview a reference (401)", st == [401] * 4, str(st))

        # ── create, update, rename, delete ──
        def add(data): return _jcall(aa, "post", site.url + "api/references", data)
        cm = dict(type="article", authors=[_P("Collier", "K."), _P("McManus", "J.")], year="2005", container="J", volume="1")
        st, a1 = add(dict(cm, title="Setting up learning partnerships in vocational education and training: Lessons learnt"))
        st2, a2 = add(dict(cm, title="Bridging the gap: The use of learning partnerships to enhance workplace learning"))
        lst = _jcall(aa, "get", site.url + "api/references")[1]["references"]
        years = {r["id"]: r["yearDisplay"] for r in lst}
        check(S, "a key is made from the author and the year when none is given", a1.get("id") == "collier2005" and a2.get("id") == "collier2005-2", f"{a1} {a2}")
        check(S, "two works by the same authors in the same year get a and b, in the order of their titles (guide 11.08)", years == {"francois2026b": "2026b", "collier2005": "2005b", "collier2005-2": "2005a"}, str(years))
        check(S, "the list is in alphabetical order of the first author", [r["id"] for r in lst] == ["collier2005-2", "collier2005", "francois2026b"], str([r["id"] for r in lst]))
        check(S, "a key that is already used is refused (409)", add(dict(cm, title="t", id="collier2005"))[0] == 409)
        st, _ = _jcall(aa, "put", site.url + "api/references/collier2005", dict(cm, title="Setting up learning partnerships: A new title", id="collier2005"))
        check(S, "a reference can be changed", st == 200 and "A new title" in [r for r in _jcall(aa, "get", site.url + "api/references")[1]["references"] if r["id"] == "collier2005"][0]["text"])
        gdir = site.dir / "project" / "grammar"
        (gdir / "zz_rename.md").write_text("## §8 Rename\n\nSee {{source: collier2005, p. 4}} and {{source: francois2026b; collier2005}}, or {{source: COLLIER2005, narrative}}. Other: {{source: francois2026b}}.\n", encoding="utf-8")
        st, j = _jcall(aa, "put", site.url + "api/references/collier2005", dict(cm, title="Setting up learning partnerships: A new title", id="collier-mcmanus-b"))
        txt = (gdir / "zz_rename.md").read_text(encoding="utf-8")
        check(S, "changing a key updates the citations in the grammar (and only that key)", st == 200 and j.get("updatedGrammarSections") == ["zz_rename"] and "{{source: collier-mcmanus-b, p. 4}}" in txt and "{{source: francois2026b; collier-mcmanus-b}}" in txt and "{{source: collier-mcmanus-b, narrative}}" in txt and "{{source: francois2026b}}" in txt, txt)
        st, j = _jcall(aa, "put", site.url + "api/references/collier-mcmanus-b", dict(cm, title="t", id="francois2026b"))
        check(S, "a key cannot be changed to one that is taken (409)", st == 409)
        lst = _jcall(aa, "get", site.url + "api/references")[1]["references"]
        check(S, "the list says where each reference is cited", {r["id"]: r["citedIn"] for r in lst}["collier-mcmanus-b"] == ["zz_rename"] and {r["id"]: r["citedIn"] for r in lst}["francois2026b"] == ["zz_rename"])
        st, j = _jcall(aa, "delete", site.url + "api/references/collier-mcmanus-b")
        check(S, "deleting a cited reference says where it was cited", st == 200 and j.get("citedIn") == ["zz_rename"], str(j))
        check(S, "deleting a reference that does not exist is a 404", _jcall(aa, "delete", site.url + "api/references/nothing")[0] == 404 and _jcall(aa, "put", site.url + "api/references/nothing", dict(cm, title="t"))[0] == 404)
        _jcall(aa, "delete", site.url + "api/references/collier2005-2")
        stored = json.loads((site.dir / "project" / "references.json").read_text(encoding="utf-8"))
        check(S, "the references are kept in project/references.json, written whole", [r["id"] for r in stored["references"]] == ["francois2026b"] and not list((site.dir / "project").glob("references.json.tmp")))

        # ── {{source: …}} in the grammar ──
        src = ("## §9 Sources\n\nA page: {{source: francois2026b, p. 128}}. A bare number: {{source: francois2026b, 128}}. A range: {{source: francois2026b, 73-128}}. Narrative: {{source: francois2026b, narrative}}.\n\n"
               "Unknown: {{source: nobody2000}}. Mixed case: {{source: Francois2026B}}.\n\n| a | b |\n|---|---|\n| {{source: francois2026b}} | x |\n")
        st, j = _jcall(aa, "post", site.url + "api/grammar/zz_sources", {"source": src})
        h = j.get("html", "")
        links = [html_lib.unescape(x) for x in re.findall(r'<a class="source-cite"[^>]*>(.*?)</a>', h)]
        check(S, "{{source: key}} gives (Author, Year); a page, a bare number and a range give p. 128, p. 128 and pp. 73–128; narrative gives Author (Year)",
              links[:4] == ["François, 2026b, p. 128", "François, 2026b, p. 128", "François, 2026b, pp. 73–128", "François (2026b)"], str(links))
        check(S, "the citation links to the reference and carries the whole APA entry for the hover", 'href="references.html#francois2026b"' in h and "Language Science Press" in h and "&lt;em&gt;Negation in the world" in h)
        check(S, "an unknown key shows an error in place of the citation, and no shortcode is left in the text", "Reference not found: nobody2000" in h and "{{source" not in h)
        check(S, "keys are not case-sensitive, and a citation works inside a table", links.count("François, 2026b") == 2 and "<td><span" not in h and "<td>(<a" in h, str(links))
        st, j = _jcall(aa, "post", site.url + "api/references", dict(type="book", authors=[_P("Smith", "A."), _P("Jones", "B.")], year="2016", title="Two authors", publisher="P", id="smithjones2016"))
        _jcall(aa, "post", site.url + "api/references", dict(type="book", authors=[_P("Black", "A.")], year="2017", title="Black", publisher="P", id="black2017"))
        _jcall(aa, "post", site.url + "api/references", dict(type="book", authors=[_P("Lupin", "R."), _P("Potter", "H."), _P("Weasley", "R.")], year="2018", title="Three", publisher="P", id="lupin2018"))
        st, j = _jcall(aa, "post", site.url + "api/grammar/zz_sources", {"source": "## §9 Sources\n\n{{source: smithjones2016}} {{source: smithjones2016, narrative}} {{source: lupin2018}} {{source: lupin2018, narrative}} {{source: lupin2018; black2017; francois2026b, p. 3}}\n"})
        links = [html_lib.unescape(x) for x in re.findall(r'<a class="source-cite"[^>]*>(.*?)</a>', j.get("html", ""))]
        check(S, "two authors: & in brackets and “and” in the sentence; three or more: et al.; several works: alphabetical, separated by semicolons",
              links == ["Smith & Jones, 2016", "Smith and Jones (2016)", "Lupin et al., 2018", "Lupin et al. (2018)", "Black, 2017", "François, 2026b, p. 3", "Lupin et al., 2018"], str(links))

        # ── hostile input ──
        evil = dict(type="article", authors=[{"family": "<b>Evil</b>", "given": "<i>x</i>"}], year="2020", title="<img src=x onerror=alert(1)> & \"quotes\" <script>alert(2)</script>", container="J<script>", id="evil2020")
        st, j = _jcall(aa, "post", site.url + "api/references", evil)
        lst = _jcall(aa, "get", site.url + "api/references")[1]["references"]
        e = [r for r in lst if r["id"] == "evil2020"][0]
        st, g = _jcall(aa, "post", site.url + "api/grammar/zz_sources", {"source": "## §9\n\n{{source: evil2020}}"})
        check(S, "HTML typed into a reference is escaped in the list, in the hover text and in the preview", "<img" not in e["html"] and "<script" not in e["html"] and "&lt;img" in e["html"] and "<img" not in g["html"] and "<script" not in g["html"], e["html"][:100])
        pge = au.new_page(); ee = []; watch(pge, ee)
        pge.on("dialog", lambda d: ee.append("DIALOG " + d.message))
        open_page(pge, site, "references.html", ".ref-entry", 800)
        check(S, "…and nothing runs when the page shows it", not pge.locator(".ref-text img, .ref-text script").count() and not [x for x in ee if "DIALOG" in x or "PAGEERROR" in x], str(ee[:2]))
        _jcall(aa, "delete", site.url + "api/references/evil2020")

        # ── LaTeX ──
        (gdir / "zz_rename.md").unlink()
        st, j = _jcall(aa, "post", site.url + "api/references", dict(type="book", authors=[_P("Fish & Chips", "A.")], year="2001", title="100% of C_x # costs", publisher="R&D Press", id="fish2001"))
        _jcall(aa, "post", site.url + "api/grammar/zz_sources", {"source": "## §9 Sources\n\nOne {{source: francois2026b, p. 128}} and {{source: fish2001}} and {{source: smithjones2016, narrative}}.\n"})
        tex = aa.get(site.url + "api/grammar/export/latex").text()
        check(S, "LaTeX: the citations are written as text, escaped", "One (François, 2026b, p. 128) and (Fish \\& Chips, 2001) and Smith and Jones (2016)." in tex, tex[tex.find("One"):tex.find("One") + 120] if "One" in tex else "")
        refs_part = tex[tex.find("\\section*{References}"):]
        check(S, "LaTeX: a References section lists the cited works only, in APA style, titles in italics, hanging indent",
              "\\section*{References}" in tex and "\\hangindent=1.27cm" in refs_part and "\\emph{Negation in the world’s languages III: Papunesia, Australia, and the Americas}" in refs_part
              and "\\url{https://doi.org/10.5281/zenodo.18234067}" in refs_part and "Smith, A., \\& Jones, B. (2016)" in refs_part and "Black" not in refs_part and "Lupin" not in refs_part, refs_part[:200])
        check(S, "LaTeX: special characters in a reference are escaped (& % _ #)", "Fish \\& Chips, A. (2001). \\emph{100\\% of C\\_x \\# costs}. R\\&D Press." in refs_part, refs_part[refs_part.find("Fish"):refs_part.find("Fish") + 120])
        for fn in ("zz_sources.md",): (gdir / fn).unlink(missing_ok=True)
        tex2 = aa.get(site.url + "api/grammar/export/latex").text()
        check(S, "LaTeX: with no citation in the grammar there is no References section", "\\section*{References}" not in tex2)

        # ── exports ──
        _jcall(aa, "post", site.url + "api/references", dict(type="dataset", authors=[{"org": "Pew Research Center"}], year="2018", title="American trends panel Wave 26", url="https://example.org/pew", id="pew2018"))
        bib = va.get(site.url + "api/references/export/bibtex"); enw = va.get(site.url + "api/references/export/endnote")
        check(S, "a visitor can download both exports, with a file name made from the project", bib.status == 200 and enw.status == 200 and 'filename="gaua-references.bib"' in bib.headers.get("content-disposition", "") and 'filename="gaua-references.enw"' in enw.headers.get("content-disposition", ""), bib.headers.get("content-disposition", ""))
        try:
            import bibtexparser
            lib = bibtexparser.parse_string(bib.text())
            ent = {e.key: {k: v.value for k, v in e.fields_dict.items()} | {"_type": e.entry_type} for e in lib.entries}
            check(S, "BibTeX: a real BibTeX parser reads the whole file without a failure", not lib.failed_blocks and len(lib.entries) == len(_jcall(aa, "get", site.url + "api/references")[1]["references"]), str(lib.failed_blocks)[:100])
            f = ent["francois2026b"]
            check(S, "BibTeX: the chapter is an @incollection with author, editors, book title, pages (--), the year without its letter, publisher and DOI",
                  f["_type"] == "incollection" and f["author"] == "François, Alexandre" and f["editor"] == "Miestamo, M. and Veselinova, L." and f["booktitle"].startswith("Negation in the world") and f["pages"] == "73--128"
                  and f["year"] == "2026" and f["publisher"] == "Language Science Press" and f["doi"] == "10.5281/zenodo.18234067" and f["title"] == "{Negation in Dorig}", str(f)[:200])
            check(S, "BibTeX: special characters are escaped, an organisation is kept whole in braces", ent["fish2001"]["title"] == "{100\\% of C\\_x \\# costs}" and ent["fish2001"]["author"] == "Fish \\& Chips, A." and ent["pew2018"]["author"] == "{Pew Research Center}" and ent["pew2018"]["_type"] == "misc", str(ent["pew2018"]))
        except ImportError:
            check(S, "BibTeX: a real parser (pip install bibtexparser) reads the file", True, "skipped: bibtexparser is not installed")
        records = [r for r in enw.text().strip().split("\n\n") if r.strip()]
        fr = [r for r in records if "%F francois2026b" in r][0].split("\n")
        check(S, "EndNote: one record per reference, separated by blank lines, each starting with its type", len(records) == len(_jcall(aa, "get", site.url + "api/references")[1]["references"]) and all(r.startswith("%0 ") for r in records))
        check(S, "EndNote: the chapter is a Book Section with author, one line per editor, title, book title, year, pages, publisher and DOI",
              fr[0] == "%0 Book Section" and "%A François, Alexandre" in fr and "%E Miestamo, M." in fr and "%E Veselinova, L." in fr and "%T Negation in Dorig" in fr and "%D 2026" in fr and "%P 73–128" in fr and "%I Language Science Press" in fr and "%R 10.5281/zenodo.18234067" in fr, str(fr))
        pew = [r for r in records if "%F pew2018" in r][0].split("\n")
        check(S, "EndNote: an organisation keeps its name whole (a trailing comma stops EndNote splitting it), a data set is a Dataset", "%0 Dataset" in pew and "%A Pew Research Center," in pew, str(pew))
        for rid in ("smithjones2016", "black2017", "lupin2018", "fish2001", "pew2018"): _jcall(aa, "delete", site.url + "api/references/" + rid)

        # ── the author's form, in a browser ──
        pa = au.new_page(); errs = []; watch(pa, errs)
        open_page(pa, site, "references.html", ".ref-entry", 800)
        check(S, "the author sees Add, Edit, Delete, the key of each reference and a hint about the shortcode", pa.locator("#ref-add").is_visible() and pa.locator("[data-edit]").first.is_visible() and pa.locator(".ref-key").first.inner_text() == "francois2026b" and "{{source: key}}" in pa.locator(".refs-hint").inner_text())
        pa.click("#ref-add"); pa.wait_for_selector("#ref-modal.visible")
        check(S, "the form opens on a journal article, with the fields of an article only", pa.locator("#rf-container").is_visible() and pa.locator("#rf-issue").is_visible() and not pa.locator("#rf-editors-box").is_visible() and not pa.locator("#rf-level").is_visible())
        def fill_person(row, fam, giv):
            pa.locator(f"#rf-authors .rf-person:nth-child({row}) [data-f=family]").fill(fam); pa.locator(f"#rf-authors .rf-person:nth-child({row}) [data-f=given]").fill(giv)
        fill_person(1, "Roe", "Jane Q."); pa.click("#rf-add-author"); fill_person(2, "Doe", "Richard")
        pa.fill("#rf-year", "2014"); pa.fill("#rf-title-in", "A study of tests"); pa.fill("#rf-container", "Journal of Tests"); pa.fill("#rf-volume", "3"); pa.fill("#rf-issue", "2"); pa.fill("#rf-pages", "1-9"); pa.fill("#rf-doi", "10.1000/xyz123")
        pa.wait_for_function("document.getElementById('rf-prev-ref').textContent.includes('Journal of Tests')"); pa.wait_for_timeout(300)
        check(S, "while the author types, the form shows the reference as it will appear, and how to cite it", pa.inner_text("#rf-prev-ref") == "Roe, J. Q., & Doe, R. (2014). A study of tests. Journal of Tests, 3(2), 1–9. https://doi.org/10.1000/xyz123" and pa.inner_text("#rf-prev-text").replace("\u00a0", " ").split("·")[0].strip() == "(Roe & Doe, 2014)", pa.inner_text("#rf-prev-text"))
        check(S, "the key is suggested from the first author and the year", pa.input_value("#rf-id") == "roe2014", pa.input_value("#rf-id"))
        pa.locator('#rf-authors .rf-person:nth-child(2) [data-mv="-1"]').click(); pa.wait_for_function("document.getElementById('rf-prev-ref').textContent.startsWith('Doe, R., & Roe')")
        check(S, "the authors can be moved up and down, and the preview follows", pa.input_value("#rf-id") == "doe2014")
        pa.locator('#rf-authors .rf-person:nth-child(2) [data-mv="-1"]').click(); pa.wait_for_function("document.getElementById('rf-prev-ref').textContent.startsWith('Roe, J. Q., & Doe')")
        pa.locator('#rf-authors .rf-person:nth-child(2) [data-f=org]').check(); pa.fill('#rf-authors .rf-person:nth-child(2) [data-f=family]', "Doe Institute")
        pa.wait_for_function("document.getElementById('rf-prev-ref').textContent.includes('Doe Institute')")
        check(S, "an organisation is one name, with no given names", pa.locator('#rf-authors .rf-person:nth-child(2) [data-f=given]').is_disabled() and pa.inner_text("#rf-prev-ref").startswith("Roe, J. Q., & Doe Institute. (2014)"), pa.inner_text("#rf-prev-ref")[:60])
        pa.locator('#rf-authors .rf-person:nth-child(2) [data-rm]').click()
        pa.select_option("#rf-type", "chapter"); pa.wait_for_timeout(200)
        check(S, "choosing another type changes the fields: a chapter asks for the editors and the title of the book", pa.locator("#rf-editors-box").is_visible() and pa.locator('label[data-f="container"] .lbl').inner_text() == "Title of the book" and not pa.locator("#rf-issue").is_visible())
        pa.select_option("#rf-type", "web"); pa.wait_for_timeout(200)
        check(S, "…and a web page asks for the website and the date", pa.locator('label[data-f="container"] .lbl').inner_text() == "Name of the website" and pa.locator("#rf-dateText").is_visible() and pa.locator("#rf-accessed").is_visible())
        pa.select_option("#rf-type", "article")
        pa.fill("#rf-title-in", ""); pa.click("#rf-save"); pa.wait_for_timeout(700)
        check(S, "saving without a title shows the reason in the form and keeps it open", "title" in pa.inner_text("#rf-msg") and pa.locator("#ref-modal.visible").count() == 1, pa.inner_text("#rf-msg"))
        pa.fill("#rf-title-in", "A study of tests"); pa.wait_for_timeout(500); pa.click("#rf-save")
        pa.wait_for_selector("#roe2014", timeout=8000)
        check(S, "saving adds the reference to the list, in its alphabetical place", pa.locator(".ref-entry").evaluate_all("els => els.map(e => e.id)") == ["francois2026b", "roe2014"], str(pa.locator(".ref-entry").evaluate_all("els => els.map(e => e.id)")))
        check(S, "…with its text in APA style", pa.locator("#roe2014 .ref-text").inner_text().strip() == "Roe, J. Q. (2014). A study of tests. Journal of Tests, 3(2), 1–9. https://doi.org/10.1000/xyz123")
        pa.click('[data-key="roe2014"]'); pa.wait_for_timeout(200)
        check(S, "clicking a key copies its shortcode", "copied: {{source: roe2014}}" in pa.locator('[data-key="roe2014"]').inner_text())
        pa.click('[data-edit="roe2014"]'); pa.wait_for_selector("#ref-modal.visible")
        check(S, "Edit opens the form filled in, with its key", pa.input_value("#rf-title-in") == "A study of tests" and pa.input_value("#rf-container") == "Journal of Tests" and pa.input_value("#rf-pages") == "1-9" and pa.input_value("#rf-id") == "roe2014" and pa.locator("#rf-heading").inner_text() == "Edit the reference")
        pa.fill("#rf-title-in", "A second study of tests"); pa.click("#rf-save"); pa.wait_for_function("document.querySelector('#roe2014 .ref-text').textContent.includes('A second study')", timeout=8000)
        check(S, "an edited reference is updated in the list", "A second study of tests" in pa.locator("#roe2014 .ref-text").inner_text())
        pa.fill("#refs-search", "dorig"); pa.wait_for_timeout(200)
        shown = pa.locator(".ref-entry").count(); pa.fill("#refs-search", "zzzzz"); pa.wait_for_timeout(200)
        check(S, "the search box narrows the list, and says when nothing matches", shown == 1 and "Nothing matches" in pa.locator("#refs-list").inner_text() and "shown" in pa.locator("#refs-count").inner_text())
        pa.fill("#refs-search", ""); pa.wait_for_timeout(200)
        pa.click('[data-del="roe2014"]'); pa.wait_for_function("!document.getElementById('roe2014')", timeout=8000)
        check(S, "Delete removes it (after a confirmation)", pa.locator(".ref-entry").count() == 1)
        open_page(pa, site, "references.html#francois2026b", ".ref-entry", 700)
        check(S, "a link to references.html#key highlights that reference", pa.evaluate("getComputedStyle(document.getElementById('francois2026b')).backgroundColor") == "rgb(251, 241, 214)")
        real = [e for e in errs if not ("HTTP 400" in e and e.endswith("/api/references"))]          # the refusal of an empty title is expected
        check(S, "the form and the list raised no JavaScript or loading error", not real, "; ".join(real[:2]))

        # ── the citation in the grammar page, with its hover ──
        (gdir / "zz_page.md").write_text("## §9 Sources\n\nThe negator is described by {{source: francois2026b, p. 128}}.\n", encoding="utf-8")
        pg = au.new_page(); errs = []; watch(pg, errs)
        open_page(pg, site, "grammar.html", "#sections-container .source-cite", 1500)
        cite = pg.locator(".source-cite").first
        cite.scroll_into_view_if_needed(); cite.hover(); pg.wait_for_timeout(300)
        tip = pg.evaluate("""() => { const d = [...document.querySelectorAll('body > div')].filter(e => getComputedStyle(e).position === 'fixed' && getComputedStyle(e).display !== 'none' && e.textContent.includes('Language Science Press')).pop(); return d ? {text: d.innerText, html: d.innerHTML} : null; }""") or {"text": "", "html": ""}
        check(S, "in the grammar the citation reads (François, 2026b, p. 128) and, on hover, shows the whole reference with its italics", cite.inner_text() == "François, 2026b, p. 128" and "Negation in Dorig" in tip["text"] and "Language Science Press" in tip["text"] and "<em>" in tip["html"], tip["text"][:60])
        pg.evaluate("window.scrollTo(0, 0)")
        pg.evaluate("document.querySelector('.edit-tab.section-edit').click()"); pg.wait_for_selector(".editor-toolbar-btn", timeout=8000)
        pg.evaluate("[...document.querySelectorAll('.editor-toolbar-btn')].find(b => b.textContent.includes('{{source}}')).click()")
        check(S, "the grammar editor has a {{source}} button that inserts a citation, and lists it among the shortcodes", "{{source: key, p. 12}}" in pg.locator("textarea").first.input_value() and "cite a reference" in pg.locator(".shortcode-ref").first.inner_text().lower(), pg.locator("textarea").first.input_value()[-40:])
        cite.click(); pg.wait_for_url("**/references.html#francois2026b", timeout=8000)
        check(S, "…and clicking it goes to that reference", pg.url.endswith("references.html#francois2026b"))
        check(S, "the grammar page raised no JavaScript or loading error", not errs, "; ".join(errs[:2]))
        (gdir / "zz_page.md").unlink()

        # ── narrow screens ──
        for w in (600, 390, 320):
            c = new_context(browser, site, w, author=True); p = c.new_page()
            wide = []
            for fn in pages:
                open_page(p, site, fn, None, 500)
                nav = p.evaluate("(() => { const n = document.querySelector('.topnav'); return n ? n.scrollWidth - n.clientWidth : 0; })()")
                if nav > 0: wide.append(f"{fn} nav +{nav}px")
            open_page(p, site, "references.html", ".ref-entry", 500)
            page_w = p.evaluate("document.documentElement.scrollWidth")
            p.click("#ref-add"); p.wait_for_selector("#ref-modal.visible"); box = p.locator("#ref-modal .ref-form").bounding_box()
            check(S, f"at {w}px the top bar of every page fits, the References page does not scroll sideways and its form stays inside the screen", not wide and page_w <= w and box["x"] >= 0 and box["x"] + box["width"] <= w + 1, f"{wide} page {page_w}px form {box}")
            c.close()
        pg.context.close(); pa.context.close(); vis.close(); au.close()
    finally:
        site.stop()

    # ── a project with no references yet ──
    site = Site(prepare=lambda d: (d / "project" / "references.json").unlink())
    try:
        c = new_context(browser, site, 1280); p = c.new_page(); errs = []; watch(p, errs)
        open_page(p, site, "references.html", "#refs-list", 700)
        d = c.request.get(site.url + "api/references").json()
        check(S, "with no references.json the page says there are none, the API returns an empty list and the exports are empty", "No references yet" in p.locator("#refs-list").inner_text() and d["references"] == [] and c.request.get(site.url + "api/references/export/bibtex").text() == "" and not errs, "; ".join(errs[:2]))
        a = new_context(browser, site, 1280, author=True)
        st, j = _jcall(a.request, "post", site.url + "api/references", dict(type="book", authors=[_P("First", "A.")], year="2020", title="The first one", publisher="P"))
        check(S, "the author can add the first reference to a project that had none (the file is created)", st == 200 and (site.dir / "project" / "references.json").exists() and j.get("id") == "first2020", str(j))
        c.close(); a.close()
    finally:
        site.stop()


# ───────────────────────── 10. dictionary suite: entries in the headword language, etymology and senses per language ─────────────────────────
ALLC = ["num", "drg", "kro", "olr", "lkn"]

def _entry_xml(site, eid):
    root = etree.parse(str(site.dir / "project" / "dictionary.xml")).getroot()
    found = [e for e in root.iter("EntréeLexicale") if e.get("identifiant") == eid]
    return found[0] if found else None

def _dict_with_languages(d):
    """speech: its etymology applies to Dorig and Lakon only; sense 1 is for Dorig, Olrat and Lakon, sense 2 for Nume and Koro.
    multi: three senses, for Dorig / Dorig and Koro / Koro. art already has no Olrat and no Lakon form."""
    p = d / "project" / "dictionary.xml"
    tree = etree.parse(str(p)); root = tree.getroot()
    sp = [e for e in root.iter("EntréeLexicale") if e.get("identifiant") == "speech"][0]
    sp.find("Étymologie/Étymon").set("langues", "drg lkn")
    sp.find("Sens").set("langues", "drg olr lkn")
    sp.append(etree.fromstring('<Sens identifiant="speechⓢ2" langues="num kro"><NuméroDeSens>2</NuméroDeSens><Glose langue="eng">noise, sound</Glose>'
                               '<Définition><ReprésentationDeTexte langue="eng">noise, sound</ReprésentationDeTexte></Définition><gloss>noise</gloss></Sens>'))
    root.find(".//Dictionnaire").append(etree.fromstring(
        '<EntréeLexicale identifiant="multi"><Lemme><ReprésentationDeForme langue="drg">mltdrg</ReprésentationDeForme><ReprésentationDeForme langue="kro">mltkro</ReprésentationDeForme></Lemme>'
        '<ClasseGrammaticale>n.</ClasseGrammaticale>'
        '<Sens identifiant="multiⓢ1" langues="drg"><NuméroDeSens>1</NuméroDeSens><Glose langue="eng">alpha</Glose><gloss>alpha</gloss></Sens>'
        '<Sens identifiant="multiⓢ2" langues="drg kro"><NuméroDeSens>2</NuméroDeSens><Glose langue="eng">beta</Glose><gloss>beta</gloss></Sens>'
        '<Sens identifiant="multiⓢ3" langues="kro"><NuméroDeSens>3</NuméroDeSens><Glose langue="eng">gamma</Glose><gloss>gamma</gloss></Sens></EntréeLexicale>'))
    tree.write(str(p), encoding="UTF-8", xml_declaration=True, pretty_print=True)

def _dict_hostile(d):
    p = d / "project" / "dictionary.xml"
    tree = etree.parse(str(p)); root = tree.getroot()
    et = [e for e in root.iter("EntréeLexicale") if e.get("identifiant") == "speech"][0].find("Étymologie/Étymon")
    et.find("Forme").text = "<img src=x onerror=alert(1)>"
    et.find("LienTLOPO").text = "javascript:alert(2)"
    et.find("LienEtymograph").text = "https://example.org/ok"
    tree.write(str(p), encoding="UTF-8", xml_declaration=True, pretty_print=True)

_VIEW_JS = """(id) => { const e = document.getElementById(id); if (!e) return null;
  const t = s => [...e.querySelectorAll(s)].map(x => x.innerText.trim());
  const abbr = s => [...e.querySelectorAll(s + ' .étiquette_lang')].map(x => x.innerText.trim().toLowerCase());
  return { etym: t('.etym-form'), pre: t('.etym-pre'), cogLabel: e.querySelectorAll('.cog-label').length, cognates: abbr('.entry-cognates'),
           others: abbr('.entry-equivs:not(.entry-cognates)'), senses: t('.entry-gloss'), numbers: t('.sense-n'), nosense: e.querySelectorAll('.no-sense').length,
           links: [...e.querySelectorAll('.etym-badge a')].map(a => a.getAttribute('href')), imgs: e.querySelectorAll('.etym-badge img').length }; }"""

def suite_dictionary(browser, args):
    S = "dictionary"
    section("dictionary: entries in the headword language, the etymology of a form, the senses of a language")
    proj = json.loads((ROOT / "project" / "project.json").read_text(encoding="utf-8"))
    NAME = {l["code"]: l["name"] for l in proj["languages"]}
    ABBR = {l["code"]: l["abbr"].lower() for l in proj["languages"]}
    ET = "*[qa]liŋa- 'voice'"

    def view(page, site, lang_code, eid):
        open_page(page, site, f"dictionary.html?lang={NAME[lang_code]}", "#dict-content .entry", 500)
        return page.evaluate(_VIEW_JS, eid)

    # ── old data: no language list anywhere, nothing changes ──
    site = Site()
    try:
        vis = new_context(browser, site, 1280); page = vis.new_page(); errs = []; watch(page, errs)
        same = []
        for c in ALLC:
            v = view(page, site, c, "speech")
            if not (v and v["etym"] == [ET] and v["cogLabel"] == 0 and len(v["others"]) == 4): same.append(c)
        check(S, "an etymology without a language list applies to every language and looks as before (no cognates row)", not same, str(same))
        check(S, "…and so does a sense without a language list: every language shows it", all((view(page, site, c, "speech") or {}).get("senses", [""])[0].startswith("speech") for c in ALLC))
        check(S, "no JavaScript or loading error on old data", not errs, "; ".join(errs[:2]))
        vis.close()
    finally:
        site.stop()

    # ── the display, language by language ──
    site = Site(prepare=_dict_with_languages)
    try:
        vis = new_context(browser, site, 1280); page = vis.new_page(); errs = []; watch(page, errs)
        v = view(page, site, "drg", "speech")
        check(S, "Dorig: the etymology of the Dorig form, followed by its cognates (Lakon only), then the other forms", v["etym"] == [ET] and [x.lower() for x in v["pre"]] == ["poc"] and v["cogLabel"] == 1 and v["cognates"] == [ABBR["lkn"]] and sorted(v["others"]) == sorted(ABBR[c] for c in ("num", "kro", "olr")), str(v))
        check(S, "Dorig: only the senses ticked for Dorig (sense 1), not numbered when there is one", v["senses"] == ["speech, language, word"] and v["numbers"] == [], str(v["senses"]))
        v = view(page, site, "lkn", "speech")
        check(S, "Lakon: the same etymology, with Dorig as its cognate", v["etym"] == [ET] and v["cognates"] == [ABBR["drg"]] and v["senses"] == ["speech, language, word"], str(v))
        v = view(page, site, "num", "speech")
        check(S, "Nume: no etymology (it applies to Dorig and Lakon only), no cognates, every other form listed", v["etym"] == [] and v["cogLabel"] == 0 and len(v["others"]) == 4, str(v))
        check(S, "Nume: only sense 2 (“noise, sound”), the one ticked for Nume and Koro", v["senses"] == ["noise, sound"], str(v["senses"]))
        v = view(page, site, "kro", "speech"); k = v["senses"]
        v2 = view(page, site, "olr", "speech")
        check(S, "Koro shows sense 2 and Olrat sense 1, each without the other's", k == ["noise, sound"] and v2["senses"] == ["speech, language, word"] and v2["etym"] == [], f"{k} / {v2['senses']}")
        d = view(page, site, "drg", "multi"); k = view(page, site, "kro", "multi")
        check(S, "senses are numbered 1, 2 … among those shown (Koro: stored senses 2 and 3 show as 1 and 2)", d["senses"] == ["alpha", "beta"] and d["numbers"] == ["1", "2"] and k["senses"] == ["beta", "gamma"] and k["numbers"] == ["1", "2"], f"{d} {k}")
        # entries per language
        counts = {}
        for c in ALLC:
            open_page(page, site, f"dictionary.html?lang={NAME[c]}", "#dict-content .entry", 400)
            counts[c] = (page.locator("#dict-content .entry").count(), page.locator("#art").count(), page.locator("#result-bar").inner_text().split()[0])
        check(S, "a language lists the entries that have a form in it: art (no Olrat, no Lakon form) is not listed under Olrat or Lakon", counts["olr"][1] == 0 and counts["lkn"][1] == 0 and all(counts[c][1] == 1 for c in ("num", "drg", "kro")), str(counts))
        check(S, "…and the entry count follows (multi has forms in Dorig and Koro only)", [counts[c][0] for c in ALLC] == [8, 9, 9, 7, 7] and [counts[c][2] for c in ALLC] == ["8", "9", "9", "7", "7"], str(counts))
        # search follows the senses of the language
        open_page(page, site, "dictionary.html?lang=Dorig", "#dict-content .entry", 400); page.fill("#search-input", "noise"); page.wait_for_timeout(500)
        in_dorig = page.locator("#dict-content .entry").count()
        open_page(page, site, "dictionary.html?lang=Nume", "#dict-content .entry", 400); page.fill("#search-input", "noise"); page.wait_for_timeout(500)
        in_nume = page.locator("#dict-content .entry").count()
        check(S, "a word found only in a sense that is not shown for the language does not find the entry there (Dorig: 0, Nume: 1)", (in_dorig, in_nume) == (0, 1), f"{in_dorig}, {in_nume}")
        # a badge for a language without a form does not leave the entry
        open_page(page, site, "dictionary.html?lang=Nume", "#art", 400)
        page.locator(f"#art .étiquette_lang[data-lang='{NAME['olr']}'] a").click(); page.wait_for_timeout(600)
        check(S, "clicking the badge of a language in which the entry has no form changes nothing", page.locator("#art").count() == 1 and NAME["num"] in page.locator("#result-bar").inner_text())
        page.locator(f"#speech .étiquette_lang[data-lang='{NAME['drg']}'] a").click(); page.wait_for_timeout(600)
        check(S, "…while the badge of a language that has the form switches to it, with its etymology", NAME["drg"] in page.locator("#result-bar").inner_text() and page.locator("#speech .etym-form").count() == 1)
        check(S, "no JavaScript or loading error", not errs, "; ".join(errs[:2]))
        vis.close()

        # ── the entries API names the language of a restricted sense only ──
        api = new_context(browser, site, 1280, author=False).request
        ents = {e["id"]: e for e in api.get(site.url + "api/dictionary/entries").json()["entries"]}
        check(S, "the entries API gives the languages of a restricted sense, and nothing for a free one", ents["speech"]["senses"][1].get("langs") == ["num", "kro"] and "langs" not in ents["know"]["senses"][0], str(ents["speech"]["senses"]))

        # ── the server, through the API ──
        au = new_context(browser, site, 1280, author=True); aa = au.request
        def send(method, path, body): r = getattr(aa, method)(site.url + path, headers=_H, data=json.dumps(body)); return r.status, (r.json() if r.headers.get("content-type", "").startswith("application/json") else {})
        base = dict(forms={"drg": "zzdrg", "lkn": "zzlkn", "num": "zznum"}, pos="n.", domain="")
        st, j = send("post", "api/dictionary/entry", dict(base, senses=[{"ref": None, "definition": "one", "shortGloss": "one", "langs": ["drg", "lkn", "xx"]}, {"ref": None, "definition": "two", "shortGloss": "two", "langs": ALLC}, {"ref": None, "definition": "three", "shortGloss": "three", "langs": ["xx"]}],
                  etyms=[{"ref": None, "lang": "POc", "form": "*aaa", "gloss": "x", "langs": ["drg", "lkn"]}, {"ref": None, "lang": "PNCV", "form": "*bbb", "gloss": "y", "langs": ["num", "drg"]}]))
        eid = j.get("id"); el = _entry_xml(site, eid)
        sens = [s.get("langues") for s in el.findall("Sens")]; ets = [(e.findtext("Forme"), e.get("langues")) for e in el.findall("Étymologie/Étymon")]
        check(S, "the server writes the languages of a sense (unknown codes dropped; all of them, or none valid, means no attribute)", st == 200 and sens == ["drg lkn", None, None], f"{st} {sens}")
        check(S, "…and of an etymon, keeping an explicit list; a language belongs to one etymon only (the first keeps Dorig)", ets == [("*aaa", "drg lkn"), ("*bbb", "num")], str(ets))
        before = etree.tostring(el)
        payload = dict(base, senses=[{"ref": i, "definition": d, "shortGloss": d, "langs": l} for i, (d, l) in enumerate([("one", ["drg", "lkn"]), ("two", ALLC), ("three", ALLC)])])
        send("put", f"api/dictionary/entry/{eid}", payload)
        check(S, "saving the same languages again leaves the entry byte for byte as it was (no etymons sent = left alone)", etree.tostring(_entry_xml(site, eid)) == before)
        send("put", f"api/dictionary/entry/{eid}", dict(payload, etyms=[{"ref": 1, "lang": "PNCV", "form": "*bbb", "gloss": "y2", "langs": ["num", "kro"]}]))
        ets = [(e.findtext("Forme"), e.findtext("Glose"), e.get("langues")) for e in _entry_xml(site, eid).findall("Étymologie/Étymon")]
        check(S, "an etymon is edited in place by its position, the others of the list are removed", ets == [("*bbb", "y2", "num kro")], str(ets))
        send("put", f"api/dictionary/entry/{eid}", dict(payload, etym={"lang": "POc", "form": "*ccc", "gloss": "z"}))
        e1 = _entry_xml(site, eid).find("Étymologie/Étymon")
        check(S, "an older caller that sends one etymology rewrites the first etymon and keeps its languages", e1.findtext("Forme") == "*ccc" and e1.get("langues") == "num kro" and len(_entry_xml(site, eid).findall("Étymologie/Étymon")) == 1)
        send("put", f"api/dictionary/entry/{eid}", dict(payload, etyms=[]))
        check(S, "an empty list removes the etymology", _entry_xml(site, eid).find("Étymologie") is None)
        send("delete", f"api/dictionary/entry/{eid}", {})
        au.close()
    finally:
        site.stop()

    # ── the author's window ──
    site = Site()
    try:
        au = new_context(browser, site, 1280, author=True); page = au.new_page(); errs = []; watch(page, errs)
        open_page(page, site, "dictionary.html?lang=Dorig", "#dict-content .entry", 600)
        page.evaluate("openEditEntry('speech')"); page.wait_for_selector("#entry-modal.visible")
        ticks = lambda sel: page.evaluate("(sel) => [...document.querySelectorAll(sel + ' input[type=checkbox]')].filter(c => c.checked).map(c => c.dataset.lang)", sel)
        check(S, "the window offers, for each sense, a tick per language of the project (all ticked for an old sense)", len(page.locator(".em-sense:not(.em-etym) .em-lang-tick").all()) == 5 and ticks(".em-sense:not(.em-etym)") == list(NAME.values()))
        check(S, "…and for the etymology (an old one shows every language ticked)", ticks(".em-etym") == list(NAME.values()) and page.locator("#em-etym-box").evaluate("e => e.open"))
        page.fill('.em-etym [data-f="tlopo"]', "https://tlopo.example/changed"); page.click("#em-submit"); page.wait_for_function("!document.getElementById('entry-modal').classList.contains('visible')", timeout=8000)
        et = _entry_xml(site, "speech").find("Étymologie/Étymon")
        check(S, "changing only a link of an old etymology does not give it a language list", et.get("langues") is None and et.findtext("LienTLOPO") == "https://tlopo.example/changed")
        page.evaluate("openEditEntry('speech')"); page.wait_for_selector("#entry-modal.visible")
        for l in ("Nume", "Koro", "Olrat"): page.locator(f'.em-etym input[data-lang="{l}"]').uncheck()
        page.click("#em-submit"); page.wait_for_function("!document.getElementById('entry-modal').classList.contains('visible')", timeout=8000)
        check(S, "unticking languages on the etymology writes the list of the forms it applies to", _entry_xml(site, "speech").find("Étymologie/Étymon").get("langues") == "drg lkn")
        check(S, "…and the entry now shows it in Dorig, with Lakon as its cognate, and not in Nume", view(page, site, "drg", "speech")["cognates"] == [ABBR["lkn"]] and view(page, site, "num", "speech")["etym"] == [])
        # a second etymology for the other forms
        open_page(page, site, "dictionary.html?lang=Dorig", "#dict-content .entry", 600)
        page.evaluate("openEditEntry('speech')"); page.wait_for_selector("#entry-modal.visible"); page.click("#em-add-etym")
        second = ticks(".em-etym:nth-child(2)")
        check(S, "a new etymology starts with the languages that have a form and belong to no other etymology", second == [NAME["num"], NAME["kro"], NAME["olr"]] and ticks(".em-etym:nth-child(1)") == [NAME["drg"], NAME["lkn"]], str(second))
        page.locator('.em-etym:nth-child(2) input[data-lang="Dorig"]').check()
        check(S, "ticking a language on one etymology takes it from the other", ticks(".em-etym:nth-child(1)") == [NAME["lkn"]] and NAME["drg"] in ticks(".em-etym:nth-child(2)"))
        page.locator('.em-etym:nth-child(2) input[data-lang="Dorig"]').uncheck(); page.locator('.em-etym:nth-child(1) input[data-lang="Dorig"]').check()
        page.fill('.em-etym:nth-child(2) [data-f="form"]', "*bbb"); page.fill('.em-etym:nth-child(2) [data-f="gloss"]', "other"); page.fill('.em-etym:nth-child(2) [data-f="lang"]', "PNCV")
        page.click("#em-submit"); page.wait_for_function("!document.getElementById('entry-modal').classList.contains('visible')", timeout=8000)
        ets = [(e.findtext("Forme"), e.get("langues")) for e in _entry_xml(site, "speech").findall("Étymologie/Étymon")]
        check(S, "two etymologies are saved, each with its own languages", ets == [(ET.split(" ")[0], "drg lkn"), ("*bbb", "num kro olr")], str(ets))
        n = view(page, site, "num", "speech")
        check(S, "Nume shows the second one, with Koro and Olrat as its cognates; Dorig still shows the first", n["etym"] == ["*bbb 'other'"] and [x.lower() for x in n["pre"]] == ["pncv"] and n["cognates"] == [ABBR["kro"], ABBR["olr"]] and view(page, site, "drg", "speech")["etym"] == [ET])
        page.evaluate("openEditEntry('speech')"); page.wait_for_selector("#entry-modal.visible")
        page.locator('.em-etym:nth-child(2) [data-act="del"]').click(); page.click("#em-submit"); page.wait_for_function("!document.getElementById('entry-modal').classList.contains('visible')", timeout=8000)
        check(S, "an etymology can be removed from the window", len(_entry_xml(site, "speech").findall("Étymologie/Étymon")) == 1)
        # senses: a sense with no language is refused
        open_page(page, site, "dictionary.html?lang=Dorig", "#dict-content .entry", 600)
        page.evaluate("openEditEntry('know')"); page.wait_for_selector("#entry-modal.visible"); before = etree.tostring(_entry_xml(site, "know"))
        for l in NAME.values(): page.locator(f'.em-sense:not(.em-etym) input[data-lang="{l}"]').uncheck()
        page.click("#em-submit"); page.wait_for_timeout(500)
        check(S, "a sense with no language ticked is refused, with the reason, and nothing is written", "Tick at least one language for sense 1" in page.inner_text("#em-msg") and etree.tostring(_entry_xml(site, "know")) == before)
        page.locator('.em-sense:not(.em-etym) input[data-lang="Koro"]').check(); page.locator('.em-sense:not(.em-etym) input[data-lang="Olrat"]').check()
        page.click("#em-submit"); page.wait_for_function("!document.getElementById('entry-modal').classList.contains('visible')", timeout=8000)
        check(S, "ticking some languages for a sense saves them (and the entry disappears from the others)", _entry_xml(site, "know").find("Sens").get("langues") == "kro olr" and view(page, site, "kro", "know") is not None)
        open_page(page, site, "dictionary.html?lang=Dorig", "#dict-content .entry", 600)
        v = page.evaluate(_VIEW_JS, "know")
        check(S, "…in Dorig the entry is still listed (it has a Dorig form) but says it has no sense there", v["nosense"] == 1 and v["senses"] == ["No sense for Dorig yet."], str(v["senses"]))
        # a new entry whose only form is in another language: the page follows it
        open_page(page, site, "dictionary.html?lang=Koro", "#dict-content .entry", 600)
        page.click("#add-entry-btn"); page.wait_for_selector("#entry-modal.visible")
        page.fill("#ef-num", "zznume"); page.locator(".em-sense textarea").first.fill("only in Nume"); page.click("#em-submit"); page.wait_for_function("!document.getElementById('entry-modal').classList.contains('visible')", timeout=8000); page.wait_for_timeout(900)
        check(S, "a new entry that has no form in the language being viewed: the page moves to a language where it exists and shows it", NAME["num"] in page.locator("#result-bar").inner_text() and page.locator("#zznume").count() == 1, page.locator("#result-bar").inner_text())
        check(S, "the window and the list raised no JavaScript or loading error", not errs, "; ".join(errs[:2]))
        au.close()
    finally:
        site.stop()

    # ── what the author types is never run ──
    site = Site(prepare=_dict_hostile)
    try:
        c = new_context(browser, site, 1280); page = c.new_page(); errs = []; watch(page, errs)
        page.on("dialog", lambda d: errs.append("DIALOG " + d.message))
        v = view(page, site, "drg", "speech")
        check(S, "an etymology with markup in its form is shown as text; a link that is not http(s) is not made a link, a good one is", v["imgs"] == 1 and page.locator("#speech .etym-badge img[src=x]").count() == 0 and v["links"] == ["https://example.org/ok"] and "<img" in v["etym"][0], str(v["links"]))
        check(S, "nothing ran", not [e for e in errs if "DIALOG" in e or "PAGEERROR" in e], str(errs[:2]))
        c.close()
    finally:
        site.stop()

    # ── a project with one language: nothing to tick ──
    site = Site(setup_mode=True)
    try:
        code = site.setup_code(); ctx = new_context(browser, site, 1280); api = ctx.request
        api.post(site.url + "api/setup", data=json.dumps(dict(name="One DBT", mode="starter", password="a-good-password-1", setupCode=code, languages=[])), headers=_H)
        site.wait_restart()
        a = new_context(browser, site, 1280); _login(a.request, site, "a-good-password-1"); page = a.new_page(); errs = []; watch(page, errs)
        open_page(page, site, "dictionary.html", "#dict-content .entry", 800)
        page.evaluate("openEditEntry('house')"); page.wait_for_selector("#entry-modal.visible"); page.click("#em-etym-box summary"); page.click("#em-add-etym")
        page.fill('.em-etym [data-f="form"]', "*one"); page.fill('.em-etym [data-f="gloss"]', "dwelling")
        check(S, "with one language the window shows no language ticks, for senses or etymologies", page.locator(".em-lang-tick").count() == 0)
        page.click("#em-submit"); page.wait_for_function("!document.getElementById('entry-modal').classList.contains('visible')", timeout=8000); page.wait_for_timeout(500)
        root = etree.parse(str(site.dir / "project" / "dictionary.xml")).getroot()
        et = [e for e in root.iter("EntréeLexicale") if e.get("identifiant") == "house"][0].find("Étymologie/Étymon")
        check(S, "…and an etymology added there carries no language list, and is shown", et is not None and et.get("langues") is None and page.locator("#house .etym-form").inner_text() == "*one 'dwelling'")
        check(S, "no JavaScript or loading error", not [e for e in errs if "/api/setup" not in e], "; ".join(errs[:2]))
        ctx.close(); a.close()
    finally:
        site.stop()

# ───────────────────────── main ─────────────────────────
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--update-baseline", action="store_true", help="record the current behaviour as the baseline")
    ap.add_argument("--record-missing", action="store_true", help="record baselines that do not exist yet; never overwrite one")
    ap.add_argument("--only", choices=("visual", "api", "functional", "generality", "security", "setup", "migration", "references", "dictionary"), help="run a single suite (generality includes the languages checks)")
    ap.add_argument("--tolerance", type=float, default=0.0, help="share of pixels allowed to differ in a screenshot (default 0)")
    args = ap.parse_args()
    from playwright.sync_api import sync_playwright
    if OUTPUT.exists(): shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    site = Site(); t0 = time.time()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=CHROMIUM_ARGS)
            # visual + api first, on pristine data; the functional suite then changes the data
            if args.only in (None, "visual"):     suite_visual(browser, site, args)
            if args.only in (None, "api"):        suite_api(browser, site, args)
            if args.only in (None, "functional"): suite_functional(browser, site, args)
            if args.only in (None, "generality"): suite_generality(browser, site, args); suite_languages(browser, args)
            if args.only in (None, "security"):   suite_security(browser, site, args)
            if args.only in (None, "setup"):      suite_setup(browser, args)
            if args.only in (None, "migration"):  suite_migration(browser, args)
            if args.only in (None, "references"): suite_references(browser, args)
            if args.only in (None, "dictionary"): suite_dictionary(browser, args)
            browser.close()
    finally:
        site.stop()
    failed = [r for r in RESULTS if not r[2]]
    print(f"\n{'=' * 74}\n{len(RESULTS) - len(failed)} of {len(RESULTS)} checks passed in {time.time() - t0:.0f}s"
          + ("  (baseline recorded)" if args.update_baseline else ""))
    for suite, name, _, detail in failed: print(f"  ✗ [{suite}] {name}: {detail}")
    (OUTPUT / "report.json").write_text(json.dumps([{"suite": s, "check": n, "ok": o, "detail": d} for s, n, o, d in RESULTS], indent=1, ensure_ascii=False), encoding="utf-8")
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
