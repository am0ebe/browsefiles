#!/usr/bin/python3

# 2d: file_idx in main global, so that go left and back will go back to same pos? safe and restore pos...
#OPT parse_filelist: if not filelist # search for filelist__XX in cur Dir

# browsefiles: implement tree like structure. nav up,right,down,left ...
#(later) overview feature!
	# just 3 for each g. concise to skim quickly
	# and elab todo, with more reading and thoughts/optional, not so important todos

# DONE
# * filelist can contain filenames with out paths
# * filelist can contain filenames with relative paths (./a/b )
# * script and filelist can contain rel path (./a/b/browsefiles ../x/filelist)
# * filelist can contain paths with "*","**",'?','[1..3]' at end -> open all ASCII files
# * only keep editable files (discerned by isEditable() )

# TODO
# -------------------------------
# * create structure to go a project UP,DOWN,LEFT,RIGHT
#			to each file note UP,L,R,DOWN filelists
#			note CUR filelist?
# * show icons if up/down/left/right/exists!
# -------------------------------
# > use find menu navigation for normal files....
# > display list of file names and hilight current one...
#	-> need to truncate if list/filenames are too long
# > F8 changes day/night theme
# > press number to jump to file/page
# > use regex in find: either create two finds or prepend query with marker
#
# ------------------------------- SUM
# browse through a custom list of files. Open with editor. Find function.
# uses curses:
# 	https://docs.python.org/3/howto/curses.html
# uses pyfiglet:
# 	pip install pyfiglet
#
#requires magic for filetype
#	pip3 install python-magic#
#===============================
## MISC
# atexit.register(cleanup)
# nonlocal =~ global
# query_bytes = gui.getstr()
# query = query_bytes.decode("utf-8") 		# OR
# query = "".join(map(chr, query_bytes)) 	# map bytes to chr if the bytes since they represent ASCII

import os, sys, curses, re, random, time
import pyfiglet # BIG text
import magic #for isAscii()
from glob import glob as glob #	wildcards in filenames. https://docs.python.org/3/library/glob.html
from pathlib import Path
from pprint import pprint as pp

mLINES = 50

x = 0
y = 0
COLOR_THEME=5
GLOBAL_SEARCH=""
first = True
editor = "subl"
parent=""
filelist=""

def isEditable(file_abs):
	editables=[
		'Unicode text', #UTF-8
		'ASCII text',
	]
	file_type = magic.from_file(file_abs)
	if any( True for e in editables if e in file_type ):
		return True
	else:
		pp(f"skipping uneditable: {file_abs} of type {file_type}")
		return False

def make_abs_filepath(line):

	line = os.path.expanduser(line.strip()) # remove trailing newline + append ~
	if os.sep not in line:
		line = os.getcwd() + os.sep + line # add cwd to files without path

	line = str(Path(line).resolve()) #resolve relative paths (./a/x or ../a/x)
	line = glob(line, recursive=True) # expand *','?','[1..3] and '**' -> list
	return line

def parse_filelist(filelist_):
	#call before init_curses!
	global files_with_path, files_with_kid, filelist_with_path, filelist
	global parent, files, contents, GLOBAL_SEARCH, maxPage

	files = []
	files_with_path = []
	files_with_kid = []
	filelist_with_path = make_abs_filepath(filelist_)[0]
	# input(filelist_with_path)

	cwd = os.path.dirname(filelist_with_path)
	os.chdir(cwd) #! then kids without abspath will be found relative to filelist dir
	filelist = os.path.basename(filelist_with_path)

	print(f"open filelist: {filelist_with_path}")
	with open(filelist_with_path) as f:

		for line in f.readlines():
			# print(f"line: {line}")
			if line.startswith("#") or line.isspace():
				continue #ignore comments, empty

			if line.startswith("^"):
				parent=make_abs_filepath(line[1:-1])[0] #quickfix: abs: glob: always returns list
				continue

			# split line and xtract second file as kid and store in files_with_kid
			kid=""
			if " " in line:
				line,kid = line.split(" ")
				kid = make_abs_filepath(kid)

			line = make_abs_filepath(line)
			for f in line:
				if os.path.isfile(f) and isEditable(f):
					files_with_path.append(f)
					files_with_kid += kid

	files = [f.split('/')[-1] for f in files_with_path] # filenames only
	# [ pp(x) for x in zip(files_with_path,files_with_kid) ]

	#load all files
	contents=[]
	for file in files_with_path:
		with open( file ) as f:
			lines = list( f )
			lines = [x.rstrip() for x in lines] #remove trailing '\n'
			contents.append( lines )

	# info()

def init_curses():
	global gui, contents, maxPage, nColor

	## curses stuff
	curses.noecho()
	curses.cbreak()		# dont wait for enter
	curses.curs_set(0) 	# hide cursor
	gui.keypad(1) 	# nicer escapes like KEY.LEFT

	#colors
	nColor=1
	curses.init_pair(nColor, curses.COLOR_CYAN, curses.COLOR_BLACK); nColor +=1
	curses.init_pair(nColor, curses.COLOR_MAGENTA, curses.COLOR_BLACK); nColor +=1
	curses.init_pair(nColor, curses.COLOR_GREEN, curses.COLOR_BLACK); nColor +=1
	curses.init_pair(nColor, curses.COLOR_RED, curses.COLOR_BLACK); nColor +=1
	curses.init_pair(nColor, curses.COLOR_YELLOW, curses.COLOR_BLACK); nColor +=1
	curses.init_pair(nColor, curses.COLOR_WHITE, curses.COLOR_BLACK); nColor +=1
	curses.init_pair(nColor, curses.COLOR_BLUE, curses.COLOR_BLACK); nColor +=1
	# curses.init_pair(nColor, curses.COLOR_BLACK, curses.COLOR_WHITE); nColor += 1




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

	s1=f"####################### file [{file_idx+1}/{nfiles}] ###"
	p(s1)

	s2_1=f"#       "
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
		p(content[idx])
		idx+=1

def p(msg="", attr=0, add_newline=True):
	global y, x, gui

	msg = str(msg[:curses.COLS-1])

	try:
		gui.addstr(y,x,msg,attr)
	except Exception  as e:
		pass

	if add_newline:
		x = 0
		y += 1
	else:
		x += len(msg)

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
		return type(r) == str

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
				exit()

			elif ch == ord('E'):
				done = []
				args = ()
				for line in self.res:
					if type(line) != list:
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

			else:
				break

			self.show()

def print_help():
	global x, y
	gui.clear()
	y,x=printBIG2(" __ HELP  __ ")
	x=curses.COLS//3
	p("")
	x=curses.COLS//3
	p("?, h			- print this help",color(COLOR_THEME))
	x=curses.COLS//3
	p("a,w,s,d 	- navigate",color(COLOR_THEME))
	x=curses.COLS//3
	p("arrows	- navigate",color(COLOR_THEME))
	x=curses.COLS//3
	p("f, f3, f4 			- find",color(COLOR_THEME))
	x=curses.COLS//3
	p("q, esc 			- quit",color(COLOR_THEME))
	x=curses.COLS//3
	p("e 			- edit current file",color(COLOR_THEME))
	x=curses.COLS//3
	p("E 			- edit all files",color(COLOR_THEME))
	x=curses.COLS//3
	p("l 			- edit file list",color(COLOR_THEME))
	x=curses.COLS//3
	p("p 			- edit this file",color(COLOR_THEME))
	x=curses.COLS//3

	ch = gui.getch()
	gui.clear()
	GLOBAL_SEARCH=""

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
	maxlen = max(len(ele) for ele in ss)

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
	maxlen = max(len(ele) for ele in ss)

	for s in ss:
		gui.addstr(y,x,s,color())
		y+=1

	gui.addstr(curses.LINES-1,0,f"{font}, y:{y}, x:{x}, cols:{curses.COLS}",color())
	return y,x

def zoom_in(file_idx):
	# for cur file > find filelist (if it exists) and
	if files_with_kid:
		# printBIG(f"x{files_with_kid[file_idx]}x")
		# gui.clear()
		os.system(sys.argv[0] + " " + files_with_kid[file_idx]) #recursion
		exit()
	# else:


def zoom_out():
	if parent:
		os.system(f"{sys.argv[0]} {parent}") #recursion.
		exit()
	# else:
	# 	printBIG("nope")
	# 	gui.clear()

def zoom_side(isRight=False):
	global parent, files_with_path, files_with_kid, filelist_with_path
	if not parent:
		return

	cur_filelist = filelist_with_path
	# print(f"files_with_kid: {files_with_kid}")
	print(f"parent!!: {parent}")
	parse_filelist(parent) #resets global: files_with_path, files_with_kid, parent, filelist
	try:
		print(f"files_with_kid: {files_with_kid}")

		if isRight:
			files_with_kid.reverse()
		idx = files_with_kid.index(cur_filelist) - 1


		print(f"found {files_with_kid[idx]}")
		parse_filelist(files_with_kid[idx]) # go left

	except Exception as e:
		print(f"didnt find {cur_filelist}")
		raise e
		parse_filelist(cur_filelist)

def main():

	global x, y, gui, maxPage, GLOBAL_SEARCH, mLINES

	parse_filelist(sys.argv[1])

	file_idx=0
	page=0

	info(files[file_idx])
	ch=input()
	while ch != 'q':
		pp(ch)
		info(files[file_idx])
		# gui.clear()

		if ch == 'q':
			break
		elif ch == 'w':
			zoom_out()
		elif ch == 's':
			zoom_in(file_idx)
		elif ch == 'a':
			zoom_side(isRight=False)
		elif ch == 'd':
			zoom_side(isRight=True)
		else:
			pass
		ch=input()

def info(cfile="xxx"):
	showFullPath=True
	if showFullPath:
		print(f"parent: {parent}")
		print(f"filelist: {filelist}")
		print(f"filelist_with_path: {filelist_with_path}")
		print(f"files: {files}")
		print(f"files_with_path: {files_with_path}")
		print(f"files_with_kid: {files_with_kid}")
	else:
		print(f"parent: {parent.split('/')[-1]}")
		print(f"filelist: {filelist.split('/')[-1]}")
		print(f"filelist_with_path: {filelist.split('/')[-1]}")
		print(f"files: {files}")
		print(f"files_with_path: {files}")
		print(f"files_with_kid: {[kid.split('/')[-1] for kid in files_with_kid]}")

	print(f"curfile: {cfile}")
	pp(f"-------------------------------")


if __name__ == "__main__":
	if len(sys.argv) < 2:
		print(f"usage: {sys.argv[0]} filelist_containing_files to browse through")
		exit()

	# curses.wrapper(main)
	main()
