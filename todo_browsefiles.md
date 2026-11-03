## ⏳
- 🦠 OSC 11 theme-query fallout — watch: @1101 freeze (select-guarded reads) · @1103 `cmds X` results closed by a **late** reply ➡ `getkey()` swallows it + Menu ignores resize (strix: "worx") · ▶ NEXT: use bf i herdr normally, freeze / menu-close back? ➡ reopen

## ‼️


## 📆

## 🔵
- xpand 2 no-txt-files (pdfs, excel). how? 🛑
	- 🔍filenames o 🔍 inside pdf w 🔧 + 🔍 inside excel / other filetypes?
	- non-txt files: mk list + menu; select+enter ➡ open w `o()`; multi-select (1/all/some) ➡ open md w subl
- U/I annotations — urg 1-5, imp 1-5, ti est
- mobile-sync filter — excl ⇧ dirs f filelist view
- auto-backlinks
- fix `make_book_template()` path ➡ `$GO/re/boox/notes` (when resumed)
- 🤖 i herdr theme alw = night: herdr answers OSC 11 w `rgb:0000/0000/0000` (nt th real bg) ➡ `BF_THEME` env override o skip query when `TERM_PROGRAM=herdr`
- 🤖 tst `_osc_query` w a pty: reply split mid-terminator (`…\x1b` | `\\`) + no reply ➡ must return ≤~0.3s (raw-mode freeze @1030, fix only tstd by hand) · + **late** reply (aft timeout) ➡ `getkey()` swallows it, `cmds X` menu stays up (@1103, pty harness i git msg)

## ✔️
- top symb bar should be narrower so theres no line break. or best just fill hspace dynamically.
- when click symb top bar, should show todo_XY first.
- the theme (n/d) isnt set correctly. on diff symb-bar click it toggles sometimes sometimes not. not kept when nav around...
