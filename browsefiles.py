#!/usr/bin/env python3
#    #!/home/USER/.venvs/o-o/bin/python

# ------------------------------- SUM
# browse through a custom list of files. Open with editor. Find function.
# uses curses:
# 	https://docs.python.org/3/howto/curses.html
#
#	pip3 install xerox 			# cp/paste
#	pip3 install pyfiglet 		# ascii fonts
#	pip3 install python-magic 	# for filetype
#
#	Note:
#	curses key combination can change (different OS, terminal)
#	use curses_key.py to find out keycode and adjust accordingly

import xerox #pip3 install -U xerox # api xclip
import os
import sys
import curses
import re
import random
import time
import pyfiglet # BIG text
import magic #for isAscii()
from pygments import lex
from pygments.lexers.markup import MarkdownLexer
from pygments.token import Token
from glob import glob as glob #	wildcards in filenames. https://docs.python.ofrom pathlib import Path
from pathlib import Path
from pprint import pprint as pp
import tempfile
import datetime
import subprocess
import tty, termios, select
import unicodedata

def disp_width(s):
	# terminal cells a string occupies. emoji = 2 cells but len()=1 codepoint,
	# so manual x-tracking falls behind → next token overwrites emoji's right half (looked like a cut char).
	w = 0
	i, n = 0, len(s)
	while i < n:
		o = ord(s[i])
		nxt = ord(s[i+1]) if i+1 < n else 0
		# standalone modifiers/joiners add no cells
		if unicodedata.combining(s[i]) or o == 0x200d or 0xfe00 <= o <= 0xfe0f or 0x1f3fb <= o <= 0x1f3ff:
			i += 1
			continue
		# 2 cells if: East-Asian Wide/Full · emoji-presentation via VS16 (e.g. ‼️ ⚙️ ↕️)
		# · in the emoji pictograph range (🏋 🖥 etc — many are EAW 'N' yet render wide)
		# · base followed by a skin-tone modifier (🏋🏾)
		wide = (unicodedata.east_asian_width(s[i]) in ('W', 'F')
		        or nxt == 0xfe0f or 0x1f3fb <= nxt <= 0x1f3ff
		        or 0x1f000 <= o <= 0x1faff)
		w += 2 if wide else 1
		i += 1
		# swallow trailing modifiers + ZWJ-joined clusters (single grapheme = same cells)
		while i < n:
			o2 = ord(s[i])
			if unicodedata.combining(s[i]) or 0xfe00 <= o2 <= 0xfe0f or 0x1f3fb <= o2 <= 0x1f3ff:
				i += 1
			elif o2 == 0x200d:        # ZWJ → consume joiner + following base char
				i += 2
			else:
				break
	return w

x = 0
y = 0
COLOR_THEME = 5
GLOBAL_SEARCH = ""
CURRENT_FILTER = ""
HEADER_SIZE = 4

DATE_RE    = re.compile(r'@(\d{3,4}|\d{6})(?!\d|\w)')  # @MDD @MMDD @YYMMDD
MD_LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')

# --- themes -----------------------------------------------------------
# Pair fg colors per theme (pairs 1-7: CYAN MAG GREEN RED YELLOW WHITE BLUE)
# Color ints: BLACK=0 RED=1 GREEN=2 YELLOW=3 BLUE=4 MAGENTA=5 CYAN=6 WHITE=7
THEMES = ['night', 'twilight', 'day']
THEME_IDX = 0
THEME_BG  = {'night': '#222222', 'twilight': '#2e3436', 'day': '#ffffff'}
INITIAL_TERM_BG = ''   # detected on startup for theme selection
THEME_PAIRS = {
    'night':    [6, 5, 2, 1, 3, 7, 4],   # CYAN MAG GREEN RED YELLOW WHITE BLUE
    'twilight': [6, 5, 2, 1, 3, 7, 4],
    'day':      [4, 5, 2, 1, 4, 0, 6],   # BLUE MAG GREEN RED BLUE  BLACK CYAN
}
# ----------------------------------------------------------------------

def _osc_query(code):
	"""Query terminal for current color (10=fg, 11=bg) via OSC sequence. Call BEFORE curses."""
	try:
		fd = sys.stdin.fileno()
		old = termios.tcgetattr(fd)
		tty.setraw(fd)
		os.write(fd, f'\033]{code};?\007'.encode())
		ready, _, _ = select.select([fd], [], [], 0.3)
		resp = b''
		if ready:
			for _ in range(64):
				c = os.read(fd, 4)
				resp += c
				if b'\007' in c or b'\033\\' in c:
					break
		termios.tcsetattr(fd, termios.TCSADRAIN, old)
		return resp.decode('ascii', errors='ignore')
	except Exception:
		return ''

def _parse_rgb(osc_resp):
	"""Parse 'rgb:RRRR/GGGG/BBBB' from OSC response → '#rrggbb'."""
	m = re.search(r'rgb:([0-9a-fA-F]+)/([0-9a-fA-F]+)/([0-9a-fA-F]+)', osc_resp)
	if not m:
		return ''
	def h(s): return int(s[:2], 16)  # take first 2 hex digits (16-bit → 8-bit)
	return f'#{h(m.group(1)):02x}{h(m.group(2)):02x}{h(m.group(3)):02x}'

def _detect_theme_idx(bg_hex):
	"""Match a bg hex color to the nearest known theme index."""
	if not bg_hex:
		return 0
	for i, name in enumerate(THEMES):
		if bg_hex.lower() == THEME_BG[name].lower():
			return i
	try:
		r = int(bg_hex[1:3], 16)
		if r > 0xa0: return THEMES.index('day')
		if r > 0x28: return THEMES.index('twilight')
	except Exception:
		pass
	return 0  # default night


_zoom_source    = ''     # file path that brought us into this filelist (for zoom-out)
VIEW_MODE       = 'todo' # default: hide done(✔️)+backlog(🔵) for quick scan · 'all'|'todo'|'done'
_prev_view      = 'all'  # view before last toggle (for d/t toggle-back)
_notes_mode     = False  # True = displaying companion notes file
_notes_content  = None   # loaded lines of notes file
_notes_file     = None   # path of current notes file
_prev_notes_view= 'all'  # VIEW_MODE to restore when toggling notes off
_overlay_label  = 'NOTES'# header tag for the current overlay (notes/week/res/…)
_git_done_cache = {}     # file_path → list of lines (cached per session)
WEEK_FILE       = os.path.expanduser("~/gopro/go/.conf/week.md")  # default 'w' quick-nav target (generated weekplan)
_VIEW_EMOJI     = {'done': '✔️', 'notes': '📕', 'res': '📌'}  # header-tag emoji per view (todo/all: none)
_RES_SPEC       = 'res.md res/res.md'  # companion resource file for RES view (mirrors nav.conf 's')

# quick-nav overlay map (key → file overlay) — see nav.conf
NAV_CONFIG  = os.path.expanduser("~/.config/user/browsefiles/nav.conf")
DEFAULT_NAV = {
	'n': {'spec': '@notes',  'label': 'notes'},
	'w': {'spec': WEEK_FILE, 'label': 'week'},
}
NAV = {}  # key_char -> {'spec', 'label'} ; loaded from NAV_CONFIG (falls back to DEFAULT_NAV)

FILTER_CONFIG = os.path.expanduser("~/.config/user/browsefiles/filters.conf")
FILTERS = {}  # key_char -> fdef dict (aliases share same dict object)

editor = "subl"
parent = ""
filelist = ""

# ---------------------------------------------------------------------------
# quick-nav config

def parse_nav_config(path):
	# format: key | spec | label   (spec: @notes | ~/abs/path | relative-glob)
	if not os.path.exists(path):
		return dict(DEFAULT_NAV)
	nav = {}
	with open(path) as f:
		for line in f:
			line = line.strip()
			if not line or line.startswith('#'):
				continue
			parts = [s.strip() for s in line.split('|')]
			if len(parts) < 2 or not parts[0]:
				continue
			nav[parts[0]] = {'spec':  parts[1],
			                 'label': parts[2] if len(parts) > 2 else os.path.basename(parts[1])}
	return nav or dict(DEFAULT_NAV)

# ---------------------------------------------------------------------------
# filter config

def parse_filter_config(path):
	filters = {}
	if not os.path.exists(path):
		return filters
	with open(path) as f:
		for line in f:
			line = line.strip()
			if not line or line.startswith('#'):
				continue
			parts = line.split('|', 2)
			if len(parts) < 2:
				continue
			keys_str  = parts[0].strip()
			pat_str   = parts[1].strip()
			desc      = parts[2].strip() if len(parts) > 2 else pat_str

			patterns = []
			section_kw = None
			for token in pat_str.split():
				if token.startswith('§'):
					section_kw = token[1:]
				else:
					patterns.append(token)

			label = " ".join(patterns) if patterns else (section_kw or desc)

			fdef = {
				'patterns':   patterns,
				'section_kw': section_kw,
				'label':      label,
				'desc':       desc,
			}
			for key_char in keys_str.split(','):
				key_char = key_char.strip()
				if key_char:
					filters[key_char] = fdef  # aliases share same dict object
	return filters

# ---------------------------------------------------------------------------

def isEditable(file_abs):

	editable=[
		'Unicode text', #UTF-8
		'ASCII text',
	]
	ignore=[
		'HTML',
		'XML',
	]
	file_type = magic.from_file(file_abs)
	if any(e in file_type for e in editable) and not any(i in file_type for i in ignore):
		return True
	else:
		return False

def make_abs_filepath(line):

	line = os.path.expanduser(line.strip()) # remove trailing newline + expand ~
	if os.sep not in line:
		line = os.getcwd() + os.sep + line # add cwd to files without path

	line = str(Path(line).resolve()) #resolve relative paths (./a/x or ../a/x)
	# Check if the line contains any wildcard characters
	if any(char in line for char in '*?[]'):
		# Use glob if there are wildcard characters
		line = glob(line, recursive=True) # expand *','?','[1..3] and '**'
	else:
		# If no wildcard characters, just wrap it in a list
		if os.path.exists(line):
			line = [line]
		else:
			pp(f"file does not exist: {line}")
			line = []

	return line

def _read_conf_section(conf_abs, section_name):
	"""Extract non-blank, non-comment lines from a [section_name] block in a .conf file."""
	lines = []
	in_section = False
	with open(conf_abs) as f:
		for raw in f:
			s = raw.strip()
			if s.startswith('[') and s.endswith(']'):
				in_section = (s[1:-1].strip() == section_name)
				continue
			if in_section and s and not s.startswith('#'):
				lines.append(s)
	return lines


def parse_filelist(filelist_):
	#call before init_curses!
	global files_with_path, files_with_kid, filelist_with_path, filelist
	global parent, files, contents, GLOBAL_SEARCH

	files = []
	files_with_path = []
	files_with_kid = []
	parent = ""

	# detect conf:section format — colon in the basename
	arg = filelist_.strip()
	is_conf = ':' in os.path.basename(arg)

	if is_conf:
		colon    = arg.rfind(':')
		conf_ref = arg[:colon]
		section  = arg[colon+1:]
		conf_abs = str(Path(os.path.expanduser(conf_ref)).resolve())
		filelist_with_path = conf_abs + ':' + section
		filelist           = os.path.basename(conf_abs) + ':' + section
		cwd = os.path.dirname(conf_abs)
		os.chdir(cwd)
		raw_lines = _read_conf_section(conf_abs, section)
	else:
		filelist_with_path = make_abs_filepath(arg)[0]
		cwd = os.path.dirname(filelist_with_path)
		os.chdir(cwd)
		filelist = os.path.basename(filelist_with_path)
		with open(filelist_with_path) as f:
			raw_lines = [l.rstrip('\n') for l in f]

	for line in raw_lines:
		stripped = line.strip()
		if not stripped or stripped.startswith('#'):
			continue

		if stripped.startswith('^'):
			ref = stripped[1:].strip()
			if is_conf:
				parent = conf_abs + ':' + ref
			elif ':' in os.path.basename(ref):
				# conf:section reference stored literally in temp filelist
				colon = ref.rfind(':')
				conf_part = str(Path(os.path.expanduser(ref[:colon])).resolve())
				parent = conf_part + ':' + ref[colon+1:]
			else:
				res = make_abs_filepath(ref)
				parent = res[0] if res else ''
			continue

		# parse kid: ' > **' / ' > section' (new) or ' kid_path' (old)
		kid            = ['']   # sentinel: no kid
		kid_is_globdir = False  # True → per-file __dir__ expansion

		kid_raw = ''
		if ' > ' in stripped:
			file_part, kid_raw = stripped.split(' > ', 1)
			kid_raw = kid_raw.strip()
		elif ' ' in stripped:
			file_part, kid_raw = stripped.split(' ', 1)
			kid_raw = kid_raw.strip()
		else:
			file_part = stripped

		if kid_raw:
			if kid_raw == '**':
				kid_is_globdir = True
			elif is_conf:
				kid = [conf_abs + ':' + kid_raw]
			else:
				res = make_abs_filepath(kid_raw)
				kid = res if res else ['']

		matched = make_abs_filepath(file_part)
		file_part_is_glob = any(c in file_part for c in '*?[]')

		for f in matched:
			if os.path.isdir(f):
				if file_part_is_glob:
					continue  # skip dirs matched by wildcards — clutters the list
				files_with_path.append(f)
				files_with_kid.append(f'__dir__:{f}')
			elif os.path.isfile(f) and isEditable(f):
				files_with_path.append(f)
				if kid_is_globdir:
					files_with_kid.append(f'__dir__:{os.path.dirname(f)}')
				else:
					files_with_kid += kid

	# sort
	sort_together=sorted(zip(files_with_kid,files_with_path))
	files_with_kid=list(list(zip(*sort_together))[0])
	files_with_path=list(list(zip(*sort_together))[1])

	# float todos to top
	todo_fp  = [f for f in files_with_path if "todo" in f]
	todo_fk  = [files_with_kid[i] for i, f in enumerate(files_with_path) if "todo" in f]
	other_fp = [f for f in files_with_path if "todo" not in f]
	other_fk = [files_with_kid[i] for i, f in enumerate(files_with_path) if "todo" not in f]
	files_with_path = todo_fp + other_fp
	files_with_kid  = todo_fk + other_fk

	files    = [f.split('/')[-1] + ('/' if os.path.isdir(f) else '') for f in files_with_path]
	contents = [None] * len(files_with_path)  # lazy: loaded on first access via get_content()

_nav_link_re = re.compile(r'^\[.+?\]\(.+?\)\s*$')

def get_content(file_idx):
	if contents[file_idx] is None:
		file = files_with_path[file_idx]
		if os.path.isdir(file):
			contents[file_idx] = sorted(os.listdir(file))
		else:
			with open(file) as f:
				lines = [l.rstrip() for l in f]
			# strip standalone nav links from top (e.g. [top](../all.md))
			for _ in range(2):
				if lines and _nav_link_re.match(lines[0]):
					lines.pop(0)
			contents[file_idx] = lines
	return contents[file_idx]

def _view_emoji_suffix(label):
	e = _VIEW_EMOJI.get(label.lower(), '')
	return f" {e}" if e else ''

def _classify_section(header_line):
	low = header_line.lower()
	if 'done' in low or '✔️' in header_line or '✅' in header_line:
		return 'done'
	if 'backlog' in low or '🔵' in header_line:
		return 'backlog'
	return 'todo'

def filter_content(content, mode):
	if mode == 'all':
		return content
	result = []
	cur = 'todo'  # items before any header belong to 'todo'
	for line in content:
		if line.strip().startswith('#'):
			cur = _classify_section(line)
		if cur == mode:
			result.append(line)
	return result or ['(nothing)']  # avoid empty content crashing maxPage calc

def resolve_nav_target(spec, current_file):
	# spec may list >1 space-separated alternatives; first hit wins (e.g. "res.md res/res.md")
	for alt in spec.split():
		hit = _resolve_nav_alt(alt, current_file)
		if hit:
			return hit
	return None

def _resolve_nav_alt(spec, current_file):
	# @notes → companion notes file · abs/~ path → fixed file · else → glob in current file's dir
	if spec == '@notes':
		return find_notes_file(current_file)
	if spec.startswith('~') or spec.startswith('/'):
		path_ = os.path.expanduser(spec)
		return path_ if os.path.isfile(path_) else None
	matches = sorted(m for m in glob(os.path.join(os.path.dirname(current_file), spec)) if os.path.isfile(m))
	return matches[0] if matches else None

def find_notes_file(file_path):
	dirname  = os.path.dirname(file_path)
	basename = os.path.basename(file_path)
	for candidate in [
		basename.replace('todo_', 'notes_', 1),  # todo_re.md → notes_re.md
		basename.replace('todo_', 'notes_', 1).replace('.md', ''),  # no ext variant
		'notes.md',
		'notes',
	]:
		if candidate == basename:
			continue
		full = os.path.join(dirname, candidate)
		if os.path.isfile(full):
			return full
	# fallback: any notes_*.md in same dir (covers non-todo active files)
	matches = [m for m in glob(os.path.join(dirname, 'notes_*.md')) if os.path.basename(m) != basename]
	if matches:
		return matches[0]
	return None

def get_content_from_file(path):
	try:
		with open(path) as f:
			return [l.rstrip() for l in f]
	except Exception:
		return ['(error reading file)']

def _git_root(file_path):
	try:
		return subprocess.check_output(
			['git', 'rev-parse', '--show-toplevel'],
			cwd=os.path.dirname(os.path.abspath(file_path)),
			text=True, stderr=subprocess.DEVNULL
		).strip()
	except Exception:
		return None

def git_done_content(file_path):
	if file_path in _git_done_cache:
		return _git_done_cache[file_path]

	result = []

	root = _git_root(file_path)
	if root:
		rel = os.path.relpath(file_path, root)
		try:
			log = subprocess.check_output(
				['git', 'log', '--oneline', '-10', '--', rel],
				cwd=root, text=True, stderr=subprocess.DEVNULL
			).strip().splitlines()
			result += ['## 📜 git log', ''] + (log if log else ['(no commits yet)']) + ['']
		except Exception:
			result += ['## 📜 git log', '', '(git error)', '']

	try:
		with open(file_path) as f:
			lines = [l.rstrip() for l in f]
		result += filter_content(lines, 'done')  # the file's own ## ✔️ section (header incl.)
	except Exception:
		result += ['## ✔️', '', '(error reading file)']

	_git_done_cache[file_path] = result
	return result

def _current_content(file_idx):
	if _notes_mode and _notes_content is not None:
		return _notes_content
	if VIEW_MODE == 'done':
		return git_done_content(files_with_path[file_idx])
	return filter_content(get_content(file_idx), VIEW_MODE)

def _maxpage(file_idx):
	return len(_current_content(file_idx)) // curses.LINES

def _apply_theme(theme_name):
	"""Reinitialize curses color pairs for the given theme."""
	bg = -1  # transparent: terminal bg is left to the terminal emulator
	for i, fg_c in enumerate(THEME_PAIRS[theme_name], 1):
		curses.init_pair(i, fg_c, bg)

def init_curses():
	global gui, contents, maxPage, nColor

	curses.noecho()
	curses.cbreak()		# dont wait for enter
	curses.curs_set(0) 	# hide cursor
	gui.keypad(1) 	# nicer escapes like KEY.LEFT

	try:
		curses.use_default_colors()  # enables -1 = transparent background
	except Exception:
		pass

	nColor = 8  # 7 pairs (1-7) will be set by _apply_theme; keep nColor=8 for color()
	_apply_theme(THEMES[THEME_IDX])

	maxPage = _maxpage(0)

	global MD_ATTR
	MD_ATTR = {
		Token.Generic.Heading:    curses.color_pair(5) | curses.A_BOLD,  # yellow bold — H1
		Token.Generic.Subheading: curses.color_pair(5) | curses.A_BOLD,  # yellow bold — H2+
		Token.Generic.Strong:     curses.A_BOLD,
		Token.Generic.Emph:       curses.A_UNDERLINE,
		Token.Literal.String:     curses.color_pair(3),                  # green — inline code
		Token.Comment:            curses.color_pair(1),                  # cyan — blockquotes/comments
		Token.Keyword:            curses.color_pair(4),                  # red
		Token.Name.Tag:           curses.color_pair(2),                  # magenta
	}


def edit(*args):
	#sa https://stackabuse.com/variable-length-arguments-in-python-with-args-and-kwargs/
	sub_args=''
	for a in args:
		if type(a) == int:
			sub_args += f":{a}"
		elif type(a) == str:
			sub_args += f" {a}"

	os.system(f"{editor} {sub_args}")

def printHeader(page, maxPage, file_idx, nfiles):
	W = curses.COLS - 1
	has_parent = bool(parent)
	has_kid = files_with_kid[file_idx] != ""
	nav = ("⇧" if has_parent else " ") + " " + ("⇩" if has_kid else " ")

	s1 = f"## file [{file_idx+1}/{nfiles}] "
	s1 += "#" * max(0, W - len(s1))
	p(s1)

	p(f"# {nav}  ", 0, False)
	printFileStripInline(file_idx)

	if _notes_mode and _notes_file:
		view_tag = f" [{_overlay_label.upper()}{_view_emoji_suffix(_overlay_label)}]"
	elif VIEW_MODE != 'all':
		view_tag = f" [{VIEW_MODE.upper()}{_view_emoji_suffix(VIEW_MODE)}]"
	else:
		view_tag = ""
	s3 = f"## page [{page+1}/{maxPage+1}]{view_tag} "
	s3 += "#" * max(0, W - disp_width(s3))
	p(s3)
	p()

def printFileStripInline(file_idx):
	avail = curses.COLS - 1 - x  # remaining cols on current line

	all_strs = [f"[{files[i]}]" if i == file_idx else f" {files[i]}" for i in range(len(files))]
	total_w  = sum(len(s) for s in all_strs)

	if total_w <= avail:
		for i, s in enumerate(all_strs):
			p(s, color(COLOR_THEME) | curses.A_BOLD if i == file_idx else 0, False)
		p("")
		return

	# window centred on current file; fill with neighbours until budget runs out
	EL     = "…"
	cur_s  = all_strs[file_idx]
	budget = avail - len(cur_s)

	left_s  = [all_strs[i] for i in range(file_idx - 1, -1, -1)]
	right_s = [all_strs[i] for i in range(file_idx + 1, len(files))]
	incl_l, incl_r, li, ri = [], [], 0, 0

	while budget > 0:
		grew = False
		if ri < len(right_s):
			cost = len(right_s[ri]) + (1 if ri + 1 < len(right_s) else 0)
			if cost <= budget:
				incl_r.append(right_s[ri]); budget -= len(right_s[ri]); ri += 1; grew = True
		if li < len(left_s):
			cost = len(left_s[li]) + (1 if li + 1 < len(left_s) else 0)
			if cost <= budget:
				incl_l.append(left_s[li]); budget -= len(left_s[li]); li += 1; grew = True
		if not grew:
			break

	if li < len(left_s):  p(EL, 0, False)
	for s in reversed(incl_l): p(s, 0, False)
	p(cur_s, color(COLOR_THEME) | curses.A_BOLD, False)
	for s in incl_r: p(s, 0, False)
	if ri < len(right_s):  p(EL, 0, False)
	p("")

def color(cid=-1):
	if cid == -1:
		cid = random.randrange(0,nColor)

	return curses.color_pair(cid) | curses.A_BOLD


def printPage(page, content, header):
	start = page * (curses.LINES - header)
	end = start + (curses.LINES - header)
	idx = start

	while start <= idx < end:
		if idx >= len(content):
			break
		p(content[idx], highlight=True)
		idx+=1

def p(msg="", attr=0, add_newline=True, highlight=False):
	global y, x, gui

	msg = str(msg[:curses.COLS-1])

	try:
		if highlight and attr == 0:
			for tok_type, tok_val in lex(msg, MarkdownLexer()):
				if x >= curses.COLS - 1:
					break
				tok_val = tok_val.rstrip('\n')  # pygments appends a '\n' token to every line; we handle newlines below, addstr'ing it corrupts cursor tracking
				if not tok_val:
					continue
				style = next((v for k, v in MD_ATTR.items() if tok_type in k), curses.A_NORMAL)
				trimmed = tok_val[:curses.COLS - x - 1]
				gui.addstr(y, x, trimmed, style)
				x += disp_width(trimmed)
		else:
			gui.addstr(y, x, msg, attr)
			x += disp_width(msg)
	except Exception:
		pass

	if add_newline:
		x = 0
		y += 1

# ---------------------------------------------------------------------------
# search

def find(query=""):

	if query == "":
		query = gui.getstr().decode("utf-8") #convert bytestring to string

		if not query:
			return

	# leading '/' → raw regex; otherwise literal substring (re.escape)
	if query.startswith('/'):
		try:
			pat = re.compile(query[1:], re.IGNORECASE)
		except re.error:
			return None  # invalid regex → no matches
	else:
		pat = re.compile(re.escape(query), re.IGNORECASE)

	result = []
	for file_idx in range(len(files)):
		for lineno, line in enumerate(get_content(file_idx), 1):

			positions = [(m.start(), m.end()) for m in pat.finditer(line) if m.end() > m.start()]

			if positions:
				result.append( [ file_idx, lineno, line, positions ] )

	return result

def find_any(queries):
	# all matches across all queries on each line; positions sorted
	result = []
	for file_idx in range(len(files)):
		for lineno, line in enumerate(get_content(file_idx), 1):
			positions = []
			for q in queries:
				for m in re.finditer(re.escape(q), line, re.IGNORECASE):
					positions.append((m.start(), m.end()))
			if positions:
				positions.sort()
				result.append([file_idx, lineno, line, positions])
	return result or None

def find_by_section(section_kw, patterns=None):
	# match lines under a section header containing section_kw,
	# or that explicitly contain any of patterns.
	# section headers containing any pattern also trigger the section.
	if patterns is None:
		patterns = []
	result = []
	for file_idx in range(len(files)):
		in_section = False
		for lineno, line in enumerate(get_content(file_idx), 1):
			stripped = line.strip()
			if not stripped:
				continue
			if stripped.startswith("#"):
				lower = stripped.lower()
				in_section = section_kw.lower() in lower
				if not in_section and patterns:
					in_section = any(p in stripped for p in patterns)
				continue
			has_explicit = patterns and any(p in line for p in patterns)
			if not has_explicit and not in_section:
				continue
			pos = []
			for p in patterns:
				for m in re.finditer(re.escape(p), line):
					pos.append((m.start(), m.end()))
			pos.sort()
			if not pos:
				pos = [(0, 0)]  # positional match — no explicit symbol on this line
			result.append([file_idx, lineno, line, pos])
	return result or None

_BAND_LABELS = {
	0: '_— overdue —_',
	1: '_— this week —_',
	2: '_— next week+ —_',
	3: '_— next month+ —_',
}

def _date_band(d, today):
	# bucket a date into overdue / this week / next week+ / next month+ (week.md-style horizon)
	if d < today:
		return 0
	if d <= today + datetime.timedelta(days=6):
		return 1
	next_month = (today.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
	if d < next_month:
		return 2
	return 3

def parse_date_tag(digits):
	today = datetime.date.today()
	try:
		if len(digits) in (3, 4):  # @MDD or @MMDD — current year, roll to next if past
			mm, dd = int(digits[:-2]), int(digits[-2:])
			d = datetime.date(today.year, mm, dd)
			if d < today:  # past this year → assume next year
				d = datetime.date(today.year + 1, mm, dd)
			return d
		elif len(digits) == 6:
			yy, mm, dd = int(digits[:2]), int(digits[2:4]), int(digits[4:])
			return datetime.date(2000 + yy, mm, dd)
	except ValueError:
		return None

def find_dated(only_soon=False, urg_syms=('⏰', '🔥')):
	# collect every line bearing an @date tag, sorted chronologically.
	#   only_soon=False → cal view: ALL dated items.
	#   only_soon=True  → now view: overdue + within-7d (auto-urgent) + any urg_syms-flagged.
	# urg_syms = manual urgency markers (lead-time escape hatch — surface regardless of proximity).
	today    = datetime.date.today()
	one_week = today + datetime.timedelta(days=7)
	rows = []
	for file_idx in range(len(files)):
		cur_sec = 'todo'
		for lineno, line in enumerate(get_content(file_idx), 1):
			if line.strip().startswith('#'):
				cur_sec = _classify_section(line)
			if cur_sec == 'done' or '✔️' in line:
				continue  # done items aren't future calendar entries
			positions, dates = [], []
			for m in DATE_RE.finditer(line):
				positions.append((m.start(), m.end()))
				d = parse_date_tag(m.group(1))
				if d:
					dates.append(d)
			has_urg = False
			for sym in urg_syms:
				for m in re.finditer(re.escape(sym), line):
					positions.append((m.start(), m.end()))
					has_urg = True
			if only_soon:
				if not (has_urg or any(d <= one_week for d in dates)):
					continue
			elif not dates:
				continue
			positions.sort()
			if not positions:
				positions = [(0, 0)]
			# no proximity marker: the chronological sort + visible @date already convey "soon"
			sort_key = min(dates) if dates else one_week  # urg-only (no date) sorts into the soon band
			rows.append((sort_key, [file_idx, lineno, line, positions]))
	if not rows:
		return None
	rows.sort(key=lambda r: r[0])
	out, cur_band = [], None
	for sort_key, entry in rows:
		b = _date_band(sort_key, today)
		if b != cur_band:          # band transition → insert week.md-style divider
			cur_band = b
			if out:                # blank line before each band (except the first)
				out.append("")
			out.append(_BAND_LABELS[b])
		out.append(entry)
	return out

def get_indent(line):
	return len(line) - len(line.lstrip())

def expand_with_context(result):
	if not result:
		return result
	# group match entries by file then lineno
	by_file = {}
	for entry in result:
		fi, ln = entry[0], entry[1]
		by_file.setdefault(fi, {})[ln] = entry

	expanded = []
	for fi in sorted(by_file.keys()):
		content    = get_content(fi)
		match_map  = by_file[fi]
		all_linenos = set(match_map)

		for ln in list(match_map):
			idx  = ln - 1
			if not (0 <= idx < len(content)):
				continue
			line  = content[idx]
			mind  = get_indent(line)
			is_hd = line.lstrip().startswith('#')

			# parent: nearest ancestor (less indent, or a heading)
			if not is_hd:
				for i in range(idx - 1, -1, -1):
					prev = content[i]
					if not prev.strip():
						continue
					if prev.lstrip().startswith('#') or get_indent(prev) < mind:
						all_linenos.add(i + 1)
						break

			# descendants
			if is_hd:
				hlevel = len(line) - len(line.lstrip('#'))
				for i in range(idx + 1, min(idx + 51, len(content))):  # cap at 50
					cl = content[i]
					if not cl.strip():
						continue
					if cl.lstrip().startswith('#') and len(cl) - len(cl.lstrip('#')) <= hlevel:
						break
					all_linenos.add(i + 1)
			else:
				for i in range(idx + 1, len(content)):
					cl = content[i]
					if not cl.strip():
						continue
					if get_indent(cl) <= mind:
						break
					all_linenos.add(i + 1)

		for ln in sorted(all_linenos):
			if ln in match_map:
				expanded.append(match_map[ln])
			else:
				raw = content[ln - 1] if ln - 1 < len(content) else ""
				expanded.append([fi, ln, raw, [(0, 0)], True])  # True = context line

	return expanded or None

def follow_link(source_file, line):
	m = MD_LINK_RE.search(line)
	if not m:
		return
	url = m.group(2)
	if url.startswith(('http://', 'https://')):
		os.system(f"xdg-open '{url}' &")
	else:
		base   = os.path.dirname(source_file)
		target = str(Path(os.path.join(base, url)).resolve())
		if os.path.isfile(target):
			edit(target)

def find_links_in_file(file_idx):
	result = []
	for lineno, line in enumerate(get_content(file_idx), 1):
		for m in MD_LINK_RE.finditer(line):
			result.append([file_idx, lineno, line, [(m.start(), m.end())]])
	return result or None

_TODO_SECTIONS = {  # moji-prompt key → status-section header symbol (scaffold order)
	'w': '⏳', 'd': '⏳', '1': '⏳',   # doing / wip
	'!': '‼️', '2': '‼️',             # committed
	'c': '📆', '3': '📆',             # calendar
	'b': '🔵', '4': '🔵',             # backlog (default)
}

def _insert_todo_line(path, line, sect='🔵'):
	# insert under '## <sect>' header; else first header; else append at EOF
	with open(path) as f:
		lines = f.read().splitlines()
	idx = next((i+1 for i, l in enumerate(lines) if l.strip().startswith('#') and sect in l), None)
	if idx is None:
		idx = next((i+1 for i, l in enumerate(lines) if l.strip().startswith('#')), None)
	if idx is None:
		lines.append(line)
	else:
		lines.insert(idx, line)
	with open(path, 'w') as f:
		f.write('\n'.join(lines) + '\n')

def quick_add_todo(file_idx):
	global y, x
	path = files_with_path[file_idx]
	if os.path.isdir(path):
		return
	# phase 1 — type the item freely (digits/letters are text here)
	gui.clear()
	y = curses.LINES - 2; x = 0
	p("quick-add new todo item:")
	y = curses.LINES - 1; x = 0
	p("> ")
	curses.echo()
	try:
		entry = gui.getstr().decode("utf-8").strip()
	except Exception:
		entry = ""
	curses.noecho()
	if not entry:
		gui.clear()
		return
	# phase 2 — file into a section (now the keys are shortcuts, not text)
	gui.clear()
	y = curses.LINES - 2; x = 0
	p(f'file "{entry[:curses.COLS-10]}" →')
	y = curses.LINES - 1; x = 0
	p("⏳=w/1   ‼️ =!/2   📆=c/3   🔵=b/4   (dflt 🔵)")
	curses.flushinp()  # drop the Enter that ended getstr → don't auto-pick
	k = gui.getch()
	sect = _TODO_SECTIONS.get(chr(k), '🔵') if 0 <= k < 256 else '🔵'
	gui.clear()
	_insert_todo_line(path, entry if entry.lstrip().startswith('-') else f"- {entry}", sect)
	contents[file_idx] = None  # invalidate cache → reload on next access

def is_date_filter(fdef):
	return "📆" in fdef['patterns'] or "⏰" in fdef['patterns']

def find_filter(fdef):
	pats = fdef['patterns']
	# date views return a flat chronological list (no context expansion — date is in the line)
	if "📆" in pats:
		return find_dated(only_soon=False)                                   # cal: ALL dated
	if "⏰" in pats:
		urg = tuple(p for p in pats if p in ('⏰', '🔥')) or ('⏰',)
		return find_dated(only_soon=True, urg_syms=urg)                      # now: soon + manual urg
	if fdef['section_kw']:
		res = find_by_section(fdef['section_kw'], pats)
	elif pats:
		res = find_any(pats)
	else:
		return None
	return expand_with_context(res) if res else None

def run_filter(fdef):
	global CURRENT_FILTER
	CURRENT_FILTER = fdef['label']
	res = find_filter(fdef)
	if res:
		Menu(res, flat=is_date_filter(fdef))  # date views: flat chronological, no file headers
	else:
		printBIG("Nah!")
	CURRENT_FILTER = ""  # clear when back in browse mode
	gui.clear()

# ---------------------------------------------------------------------------

class Menu:
	def __init__(self, result, flat=False):
		self.res = list(result)  # copy — don't mutate caller's list

		self.current_row = -1
		self.lines_page = curses.LINES - 1
		self.page = 0
		self.flat = flat

		if not flat:  # flat = chronological/cross-file list — skip per-file section headers
			last_file_idx = -1
			idx = 0
			while idx < len(self.res):

				cur_file_idx = self.res[idx][0]
				if cur_file_idx != last_file_idx:
					last_file_idx = cur_file_idx

					self.res.insert(idx  ,"")
					self.res.insert(idx+1,f"###   {files[cur_file_idx]}   ###") # add header
					idx += 2
				idx += 1

		self.nrow = len(self.res)
		assert self.nrow > 0
		self.maxPage = self.nrow // self.lines_page

		self.cursor(1)
		self.show()
		self.run()

	def isHeader(self, r):
		return isinstance(r,str)

	def show(self):

		global y,x
		y = x = 0
		idx = self.page * self.lines_page

		filter_tag = f" [{CURRENT_FILTER}]" if CURRENT_FILTER else ""
		p(f"##### page [{self.page}/{self.maxPage}]{filter_tag} #####", curses.A_BOLD)

		while idx < (self.page+1) * self.lines_page and idx < self.nrow:
			r = self.res[idx]
			if self.isHeader( r ):
				idx += 1
				p(r, curses.A_BOLD)
				continue

			is_ctx = len(r) > 4 and r[4]
			if idx == self.current_row:
				attr = curses.A_REVERSE | curses.A_BOLD
			elif is_ctx:
				attr = curses.A_DIM
			else:
				attr = curses.A_NORMAL

			lineno = r[1]
			line = r[2].replace('	',' ') #solves display bug with wrong positions because of tabsize
			positions = r[3]

			s = f"{lineno}:"
			p( s, attr, False )
			len_lineno = len(s)

			last_lend = 0
			for lbeg,lend in positions:
				p( line[last_lend:lbeg], attr, False )
				p( line[lbeg:lend], attr | color(COLOR_THEME), False )
				last_lend = lend

			p(line[lend:], attr)

			idx += 1


	def updatePage(self):

		curPage = int( self.current_row / self.lines_page)
		if curPage < self.page:
			if self.page == self.maxPage and curPage == 0:
				self.page = 0
				self.current_row = 0
				self.skipHeader()
			else:
				self.prevPage()
				self.current_row = (self.page+1) * self.lines_page -1 #skip to end
				if self.current_row >= self.nrow:
					self.current_row = self.nrow

		elif curPage > self.page:
			if self.page == 0 and curPage == self.maxPage:
				self.page = self.maxPage
				self.current_row = self.nrow -1
			else:
				self.nextPage()

	def prevPage(self):
		if self.page == 0:
			self.page = self.maxPage
		else:
			self.page -= 1

	def nextPage(self):
		if self.page == self.maxPage:
			self.page = 0
		else:
			self.page += 1

	def skipHeader(self, rel_pos = 1):
		try:
			while self.current_row <= self.nrow and self.isHeader( self.res[self.current_row] ):
				self.current_row += rel_pos
		except:
			pass

	def cursor(self, rel_pos):

		self.current_row += rel_pos
		self.skipHeader(rel_pos)

		if self.current_row < 0:
			self.current_row = self.nrow

		elif self.current_row >= self.nrow:
			self.current_row = 0

	def run(self):
		while True:
			ch = gui.getch()
			gui.clear()

			if ch == curses.KEY_DOWN:
				self.cursor(1)
				self.updatePage()

			elif ch == curses.KEY_UP:
				self.cursor(-1)
				self.updatePage()

			elif ch == curses.KEY_PPAGE:
				self.prevPage()
				self.current_row = self.page * self.lines_page
				self.skipHeader()

			elif ch == curses.KEY_NPAGE:
				self.nextPage()
				self.current_row = self.page * self.lines_page
				self.skipHeader()

			elif ch in [ ord('e'), 10 ]: # 10 == enter
				file = files_with_path[ self.res[self.current_row][0] ]
				row = self.res[self.current_row][1]
				col = self.res[self.current_row][3][0][0]+1
				edit( file, row, col)

			elif ch == ord('E'):
				done = []
				args = ()
				for line in self.res:
					if not isinstance(line,list):
						continue

					file_idx = line[0]
					if file_idx in done:
						continue

					file = files_with_path[ file_idx ]
					row = line[1]
					col = line[3][0][0] + 1
					args += (file, row, col)

					done.append( file_idx )

				edit(*args)
				exit()

			elif ch == ord('o'):
				cur = self.res[self.current_row]
				follow_link(files_with_path[cur[0]], cur[2])

			elif ch == ord('c') and not self.flat:  # in date/flat menus 'c' falls through → exit (toggle back)

				cur_line=self.res[self.current_row][2].replace('	',' ')
				xerox.copy(cur_line)

			elif ch in [ ord('x'), ord('v')]:
				cur_line=self.res[self.current_row][2].replace('	',' ')
				xerox.copy(cur_line)
				exit()

			else:
				break

			self.show()

def print_filelist(file_idx):

	global x, y
	gui.clear()
	y,x=printBIG2(" __ LIST  __ ")
	x=curses.COLS//3
	for i, file in enumerate(files):
		x=curses.COLS//3
		if i == file_idx:
			p(str(i)+"   "+file,color(COLOR_THEME) | curses.A_REVERSE | curses.A_BOLD)
		else:
			p(str(i)+"   "+file,color(COLOR_THEME))

	gui.getch()
	gui.clear()

def print_help():
	global x, y
	gui.clear()
	y,x=printBIG2(" __ HELP  __ ")
	x=curses.COLS//3
	p("")
	x=curses.COLS//3
	p("?, h         - print this help",color(COLOR_THEME))
	x=curses.COLS//3
	p("←→           - prev/next file",color(COLOR_THEME))
	x=curses.COLS//3
	p("↑↓           - scroll page up/down",color(COLOR_THEME))
	x=curses.COLS//3
	p("PgUp/PgDn    - scroll page",color(COLOR_THEME))
	x=curses.COLS//3
	p("F9           - theme: night → twilight → day → night",color(COLOR_THEME))
	x=curses.COLS//3
	p("+/= ctrl+↑   - ⇧ zoom out",color(COLOR_THEME))
	x=curses.COLS//3
	p("-/_ ctrl+↓   - ⇩ zoom in",color(COLOR_THEME))
	x=curses.COLS//3
	p("[/]          - ⇦/⇨ prev/next sibling filelist",color(COLOR_THEME))
	x=curses.COLS//3
	p("f,/          - find (context expansion) · prefix query w / for regex",color(COLOR_THEME))
	x=curses.COLS//3
	p("  regex egs: /a|b (either) · /^## (line-start) · /\\d{4} (4 digits) · /a.*b (a…b) · /\\bTODO (word)",color(COLOR_THEME))
	x=curses.COLS//3
	p("t/d          - toggle Todo/Done view (press again to go back)",color(COLOR_THEME))
	x=curses.COLS//3
	p("a            - show All (reset view)",color(COLOR_THEME))
	x=curses.COLS//3
	p("A            - quick-add todo line (asks section moji: ⏳/‼️/📆/🔵)",color(COLOR_THEME))
	x=curses.COLS//3
	p("v            - cycle views all→todo→done→notes📕→res📌→all",color(COLOR_THEME))
	x=curses.COLS//3
	p("  done view also shows git-history removed done items",color(COLOR_THEME))
	x=curses.COLS//3
	p("--- quick-nav overlays (nav.conf) ---",color(COLOR_THEME))
	for key_char in sorted(NAV.keys()):
		x=curses.COLS//3
		ent = NAV[key_char]
		p(f"{key_char:<13}- {ent['label']} ({ent['spec']})  [toggle]",color(COLOR_THEME))
	x=curses.COLS//3
	p("L            - list links in current file  (o=follow in results)",color(COLOR_THEME))
	x=curses.COLS//3
	p("--- filters (filters.conf) ---",color(COLOR_THEME))
	x=curses.COLS//3

	shown = set()
	for key_char in sorted(FILTERS.keys(), key=lambda k: (not k.isdigit(), k)):
		fdef = FILTERS[key_char]
		fid  = id(fdef)
		if fid in shown:
			continue
		shown.add(fid)
		aliases = sorted([k for k,v in FILTERS.items() if v is fdef],
		                  key=lambda k: (not k.isdigit(), k))
		key_str = ", ".join(aliases)
		x=curses.COLS//3
		p(f"{key_str:<10} - {fdef['label']}  ({fdef['desc']})",color(COLOR_THEME))

	x=curses.COLS//3
	p("--- ---",color(COLOR_THEME))
	x=curses.COLS//3
	p("f1..10       - jump to file",color(COLOR_THEME))
	x=curses.COLS//3
	p("j            - show file list",color(COLOR_THEME))
	x=curses.COLS//3
	p("c            - copy selected line",color(COLOR_THEME))
	x=curses.COLS//3
	p("x, v         - copy selected line and exit",color(COLOR_THEME))
	x=curses.COLS//3
	p("e            - edit current file",color(COLOR_THEME))
	x=curses.COLS//3
	p("w            - week.md quick-view (toggle)",color(COLOR_THEME))
	x=curses.COLS//3
	p("W            - edit current file and exit",color(COLOR_THEME))
	x=curses.COLS//3
	p("E            - edit all files",color(COLOR_THEME))
	x=curses.COLS//3
	p("l            - edit file list",color(COLOR_THEME))
	x=curses.COLS//3
	p("p            - edit source",color(COLOR_THEME))
	x=curses.COLS//3

	gui.getch()
	gui.clear()

def _safe_addstr(y, x, s, attr):
	# clip to screen: skip off-screen rows, trim line to fit width (last cell would ERR)
	if y < 0 or y >= curses.LINES:
		return
	if x < 0:
		s = s[-x:]; x = 0
	maxw = curses.COLS - x - 1
	if maxw <= 0:
		return
	try:
		gui.addstr(y, x, s[:maxw], attr)
	except curses.error:
		pass

def _render_big(s):
	# render within current terminal width so wide words don't overflow
	font = random.choice(["shadow","standard","3-d","block","small","ogre","chunky"])
	f = pyfiglet.Figlet(font=font, width=max(curses.COLS, 1))
	return f.renderText(s).split("\n")

def printBIG(str):

	curses.flash()
	gui.clear()
	ss = _render_big(str)
	y = max(0, curses.LINES // 2 - len(ss) // 2)
	x = max(0, curses.COLS // 2 - 20)

	q=10  # 1s at 0.1s/frame
	while q:
		q-=1
		y_off=0
		for s in ss:
			_safe_addstr(y+y_off, x, s, color())
			y_off+=1
		gui.refresh()
		time.sleep(0.1)

def printBIG2(str,y=0,x=0):

	ss = _render_big(str)
	for s in ss:
		_safe_addstr(y, x, s, color())
		y+=1

	return y,x

def zoom_in(file_idx):
	kid = files_with_kid[file_idx]
	cur_file = files_with_path[file_idx]
	os.environ['BF_INITIAL_FILE'] = cur_file   # child: select this file on zoom-back-out
	os.environ['BF_ZOOM_SOURCE']  = cur_file   # child stores this; used when it zooms out
	if kid.startswith("__dir__:"):
		dirpath = kid[8:]
		with tempfile.NamedTemporaryFile(mode='w', suffix='.fl', delete=False, prefix='bf_') as tf:
			tf.write(f"^{filelist_with_path}\n\n{dirpath}/**\n")
			tmppath = tf.name
		os.system(f"{sys.argv[0]} {tmppath}")
		try: os.unlink(tmppath)
		except: pass
		exit()
	elif kid != "":
		os.system(sys.argv[0] + " " + kid)
		exit()

def zoom_out():
	if parent:
		# _zoom_source = the file in the parent that zoomed us in here → select it on return
		os.environ['BF_INITIAL_FILE'] = _zoom_source if _zoom_source else filelist_with_path
		os.system(f"{sys.argv[0]} {parent}")
		exit()

def _extract_kids_from_lines(raw_lines, conf_abs=None, parent_dir=''):
	"""Collect unique non-** kid references from filelist/conf lines."""
	kids = []
	for line in raw_lines:
		s = line.strip()
		if not s or s.startswith('#') or s.startswith('^'):
			continue
		kid_raw = ''
		if ' > ' in s:
			_, kid_raw = s.split(' > ', 1)
			kid_raw = kid_raw.strip()
		elif ' ' in s:
			_, kid_raw = s.split(' ', 1)
			kid_raw = kid_raw.strip()
		if not kid_raw or kid_raw == '**':
			continue
		if conf_abs:
			ref = conf_abs + ':' + kid_raw
		else:
			ref = os.path.expanduser(kid_raw)
			if not os.path.isabs(ref):
				ref = os.path.join(parent_dir, ref)
			ref = str(Path(ref).resolve())
			if not os.path.isfile(ref):
				continue
		if ref not in kids:
			kids.append(ref)
	return kids


def zoom_side(isRight=False):
	if not parent:
		return

	cur = filelist_with_path
	is_conf_parent = ':' in os.path.basename(parent)

	if is_conf_parent:
		conf_path, par_section = parent.rsplit(':', 1)
		kids = _extract_kids_from_lines(_read_conf_section(conf_path, par_section),
		                                conf_abs=conf_path)
	else:
		try:
			with open(parent) as f:
				raw = [l.rstrip('\n') for l in f]
		except OSError:
			return
		kids = _extract_kids_from_lines(raw, parent_dir=os.path.dirname(parent))

	if cur not in kids or len(kids) < 2:
		return

	idx     = kids.index(cur)
	sibling = kids[(idx + (1 if isRight else -1)) % len(kids)]
	os.system(f"{sys.argv[0]} {sibling}")
	exit()

def main(stdscr):

	global x, y, gui, maxPage, GLOBAL_SEARCH, CURRENT_FILTER, _zoom_source, THEME_IDX
	global VIEW_MODE, _prev_view, _notes_mode, _notes_content, _notes_file, _prev_notes_view, _overlay_label

	gui = stdscr

	parse_filelist(sys.argv[1])
	GLOBAL_SEARCH = " ".join(sys.argv[2:])
	_zoom_source  = os.environ.pop('BF_ZOOM_SOURCE', '')  # file that zoomed us in here

	init_curses()

	file_idx = 0
	page = 0

	# restore selection across zoom-in / zoom-out
	initial_file = os.environ.pop('BF_INITIAL_FILE', None)
	if initial_file:
		basename = os.path.basename(initial_file)
		# 1. match by file basename (zoom-in, or zoom-out via BF_ZOOM_SOURCE)
		found = next((i for i, f in enumerate(files) if f.rstrip('/') == basename), None)
		# 2. match by exact path in files_with_path
		if found is None:
			found = next((i for i, fp in enumerate(files_with_path) if fp == initial_file), None)
		# 3. match by kid filelist path (old zoom-out fallback)
		if found is None:
			ki_base = os.path.basename(initial_file)
			found = next(
				(i for i, k in enumerate(files_with_kid)
				 if k == initial_file or os.path.basename(k) == ki_base),
				None
			)
		if found is not None:
			file_idx = found
			maxPage = _maxpage(file_idx)

	while True:
		x=y=0

		printHeader(page, maxPage, file_idx, len(files))
		printPage(page, _current_content(file_idx), HEADER_SIZE)

		if GLOBAL_SEARCH:
			ch = ord('f') #find
		else:
			ch = gui.getch()

		gui.clear()

		if ch in [ ord('q'), 27 ]: #ESC
			break

		elif ch in [ ord('l') ]:
			target = sys.argv[1]
			if ':' in os.path.basename(target):
				target = target.rsplit(':', 1)[0]  # open conf file, not conf:section string
			edit(target)
			exit()

		elif ch in [ ord('p') ]:
			edit( sys.argv[0])
			exit()

		elif ch in [ ord('?'), ord('h') ]:
			print_help()

		elif ch in [ ord('e'), 10]:
			edit(_notes_file if _notes_mode else files_with_path[ file_idx ])

		elif ch == ord('W'):  # edit current file and exit ('w' is now a quick-nav key)
			edit(_notes_file if _notes_mode else files_with_path[ file_idx ])
			exit()

		elif ch == ord('E'):
			edit(*files_with_path)
			exit()

		elif ch in [ curses.KEY_UP ]:
			if page > 0:
				page -= 1
			else:
				page = maxPage

		elif ch in [ curses.KEY_DOWN ]:
			if page < maxPage:
				page += 1
			else:
				page = 0

		elif ch in [ curses.KEY_PPAGE ]:
			if page > 0:
				page-=1
			else:
				page = maxPage

		elif ch in [ curses.KEY_NPAGE, ord(' ') ]:
			if page < maxPage:
				page+=1
			else:
				page = 0

		elif ch in [ curses.KEY_LEFT ]:
			file_idx = (file_idx - 1) % len(files)
			_notes_mode = False
			maxPage = _maxpage(file_idx)
			page=0

		elif ch in [ curses.KEY_RIGHT ]:
			file_idx = (file_idx + 1) % len(files)
			_notes_mode = False
			maxPage = _maxpage(file_idx)
			page=0

		elif ch in [ ord('+'), ord('='), 337, 567 ] : # shift/ctrl+up
			zoom_out()

		elif ch in [ ord('-'), ord('_'), 336, 526 ] : # shift/ctrl+down
			zoom_in(file_idx)

		elif ch in [ ord('[') ]:
			zoom_side(isRight=False)

		elif ch in [ ord(']') ]:
			zoom_side(isRight=True)

		elif ch == curses.KEY_F9:
			THEME_IDX = (THEME_IDX + 1) % len(THEMES)
			_apply_theme(THEMES[THEME_IDX])
			gui.clear()

		elif ch == curses.KEY_HOME:
			page=0

		elif ch == curses.KEY_END:
			page=maxPage

		elif ch in [ ord('f'), ord('/') ]:

			curses.echo()
			gui.clear()
			y=0; x=0
			p("/=regex")
			y=1; x=0
			p("regex egs: a|b (either) · ^## (line-start) · done$ (line-end) · \\d{4} (4 digits)")
			y=2; x=0
			p("           a.*b (a…b) · (foo|bar) (group) · (ab)+ (repeat) · [aeiou] (charclass)")
			y=3; x=0
			p("(no / prefix = literal substring)")
			y=curses.LINES-1; x=0
			p("find? ")
			y=0

			if GLOBAL_SEARCH:
				CURRENT_FILTER = GLOBAL_SEARCH
				res=find(GLOBAL_SEARCH)
				GLOBAL_SEARCH = ""
			else:
				res=find()

			if res:
				Menu(expand_with_context(res) or res)
			else:
				printBIG("Nah!")

			CURRENT_FILTER = ""
			gui.clear()
			curses.noecho()

		elif ch == ord('t'):
			if VIEW_MODE == 'todo':
				VIEW_MODE = _prev_view
			else:
				_prev_view = VIEW_MODE; VIEW_MODE = 'todo'
			_notes_mode = False; page = 0; maxPage = _maxpage(file_idx)

		elif ch == ord('d'):
			if VIEW_MODE == 'done':
				VIEW_MODE = _prev_view
			else:
				_prev_view = VIEW_MODE; VIEW_MODE = 'done'
			_notes_mode = False; page = 0; maxPage = _maxpage(file_idx)

		elif ch in [ord('a')]:
			VIEW_MODE = 'all'; _prev_view = 'all'
			_notes_mode = False; page = 0; maxPage = _maxpage(file_idx)

		elif ch == ord('A'):  # quick-add a todo line to current file (→ 🔵 backlog)
			quick_add_todo(file_idx)
			page = 0; maxPage = _maxpage(file_idx)

		elif ch == ord('v'):
			modes = ['all', 'todo', 'done', 'notes', 'res']
			cur = _overlay_label if _notes_mode else VIEW_MODE
			if cur not in modes: cur = 'all'  # foreign overlay (week/…) → restart cycle
			nxt = modes[(modes.index(cur) + 1) % len(modes)]
			for _ in range(len(modes)):  # advance, skipping overlays whose companion file is missing
				if nxt in ('notes', 'res'):
					tgt = (find_notes_file(files_with_path[file_idx]) if nxt == 'notes'
					       else resolve_nav_target(_RES_SPEC, files_with_path[file_idx]))
					if tgt:
						_notes_file, _notes_content = tgt, get_content_from_file(tgt)
						_prev_notes_view, _notes_mode, _overlay_label = VIEW_MODE, True, nxt
						break
				else:
					_notes_mode = False
					_prev_view  = VIEW_MODE
					VIEW_MODE   = nxt
					break
				nxt = modes[(modes.index(nxt) + 1) % len(modes)]
			page = 0; maxPage = _maxpage(file_idx)

		elif (32 <= ch < 127) and chr(ch) in NAV:  # quick-nav overlay (nav.conf): n=notes w=week …
			entry  = NAV[chr(ch)]
			target = resolve_nav_target(entry['spec'], files_with_path[file_idx])
			if _notes_mode and target and _notes_file == target:   # same target → toggle off
				_notes_mode = False
				VIEW_MODE = _prev_notes_view
				page = 0; maxPage = _maxpage(file_idx)
			elif target:
				_notes_file      = target
				_notes_content   = get_content_from_file(target)
				_prev_notes_view = VIEW_MODE
				_notes_mode      = True
				_overlay_label   = entry['label']
				page = 0; maxPage = _maxpage(file_idx)
			else:
				printBIG("Nah :)")
				gui.clear()

		else:
			# dynamic filter keys from filters.conf
			ch_char = chr(ch) if 32 <= ch < 127 else None
			if ch_char == 'L':
				CURRENT_FILTER = "links"
				res = find_links_in_file(file_idx)
				if res:
					Menu(res)
				else:
					printBIG("No links")
				CURRENT_FILTER = ""
				gui.clear()
			elif ch_char and ch_char in FILTERS:
				run_filter(FILTERS[ch_char])
			elif ch == curses.KEY_F1:
				file_idx=0
				if file_idx >= len(files)-1:
					file_idx = len(files)-1
			elif ch == curses.KEY_F2:
				file_idx=1
				if file_idx >= len(files)-1:
					file_idx = len(files)-1
			elif ch == curses.KEY_F3:
				file_idx=2
				if file_idx >= len(files)-1:
					file_idx = len(files)-1
			elif ch == curses.KEY_F4:
				file_idx=3
				if file_idx >= len(files)-1:
					file_idx = len(files)-1
			elif ch == curses.KEY_F5:
				file_idx=4
				if file_idx >= len(files)-1:
					file_idx = len(files)-1
			elif ch == curses.KEY_F6:
				file_idx=5
				if file_idx >= len(files)-1:
					file_idx = len(files)-1
			elif ch == curses.KEY_F7:
				file_idx=6
				if file_idx >= len(files)-1:
					file_idx = len(files)-1
			elif ch == curses.KEY_F8:
				file_idx=7
				if file_idx >= len(files)-1:
					file_idx = len(files)-1
			elif ch == curses.KEY_F9:
				file_idx=len(files)-1
			elif ch == curses.KEY_F10:
				file_idx=len(files)-1
			elif ch in [ ord('j'), curses.KEY_DC ]:
				print_filelist(file_idx)



if __name__ == "__main__":
	if len(sys.argv) < 2:
		print(f"usage: {sys.argv[0]} filelist_containing_files to browse through")
		exit()

	FILTERS = parse_filter_config(FILTER_CONFIG)
	NAV     = parse_nav_config(NAV_CONFIG)

	# detect current terminal theme via OSC query (read-only, never writes back)
	INITIAL_TERM_BG = _parse_rgb(_osc_query('11'))
	THEME_IDX       = _detect_theme_idx(INITIAL_TERM_BG)

	curses.wrapper(main)
