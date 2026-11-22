# `track-record setup`

Choose your record folder once, so the other commands can find your files without a path on every run. `setup` asks for the folder, writes a small config that names it, and makes the folder and four folders inside it. It runs no check.

    track-record setup
    track-record setup --folder PATH
    track-record setup --show

With no option, `setup` asks where the folder should be the first time. On a later run it shows the folder the config names and asks `Keep it? [Y/n]`, and asks for a new place only if you answer no. With `--folder PATH` it uses `PATH` and asks nothing. Run with no terminal and no `--folder`, as from a script, it stops with exit 2:

    cannot run: setup needs --folder when it is not run in a terminal

## What it writes

One config file, which names the record folder, and the folders below. The config is `$CTR_CONFIG_DIR/config.json` if that variable is set, else `$XDG_CONFIG_HOME/track-record/config.json`, else `~/.config/track-record/config.json`. These are the lines a run with `--folder` prints. The folder and config paths here are invented:

    Setup done.
    config: /home/you/.config/track-record/config.json
    record folder: /home/you/my-record
      sources/   old résumés, letters and notes you collect here; no command looks here yet
      postings/  saved job postings; keywords looks here
      drafts/    your own document versions, kept here if you like; no command looks here yet
      plans/     frozen plans for ab and panel, kept here if you like; no command looks here yet
    Create these in your record folder when you need them; the commands look for them there:
      barred-list.txt   your barred wording list (barred)
      claims-list.txt   your approved claims (claims)
      tone-rules.json   your tone rules (tone; the shipped rules are used without it)
      terms.tsv         your keyword terms (keywords)
    next: write barred-list.txt in your record folder, then run: track-record barred --control "Your Name" FILE; see docs/guides/barred.md

Besides the config, `setup` makes the four folders and no file. The four files at the end are the ones you write yourself, in the record folder, when you need them.

## What it changes for the other commands

Once `setup` has named a folder, `barred`, `claims`, `tone` and `keywords` look for their files there, without a path on the command line. `--show` prints the config it found and the file each command would use. It prints these lines for the invented folder above, run right after `setup` and before you have written any of the files:

    config: /home/you/.config/track-record/config.json (found)
    record folder: /home/you/my-record (not checked)
    barred --list: /home/you/my-record/barred-list.txt (not checked)
    claims --list: /home/you/my-record/claims-list.txt (not checked)
    tone --rules: /home/you/my-record/tone-rules.json (not checked)
    keywords --postings: /home/you/my-record/postings (not checked)
    keywords --terms: /home/you/my-record/terms.tsv (not checked)

For `barred`, which lists its default as `$BARRED_STRINGS_PATH`, else your record folder, see [the barred guide](barred.md).

## Exit codes

- 0: done, kept or shown.
- 1: the folder is refused, because git tracks it, or because it is in a work tree that does not ignore it.
- 2: `setup` cannot run.
