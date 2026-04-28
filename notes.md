# pr/browsefiles

code: `~/gopro/go/pr/kb/browsefiles/browsefiles.py` (symlinked: `~/bin/browsefiles.py`)
filelists: `~/dotfiles/.config/user/browsefiles/go/`
aliases: te2 ag2 ml2 sy2 pr2 le2 aa2 + ‼️ variants

## status
active — core KB navigation tool. continuously maintained.

## todo
- U/I annotations (urgency 1-5, importance 1-5, time estimate)
- mobile-sync filter (exclude large dirs from filelist view)
- auto-backlinks
- fix make_book_template() path → `$GO/re/boox/notes` when resumed

## notes
curses TUI. reads filelist configs line by line.
format: `glob [drilldown_filelist]` or `^parent_filelist` (nav chain)
symbol `‼️` passed as arg filters to urgent todos only.
