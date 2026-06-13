#!/usr/bin/env python3
"""Regression tests for browsefiles navigation: conf integrity + breadcrumb zoom in/out/sideways.

Run:  python3 test_nav.py        # exits 0 if all pass, 1 otherwise
No curses / tty needed — drives the REAL zoom_in/zoom_out/zoom_side with os.system mocked
so we can assert what each relaunch targets and what BF_STACK breadcrumb it carries.
"""
import os, sys
from pathlib import Path

import browsefiles as bf

CONF = str(Path(os.path.expanduser("~/.config/user/browsefiles/go/browse.conf")).resolve())
SEP  = "\x1f"

# ── conf model (for integrity checks + expected siblings) ───────────────────
def parse_conf():
    secs, cur = {}, None
    for raw in Path(CONF).read_text().splitlines():
        s = raw.strip()
        if s.startswith("[") and s.endswith("]"):
            cur = s[1:-1]; secs[cur] = {"parent": None, "kids": []}
        elif cur and s.startswith("^"):
            secs[cur]["parent"] = s[1:].strip()
        elif cur and " > " in s and not s.startswith("#"):
            k = s.split(" > ", 1)[1].strip()
            if k and k != "**":
                secs[cur]["kids"].append(k)
    return secs

SECS = parse_conf()

# ── process-boot + real-function harness ────────────────────────────────────
_captured = {}
def _fake_system(cmd):
    # cmd is "<script> <target>"; capture target + the BF_STACK we set right before
    _captured["target"] = cmd.split(" ", 1)[1].strip()
    _captured["stack"]  = os.environ.get("BF_STACK", "")
    raise SystemExit            # mimic the exit() that follows os.system in the real code
bf.os.system = _fake_system

def short(s):                   # ".../browse.conf:work" -> "work"
    return s.split(":")[-1] if s else "<none>"

def boot(section, stack):
    """Simulate launching the process on `section` with breadcrumb `stack` (list or None)."""
    if stack is None:
        os.environ.pop("BF_STACK", None)
    else:
        os.environ["BF_STACK"] = SEP.join(stack)
    bf.parse_filelist(f"{CONF}:{section}")
    stk = os.environ.pop("BF_STACK", "")
    bf.NAV_STACK = stk.split(SEP) if stk else []
    bf._zoom_source = os.environ.pop("BF_ZOOM_SOURCE", "")
    if bf.NAV_STACK:
        bf.parent = bf.NAV_STACK[-1]

def _run(fn, *a):
    _captured.clear()
    try: fn(*a)
    except SystemExit: pass
    tgt = short(_captured.get("target"))
    stk = [short(x) for x in _captured.get("stack", "").split(SEP) if x]
    return tgt, stk

def kid_idx(section):
    """Index in current view whose kid zooms into `section` (matches the .../conf:section kid)."""
    return next(i for i, k in enumerate(bf.files_with_kid) if k.endswith(":" + section))

def do_zoom_in(section):  boot_target = _run(bf.zoom_in, kid_idx(section)); return boot_target
def do_zoom_out():        return _run(bf.zoom_out)
def do_zoom_side(right):  return _run(bf.zoom_side, right)

# ── assertion plumbing ──────────────────────────────────────────────────────
_fails = []
def check(desc, got, want):
    ok = got == want
    print(f"  [{'PASS' if ok else 'FAIL'}] {desc}: got {got!r}" + ("" if ok else f"  want {want!r}"))
    if not ok:
        _fails.append(desc)

# ─────────────────────────────────────────────────────────────────────────────
print("== conf integrity ==")
all_secs = set(SECS)
for sec, d in SECS.items():
    if d["parent"] is not None:
        check(f"[{sec}] ^parent '{d['parent']}' exists", d["parent"] in all_secs, True)
    for k in d["kids"]:
        check(f"[{sec}] > '{k}' target exists", k in all_secs, True)

print("\n== top-level ring is exactly work/life ==")
def ring_of(section):
    cp, ps = bf.parent.rsplit(":", 1)
    kids = bf._extract_kids_from_lines(bf._read_conf_section(cp, ps), conf_abs=cp)
    return [short(k) for k in kids]
boot("work", [f"{CONF}:all"]); check("ring under [all]", ring_of("work"), ["work", "life"])

print("\n== work⇄life toggle (both directions flip) ==")
boot("work", [f"{CONF}:all"]); check("work →]→", do_zoom_side(True)[0],  "life")
boot("work", [f"{CONF}:all"]); check("work →[→", do_zoom_side(False)[0], "life")
boot("life", [f"{CONF}:all"]); check("life →]→", do_zoom_side(True)[0],  "work")
boot("life", [f"{CONF}:all"]); check("life →[→", do_zoom_side(False)[0], "work")

print("\n== zoom-in pushes breadcrumb ==")
boot("work", [f"{CONF}:all"])
tgt, stk = do_zoom_in("scagent")
check("work→scagent target", tgt, "scagent")
check("work→scagent stack",  stk, ["all", "work"])

print("\n== zoom-out returns to REAL parent, not static ^ (the bug we fixed) ==")
# every multi-entry section: entering via work must zoom-out back to work
for sec in ["te", "kb", "scagent", "sys", "demo", "bf"]:
    boot(sec, [f"{CONF}:all", f"{CONF}:work"])
    check(f"work→{sec}→out", do_zoom_out()[0], "work")
# entering via life
for sec in ["kb", "te", "tr", "aa", "mv"]:
    boot(sec, [f"{CONF}:all", f"{CONF}:life"])
    check(f"life→{sec}→out", do_zoom_out()[0], "life")

print("\n== sideways uses the REAL parent's ring (not static ^) ==")
# scagent entered via work → next sibling is a WORK kid (te), not a dev kid
boot("scagent", [f"{CONF}:all", f"{CONF}:work"])
nxt, stk = do_zoom_side(True)
check("work→scagent→sideways target", nxt, "te")
check("work→scagent→sideways keeps stack", stk, ["all", "work"])

print("\n== deep in/out unwinds level by level ==")
boot("all", None)
do_zoom_in("work")                                   # all -> work
boot("work", [f"{CONF}:all"]); do_zoom_in("scagent") # work -> scagent
boot("scagent", [f"{CONF}:all", f"{CONF}:work"])
t1, s1 = do_zoom_out(); check("scagent→out1 target", t1, "work"); check("scagent→out1 stack", s1, ["all"])
boot("work", [f"{CONF}:all"])
t2, s2 = do_zoom_out(); check("work→out2 target", t2, "all"); check("work→out2 stack", s2, [])

print("\n== direct entry (no breadcrumb) falls back to static ^parent ==")
boot("kb", None);      check("kb(direct) ^parent",      short(bf.parent), "pr");   check("kb(direct)→out",      do_zoom_out()[0], "pr")
boot("te", None);      check("te(direct) ^parent",      short(bf.parent), "dev");  check("te(direct)→out",      do_zoom_out()[0], "dev")
boot("scagent", None); check("scagent(direct) ^parent", short(bf.parent), "dev");  check("scagent(direct)→out", do_zoom_out()[0], "dev")

print("\n== tr nests under life, bf under work ==")
check("tr ^life",  SECS["tr"]["parent"],  "life")
check("bf ^work",  SECS["bf"]["parent"],  "work")
check("life lists tr", "tr" in SECS["life"]["kids"], True)
check("work lists bf", "bf" in SECS["work"]["kids"], True)

# ─────────────────────────────────────────────────────────────────────────────
print("\n" + ("ALL PASS ✓" if not _fails else f"FAILED ({len(_fails)}): " + "; ".join(_fails)))
sys.exit(1 if _fails else 0)
