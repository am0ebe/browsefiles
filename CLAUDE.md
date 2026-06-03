# browsefiles — Claude context

## What it is
Curses TUI file browser. Reads a filelist config, displays matched files, opens them in `$EDITOR` (subl). Core KB navigation tool for go/.

## Key paths
- Script: `~/bin/browsefiles.py` (symlink into bin)
- Filelists: `~/.config/user/browsefiles/go/` (= `~/dotfiles/.config/user/browsefiles/go/`)
- Entry alias: `2d` → `browsefiles.py ~/.config/user/browsefiles/go/filelist_all`
- Area aliases: `te2`, `pr2`, `aa2`, etc. → their own filelist

## Filelist format

```
^parent_filelist          # back-navigation (left key goes here)

~/path/to/glob            # file or glob — no kid, just opens
~/path/to/glob filelist_X # file/glob with zoom-in kid (right key → filelist_X)
```

- Lines starting with `#` or blank → ignored
- `^parent` → sets parent for left/back navigation (one per filelist)
- Second column = kid filelist path (relative to filelist dir or absolute)
- Glob support: `*` (one level), `**` (recursive, uses Python `glob(..., recursive=True)`)
- Files filtered by `isEditable()` — only ASCII/UTF-8, not HTML/XML
- todos (`todo` in filename) always sorted to top of list

## Zoom hierarchy (go/ pr/ example)

```
filelist_all
  ~/gopro/go/pr/*/todo_*.md  → filelist_pr      # single * = project subdirs only
    ~/gopro/go/pr/kb/todo_kb.md → filelist_pr_kb
    ~/gopro/go/pr/sys/todo_sys.md → filelist_pr_sys
    ~/gopro/go/pr/scagent/todo_scagent.md → filelist_pr_scagent
      ~/gopro/go/pr/scagent/**                   # all files in project
```

- Use `*` (not `**`) in filelist_all to match only one level deep (skip top-level area todos)
- Each project zoom-in filelist uses `**` to show all files recursively

## Adding a new pr/ project

1. Add line to `filelist_pr`: `~/gopro/go/pr/XY/todo_XY.md filelist_pr_XY`
2. Create `filelist_pr_XY`:
   ```
   ^filelist_pr

   ~/gopro/go/pr/XY/**
   ```

## te/ sub-area pattern (reference)
`filelist_te` uses same pattern for ml/, ag/, sys/ sub-areas.
`filelist_te_ag` → `^filelist_te` + `~/gopro/go/te/ag/**`

## 3-layer hierarchy (browse.conf)
`[all]` (2d) → `[work]`/`[life]` (2w/2l) → each area/project section.
- **Layer 1** `[all]`: every area/project todo, but each entry's kid = its *cluster* (`> work`/`> life`) — so right-arrow groups them. Unclustered (tr, bf) zoom direct to own section.
- **Layer 2** `[work]`/`[life]` (`^all`): cluster's todos, each `> section` → its area. work = scagent/te/le/bigbro/audio/demo/sys/kb · life = aa/bx/mv/po/re/so/te/kb. te+kb appear in both.
- **Layer 3** area sections: the files.

Back-nav: life-exclusive areas `^life`, le `^work`; te/kb (dual) + work pr-projects keep `^dev`/`^pr` (also reachable via `[dev]`/`[pr]` views).
Aliases `2w`/`2l` (+ `2w!`/`2l!` ‼️-filtered) manual in `.common.sh`; `work`/`life` in auto-gen `_bskip` (cluster meta, no cd/`*2` alias) — mirrors `all`/`2d`.

## Key browsefiles.py internals
- `parse_filelist()`: reads filelist, expands globs, builds `files_with_path` + `files_with_kid`
- `files_with_kid`: parallel list — kid filelist path per file (space `" "` if no kid)
- Right key on a file with kid → calls `parse_filelist(kid)` to zoom in
- Left key → calls `parse_filelist(parent)` to zoom out
- `make_abs_filepath()`: expands `~`, resolves relative paths, runs glob with `recursive=True`
- Sort: zip(kid, path) sorted together, then todos floated to top
