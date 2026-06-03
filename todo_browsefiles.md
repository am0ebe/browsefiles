## ⏳

## ‼️
## 📆

## 🔵
- in 'j' file list overview, add scroll mechanism (reuse existing menu class/func?)  
- add file search (useful in big project) to not only search in files, but to search for files as well 
- xpand 2 no-txt-files (pdfs, excel). how? 🛑
	- 🔍filenames o 🔍 inside pdf w 🔧 + 🔍 inside excel / other filetypes?
	- non-txt files: mk list + menu; select+enter ➡ open w `o()`; multi-select (1/all/some) ➡ open md w subl

## ✔️
- regex in find: prefix query w `/` → raw regex (else re.escape literal); invalid regex → no matches; zero-width matches filtered
- `A` quick-add todo: prompt for text → 2nd "moji?" prompt picks section (⏳=w ‼️=! 📆=c 🔵=b, def 🔵) → insert at top of that `## <sect>` (or first header/EOF) · auto-prefix `- ` · cache invalidated
- DONE view: git log + file's own `## ✔️` section (via filter_content) — dropped "last 10 lines" tail
- `v` view cycle now all→todo→done→notes📕→res📌→all (RES via `res.md res/res.md` overlay); header tags show emoji (DONE✔️/NOTES📕/RES📌); missing-companion overlays auto-skip
- 🩹 printBIG crash + ↕️ render space: bounds-clip rows/width, center vertically, figlet width=COLS (`_safe_addstr`/`_render_big`) — fixes addwstr ERR on 'x'/"Nah :)"
- add toggle mode to toggle/show todo_* (optional + notes files) and then show all md files  
- 📆 cal quick-nav: `c`=ALL dated chronological · `3`=now (overdue+7d+⏰/🔥) · widened @MDD regex · urgency derived f date proximity, ⏰=lead-time escape
- done view can it always show git if git exists and then just show last 10 lines (as git oneliner )
- after press 'n' in NOTE mode. press 'e' should open notefile
- press 'n' should toggle notes_xy.md no matter what cur file is (not only wh todo_xy.md is active)
