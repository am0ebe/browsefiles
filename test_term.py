#!/usr/bin/env python3
"""Terminal-edge tests 4 browsefiles: theme pick at startup + OSC 11 query over a real pty + late-reply swallow.

Run:  python3 test_term.py     # exit 0 = all pass
- startup_theme: BF_THEME wins · herdr (TERM_PROGRAM / HERDR_ENV) ➡ no query, night · else OSC bg ➡ theme
- _osc_query (pty): full reply · reply split mid-ST (`…\\x1b` | `\\\\`) · no reply ➡ back ≤ ~0.3s (raw-mode freeze @1030)
- getkey: a LATE reply (aft th timeout) lands i curses input ➡ swallowed, not read as ESC (`cmds X` menu closed @1103)
"""
import os, pty, sys, threading, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "bin"))
import browsefiles as bf

PASS = FAIL = 0
def check(cond, msg):
	global PASS, FAIL
	if cond: PASS += 1; print(f"  ✔ {msg}")
	else:    FAIL += 1; print(f"  ✗ FAIL {msg}")

# ── startup_theme ───────────────────────────────────────────────────────────
print("[startup theme]")
asked = []
q = lambda code: asked.append(code) or "\033]11;rgb:ffff/ffff/ffff\007"
check(bf.startup_theme({"BF_THEME": "day"}, q) == ("", bf.THEMES.index("day")) and not asked, "BF_THEME=day wins, no query")
check(bf.startup_theme({"BF_THEME": "Twilight "}, q)[1] == bf.THEMES.index("twilight"), "BF_THEME case/space tolerant")
check(bf.startup_theme({"TERM_PROGRAM": "herdr"}, q) == ("", 0) and not asked, "herdr ➡ no OSC query (answers black anyway), night")
check(bf.startup_theme({"HERDR_ENV": "1"}, q) == ("", 0) and not asked, "HERDR_ENV ➡ same")
check(bf.startup_theme({"BF_THEME": "bogus"}, q) == ("#ffffff", bf.THEMES.index("day")) and asked == ["11"], "bad BF_THEME ➡ falls back 2 query")
check(bf.startup_theme({}, lambda c: "")[1] == 0, "no reply ➡ night")

# ── _osc_query over a real pty ──────────────────────────────────────────────
print("\n[_osc_query · pty]")
class Stdin:                                       # _osc_query only needs .fileno()
	def __init__(self, fd): self.fd = fd
	def fileno(self): return self.fd

def run_query(chunks, gap=0.05):
	"""term side writes `chunks` (gap s apart) aft it sees th query ➡ (result, seconds, master fd)."""
	m, s = pty.openpty()
	def term():
		buf = b""
		while b"\007" not in buf:
			buf += os.read(m, 64)
		for c in chunks:
			time.sleep(gap); os.write(m, c)
	threading.Thread(target=term, daemon=True).start()
	old, bf.sys.stdin = bf.sys.stdin, Stdin(s)
	t0 = time.time()
	try:
		r = bf._osc_query("11")
	finally:
		bf.sys.stdin = old
	return r, time.time() - t0, m, s

r, dt, m, s = run_query([b"\033]11;rgb:2222/2222/2222\007"])
check(bf._parse_rgb(r) == "#222222" and dt < 0.5, f"full BEL reply ➡ parsed ({dt:.2f}s)")
os.close(m); os.close(s)
r, dt, m, s = run_query([b"\033]11;rgb:ffff/ffff/ffff\033", b"\\"])
check(r.endswith("\033\\") and bf._parse_rgb(r) == "#ffffff", "ST split mid-terminator (herdr) ➡ both halves read")
os.close(m); os.close(s)
r, dt, m, s = run_query([])
check(r == "" and dt < 0.6, f"no reply ➡ '' i {dt:.2f}s, no raw-mode freeze")
os.close(m); os.close(s)
r, dt, m, s = run_query([b"\033]11;rgb:0000/0000/0000\007"], gap=0.5)   # aft th 0.3s timeout
check(r == "" and dt < 0.6, f"late reply ➡ query gives up i time ({dt:.2f}s)")
time.sleep(0.6)
os.close(m); os.close(s)

# ── getkey: late OSC reply i curses input ───────────────────────────────────
print("\n[getkey · late reply swallow]")
class Gui:
	def __init__(self, keys): self.keys = list(keys)
	def getch(self): return self.keys.pop(0) if self.keys else -1
	def nodelay(self, on): pass
	def timeout(self, ms): pass
ungot = []
bf.curses.ungetch = lambda c: ungot.append(c)
osc = [27, ord("]")] + [ord(c) for c in "11;rgb:0000/0000/0000"]
bf.gui = Gui(osc + [7, ord("q")])
check(bf.getkey() == ord("q"), "BEL-terminated late reply swallowed ➡ nxt real key")
bf.gui = Gui(osc + [27, ord("\\"), ord("j")])
check(bf.getkey() == ord("j"), "ST-terminated late reply swallowed")
bf.gui = Gui([27, -1])
check(bf.getkey() == 27, "lone ESC = real ESC (closes menus as b4)")
bf.gui = Gui([27, ord("x")])
check(bf.getkey() == 27 and ungot == [ord("x")], "alt-combo ➡ ESC + key pushed back")
bf.gui = Gui(osc)                                  # reply cut off, no terminator ➡ timeout ends th swallow
check(bf.getkey() == -1, "unterminated body ➡ swallow ends on timeout (no hang)")

print(f"\n{'=' * 40}\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
