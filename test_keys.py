#!/usr/bin/env python3
"""bf key tsts (kb D-029) — run: PYTHONPATH=bin python3 test_keys.py
  help palette rows (runnable · filter · nav) · e/ctrl+e branches exist · no key clash · kb_url via kblink"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "bin"))
import browsefiles as bf  # noqa: E402

fails = 0


def ck(name, ok):
    global fails
    print(("✔️ " if ok else "❌ ") + name)
    fails += not ok


import py_compile  # noqa: E402
import tempfile  # noqa: E402
try:                                    # 🦠 @1118: b2 hit a half-edited file ➡ guard: bf must compile
    py_compile.compile(str(Path(__file__).resolve().parent / "bin/browsefiles.py"), doraise=True)
    ck("py_compile: browsefiles.py compiles", True)
except py_compile.PyCompileError as e:
    ck(f"py_compile: browsefiles.py compiles ({e.msg.strip()[:80]})", False)

with tempfile.TemporaryDirectory() as tmp:     # quick-add sections (A) · kb D-017/018/019
    t = Path(tmp) / "todo_x.md"
    t.write_text("## 🏔️\n## ⏳\n## 🔵\n- old\n## ✔️\n- done\n")
    bf._insert_todo_line(str(t), "- ‼️ hot", bf._TODO_SECTIONS['!'])
    bf._insert_todo_line(str(t), "- someday", bf._TODO_SECTIONS['i'])
    s = t.read_text()
    ck("quick-add ! ➡ top o 🔵 (not 🏔️ · `## ‼️` retired)", "## 🔵\n- ‼️ hot\n- old" in s and "## 🏔️\n## ⏳" in s)
    ck("quick-add i ➡ new `## 💭` at th bottom", s.rstrip().endswith("## ✔️\n- done\n\n## 💭\n- someday"))
    bf._insert_todo_line(str(t), "- 2nd", '💭')
    ck("quick-add i again ➡ same 💭 section", t.read_text().count("## 💭") == 1 and "## 💭\n- 2nd\n- someday" in t.read_text())
ck("view: 💭 section = off th todo view (like 🔵)", bf._classify_section("## 💭") == "backlog")

bf.FILTERS = bf.parse_filter_config(bf.FILTER_CONFIG)
bf.NAV = bf.parse_nav_config(bf.NAV_CONFIG)
rows = bf.help_rows()
fire = [r for r in rows if r[2] is not None]
ck("help: open block 1st = e subl · ctrl+e KB (5)", rows[1][2] == ord('e') and rows[2][2] == 5 and "KB" in rows[2][1])
ck("help: filters + overlays folded i", any("filters" in r[0] for r in rows) and any(r[0] == "n" for r in rows))
ck("help: evy runnable row fires a distinct key (no 2 rows = same key)", len({r[2] for r in fire}) == len(fire))
ck("help: filter shadowed by a main key = flagged ⚠️, not runnable (P 🎩 ⬄ P conf)",
   all("shadowed" in r[1] for r in rows if r[0] == "P" and "filters" not in r[0] and r[2] is None)
   and not any(r[2] == ord('P') and "role" in r[1] for r in rows))
ck("help filter: 'kb' ➡ ctrl+e row, heads gone", any(r[2] == 5 for r in bf.help_filter(rows, "kb"))
   and all(r[2] is not None for r in bf.help_filter(rows, "kb")))
ck("help filter: case-insens", bf.help_filter(rows, "SUBL") == bf.help_filter(rows, "subl"))
act = [i for i, r in enumerate(rows) if r[2] is not None]
ck("help nav: ↓ skips heads · ↑ wraps · End = last", bf.help_step(act, act[0], bf.curses.KEY_DOWN, 10) == act[1]
   and bf.help_step(act, act[0], bf.curses.KEY_UP, 10) == act[-1]
   and bf.help_step(act, act[0], bf.curses.KEY_END, 10) == act[-1])
ck("help nav: letter = not nav (➡ filter)", bf.help_step(act, act[0], ord('x'), 10) is None)

src = (Path(__file__).resolve().parent / "bin/browsefiles.py").read_text()
main = src[src.index("def main(stdscr)"):]
ck("main: ctrl+e (5) branch ➡ open_in_kb", re.search(r"elif ch == 5:.*\n\s+open_in_kb", main) is not None)
ck("Menu: ctrl+e ➡ open_in_kb at th hit line", re.search(r"elif ch == 5:.*\n(.*\n){2}\s+open_in_kb\(files_with_path\[cur\[0\]\], cur\[1\]\)", src) is not None)
ck("main: e still = subl", "elif ch in [ ord('e'), 10]:" in main)
taken = set(bf.FILTERS) | set(bf.NAV)
ck("no clash: e · ctrl+e not a filter / nav key", "e" not in taken and "\x05" not in taken)

url = bf.kb_url(os.path.expanduser("~/gopro/go/pr/kb/todo_kb.md"), 5)
ck("kb_url: go/ md ➡ tow KB url w anchor", url.startswith("http") and "/pr/kb/todo_kb.html" in url)
ck("kb_url: outside go/ ➡ ''", bf.kb_url("/etc/hostname") == "")

print(f"\n{'❌ ' + str(fails) + ' fail' if fails else '✔️ all pass'}")
sys.exit(1 if fails else 0)
