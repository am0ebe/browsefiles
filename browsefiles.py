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

x = 0
y = 0
COLOR_THEME = 5
GLOBAL_SEARCH = ""

#‼️	add obstacle 🚧, reflect 🪞, try&error/experiment 🧪,❓ for Q, ⁉️ ...,🔍 research/inspect,
# 🖥️ / 📱 ?
experiment_symb = "🧪"
wait_feedback_symb = "👤"
important_symb = "‼️"
urgent_symb = "⏰"

first = True
editor = "subl"
parent = ""
filelist = ""

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

	line = os.path.expanduser(line.strip()) # remove trailing newline + append ~
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

def parse_filelist(filelist_):
	#call before init_curses!
	global files_with_path, files_with_kid, filelist_with_path, filelist
	global parent, files, contents, GLOBAL_SEARCH

	files = []
	files_with_path = []
	files_with_kid = []
	filelist_with_path = make_abs_filepath(filelist_)[0]

	cwd = os.path.dirname(filelist_with_path)
	os.chdir(cwd) #! then kids without abspath will be found relative to filelist dir
	filelist = os.path.basename(filelist_with_path)

	# print(f"open filelist: {filelist_with_path}")
	with open(filelist_with_path) as f:
		lines = f.readlines()

		for line in lines:
			if line.startswith("#") or line.isspace():
				continue #ignore comments, empty

			if line.startswith("^"):
				parent=make_abs_filepath(line[1:-1])[0] #quickfix: abs: glob: always returns list
				continue

			# split line and xtract second file as kid and store in files_with_kid
			kid=" "
			if " " in line:
				line,kid = line.split(" ", 1)
				kid = make_abs_filepath(kid)

			line = make_abs_filepath(line)

			for f in line:
				if os.path.isdir(f):
					files_with_path.append(f)
					files_with_kid.append(f"__dir__:{f}")
				elif os.path.isfile(f) and isEditable(f):
					files_with_path.append(f)
					files_with_kid += kid

	# sort
	sort_together=sorted(zip(files_with_kid,files_with_path))
	files_with_kid=list(list(zip(*sort_together))[0])
	files_with_path=list(list(zip(*sort_together))[1])


	# put todos first, while preserving the order of the rest
	# Separate "todo" and non-"todo" items
	todo_files_with_path = [f for f in files_with_path if "todo" in f]
	todo_files_with_kid = [files_with_kid[idx] for idx, f in enumerate(files_with_path) if "todo" in f]

	non_todo_files_with_path = [f for f in files_with_path if "todo" not in f]
	non_todo_files_with_kid = [files_with_kid[idx] for idx, f in enumerate(files_with_path) if "todo" not in f]

	# Concatenate "todo" items with non-"todo" items
	files_with_path = todo_files_with_path + non_todo_files_with_path
	files_with_kid = todo_files_with_kid + non_todo_files_with_kid

	files = [f.split('/')[-1] + ('/' if os.path.isdir(f) else '') for f in files_with_path]

	contents=[]
	for file in files_with_path:
		if os.path.isdir(file):
			entries = sorted(os.listdir(file))
			contents.append(entries)
		else:
			with open( file ) as f:
				lines = list( f )
				lines = [x.rstrip() for x in lines] #remove trailing '\n'
				contents.append( lines )

def init_curses():
	global gui, contents, maxPage, nColor

	curses.noecho()
	curses.cbreak()		# dont wait for enter
	curses.curs_set(0) 	# hide cursor
	gui.keypad(1) 	# nicer escapes like KEY.LEFT

	#colors
	nColor=1
	curses.init_pair(nColor, curses.COLOR_CYAN, curses.COLOR_BLACK); nColor +=1
	curses.init_pair(nColor, curses.COLOR_MAGENTA, curses.COLOR_BLACK); nColor +=1
	curses.init_pair(nColor, curses.COLOR_GREEN, curses.COLOR_BLACK); nColor +=1
	curses.init_pair(nColor, curses.COLOR_RED, curses.COLOR_BLACK); nColor +=1  # noqa: E702
	curses.init_pair(nColor, curses.COLOR_YELLOW, curses.COLOR_BLACK); nColor +=1
	curses.init_pair(nColor, curses.COLOR_WHITE, curses.COLOR_BLACK); nColor +=1  # noqa: E702
	curses.init_pair(nColor, curses.COLOR_BLUE, curses.COLOR_BLACK); nColor +=1
	# curses.init_pair(nColor, curses.COLOR_BLACK, curses.COLOR_WHITE); nColor += 1

	maxPage = len(contents[0]) // curses.LINES

	global MD_ATTR
	MD_ATTR = {
		Token.Generic.Heading:    curses.color_pair(5) | curses.A_BOLD,  # yellow bold
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
	global HEADER_SIZE
	HEADER_SIZE=4

	has_parent = bool(parent)
	has_kid = files_with_kid[file_idx] != " "
	nav = ("←" if has_parent else " ") + " " + ("→" if has_kid else " ")

	s1=f"####################### file [{file_idx+1}/{nfiles}] ###"
	p(s1)

	s2_1=f"# {nav}   "
	p(s2_1,0,False)

	s2_2=files[file_idx]
	p(s2_2,color(COLOR_THEME),False)

	s2_3=(len(s1)-(len(s2_1)+len(s2_2)+1))*' '+"#"
	p(s2_3,0,True)

	s3=f"####################### page [{page+1}/{maxPage+1}] "
	s3+="#"*(len(s1)-len(s3))
	p(s3)
	p()

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
				style = next((v for k, v in MD_ATTR.items() if tok_type in k), curses.A_NORMAL)
				trimmed = tok_val[:curses.COLS - x - 1]
				gui.addstr(y, x, trimmed, style)
				x += len(trimmed)
		else:
			gui.addstr(y, x, msg, attr)
			x += len(msg)
	except Exception:
		pass

	if add_newline:
		x = 0
		y += 1

def find(query=""):

	if query == "":
		query = gui.getstr().decode("utf-8") #convert bytestring to string

		if not query:
			return

	result = []
	for file_idx,content in enumerate(contents):
		for lineno,line in enumerate(content,1):

			positions=[]
			# store all lineindices in a list of tuples
			# escape string to also search for special chars like '+' or '*'
			# s.translate(s.maketrans({"-":  r"\-","]":  r"\]", ... )
			for m in re.finditer(re.escape(query), line, re.MULTILINE | re.IGNORECASE):
				positions.append( (m.start(), m.end()) )

			if positions:
				result.append( [ file_idx, lineno, line, positions ] )

	return result

class Menu:
	def __init__(self, result):
		self.res = result 	# == file_idx, lineno, line, positions
		beg, end = result[0][3][0]
		self.query = result[0][2][beg:end]

		self.current_row = -1
		self.lines_page = curses.LINES - 1
		self.page = 0

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

		p(f"##### page [{self.page}/{self.maxPage}] #####", curses.A_BOLD)
		# p(f"##### page [{self.page}/{self.maxPage}] ### cur_row: {self.current_row} ### nrow: {self.nrow} ### lines_page: {self.lines_page} ### idx: {idx} ### curpage1: {self.current_row / self.lines_page} ## curpage2: {int( self.current_row / (self.lines_page))}", curses.A_BOLD)

		while idx < (self.page+1) * self.lines_page and idx < self.nrow:
			r = self.res[idx]
			if self.isHeader( r ):
				idx += 1
				p(r, curses.A_BOLD)
				continue

			if idx == self.current_row:
				attr = curses.A_REVERSE | curses.A_BOLD
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
				s = line[last_lend:lbeg]
				p( s, attr, False )
				p( self.query, attr | color(COLOR_THEME), False )
				last_lend = lend

			x = lend + len_lineno
			p(line[lend:], attr)
			# p(line,attr)
			# p(r)

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
				# exit()

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

			elif ch == ord('c'):

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
	global x, y, important_symb
	gui.clear()
	y,x=printBIG2(" __ HELP  __ ")
	x=curses.COLS//3
	p("")
	x=curses.COLS//3
	p("?, h			- print this help",color(COLOR_THEME))
	x=curses.COLS//3
	# p("a,w,s,d 	- navigate",color(COLOR_THEME))
	# x=curses.COLS//3
	p("←↑↓→			- prev/next file",color(COLOR_THEME))
	x=curses.COLS//3
	p("PgUp/PgDn		- scroll page",color(COLOR_THEME))
	x=curses.COLS//3
	p("+/= ctrl+↑		- zoom out",color(COLOR_THEME))
	x=curses.COLS//3
	p("-/_ ctrl+↓		- zoom in",color(COLOR_THEME))
	x=curses.COLS//3
	p("f,/		- find",color(COLOR_THEME))
	x=curses.COLS//3
	p(f"1,2|m,3,4		- show {wait_feedback_symb} ,{important_symb} ,{urgent_symb} ,{experiment_symb}",color(COLOR_THEME))
	x=curses.COLS//3
	p("f1..10	- jump to file",color(COLOR_THEME))
	x=curses.COLS//3
	p("j		- show file list",color(COLOR_THEME))
	x=curses.COLS//3
	p("c			- copy selected line",color(COLOR_THEME))
	x=curses.COLS//3
	p("x, v 			- copy selected line and exit",color(COLOR_THEME))
	x=curses.COLS//3
	p("e 			- edit current file",color(COLOR_THEME))
	x=curses.COLS//3
	p("w 			- edit current file and exit",color(COLOR_THEME))
	x=curses.COLS//3
	p("E 			- edit all files",color(COLOR_THEME))
	x=curses.COLS//3
	p("l 			- edit file list",color(COLOR_THEME))
	x=curses.COLS//3
	p("p 			- edit source",color(COLOR_THEME))
	x=curses.COLS//3

	gui.getch()
	gui.clear()
	# GLOBAL_SEARCH=""

def printBIG(str):

	curses.flash()
	gui.clear()
	y = curses.LINES // 2
	x = curses.COLS // 2 - 20

	fonts = ["shadow","standard","3-d", "block","small","ogre","chunky"]
	# fonts = pyfiglet.FigletFont.getFonts()
	font = random.choice(fonts)
	f = pyfiglet.Figlet(font=font)
	ss=f.renderText(str).split("\n")
	# maxlen = max(len(ele) for ele in ss)

	q=20
	while q:
		q-=1
		y_off=-3
		for s in ss:
			gui.addstr(y+y_off,x,s,color())
			y_off+=1
		gui.addstr(curses.LINES-1,0,f"{font}, y:{y}, x:{x}, cols:{curses.COLS}",color())

		gui.refresh()
		time.sleep(0.1)

def printBIG2(str,y=0,x=0):

	fonts = ["shadow","standard","3-d", "block","small","ogre","chunky"]
	font = random.choice(fonts)
	f = pyfiglet.Figlet(font=font)
	ss=f.renderText(str).split("\n")
	# maxlen = max(len(ele) for ele in ss)

	for s in ss:
		gui.addstr(y,x,s,color())
		y+=1

	gui.addstr(curses.LINES-1,0,f"{font}, y:{y}, x:{x}, cols:{curses.COLS}",color())
	return y,x

def zoom_in(file_idx):
	kid = files_with_kid[file_idx]
	if kid.startswith("__dir__:"):
		dirpath = kid[8:]
		with tempfile.NamedTemporaryFile(mode='w', suffix='.fl', delete=False, prefix='bf_') as tf:
			tf.write(f"^{filelist_with_path}\n\n{dirpath}/**\n")
			tmppath = tf.name
		os.system(f"{sys.argv[0]} {tmppath}")
		try: os.unlink(tmppath)
		except: pass
		exit()
	elif kid != " ":
		os.system(sys.argv[0] + " " + kid)
		exit()

def zoom_out():
	if parent:
		os.system(f"{sys.argv[0]} {parent}") #recursion.
		exit()

def zoom_side(isRight=False):
	# global gui,x,y
	# x=0
	# y=0
	# global parent, files_with_path, files_with_kid, filelist_with_path
	# gui.getch()

	if not parent:
		return

	cur_filelist = filelist_with_path
	# print(f"files_with_kid: {files_with_kid}")
	# p(f"parent!!: {parent}")
	parse_filelist(parent) #resets global: files_with_path, files_with_kid, parent, filelist
	try:
		# p(f"files_with_kid: {files_with_kid}")
		# gui.getch()

		if isRight:
			files_with_kid.reverse()
		idx = files_with_kid.index(cur_filelist) - 1


		print(f"found {files_with_kid[idx]}")
		parse_filelist(files_with_kid[idx]) # go left

	except Exception as e:
		print(f"didnt find {cur_filelist}")
		raise e
		# parse_filelist(cur_filelist)

def main(stdscr):

	global x, y, gui, maxPage, GLOBAL_SEARCH, important_symb

	gui = stdscr

	parse_filelist(sys.argv[1])
	if( len(sys.argv) > 1 ):
		GLOBAL_SEARCH=" ".join(sys.argv[2:])

	init_curses()

	file_idx=0
	page=0

	while True:
		x=y=0

		printHeader(page, maxPage, file_idx, len(files))
		printPage(page,contents[file_idx], HEADER_SIZE)

		if GLOBAL_SEARCH:
			ch = ord('f') #find
		else:
			ch = gui.getch()

		gui.clear()

		if ch in [ ord('q'), 27 ]: #ESC
			break

		elif ch in [ ord('l') ]:
			edit( sys.argv[1])
			exit()

		elif ch in [ ord('p') ]:
			edit( sys.argv[0])
			exit()

		elif ch in [ ord('?'), ord('h') ]:
			print_help()

		elif ch in [ ord('e'), 10]:
			edit(files_with_path[ file_idx ])

		elif ch == ord('w'):
			edit(files_with_path[ file_idx ])
			exit()

		elif ch == ord('E'):
			edit(*files_with_path)
			exit()

		elif ch in [ curses.KEY_UP ]:
			file_idx = (file_idx - 1) % len(files)
			maxPage = len(contents[file_idx]) // curses.LINES
			page=0

		elif ch in [ curses.KEY_DOWN ]:
			file_idx = (file_idx + 1) % len(files)
			maxPage = len(contents[file_idx]) // curses.LINES
			page=0

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
			maxPage = len(contents[file_idx]) // curses.LINES
			page=0

		elif ch in [ curses.KEY_RIGHT ]:
			file_idx = (file_idx + 1) % len(files)
			maxPage = len(contents[file_idx]) // curses.LINES
			page=0

		elif ch in [ ord('+'), ord('='), 337, 567 ] : # shift/ctrl+up
			zoom_out()

		elif ch in [ ord('-'), ord('_'), 336, 526 ] : # shift/ctrl+down
			zoom_in(file_idx)

		elif ch == curses.KEY_HOME:
			page=0

		elif ch == curses.KEY_END:
			page=maxPage

		elif ch in [ ord('f'), ord('/') ]:

			curses.echo()
			gui.clear()
			y=curses.LINES-1
			x=0
			p("find? ")
			y=0

			if GLOBAL_SEARCH:
				res=find(GLOBAL_SEARCH)
				GLOBAL_SEARCH = ""
			else:
				res=find()

			if res:
				Menu(res)
			else:
				printBIG("Nah!")

			gui.clear()
			curses.noecho()

		elif ch in [ord('1')]:
			GLOBAL_SEARCH=wait_feedback_symb
		elif ch in [ord('2'), ord('m')]:
			GLOBAL_SEARCH=important_symb
		elif ch in [ord('3')]:
			GLOBAL_SEARCH=urgent_symb
		elif ch in [ord('4')]:
			GLOBAL_SEARCH=experiment_symb

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
			#tab - 9
			#bkscp 263
			#del / curses.KEY_DC 330
			#space 32
			print_filelist(file_idx)
		else:
			pass



if __name__ == "__main__":
	if len(sys.argv) < 2:
		print(f"usage: {sys.argv[0]} filelist_containing_files to browse through")
		exit()

	# pp(sys.argv)
	parse_filelist(sys.argv[1])
	curses.wrapper(main)
