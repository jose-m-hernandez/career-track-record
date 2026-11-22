# `track-record absence`

Some claims are claims of absence: a term appears nowhere in a set of files. A search that finds nothing proves that only if it could see the place where the term would be, read every file it was given, and says which files it left out. `absence` runs that search and shows the evidence for each of those three.

It uses the list file that `barred` uses: one term per line, with an optional `word` flag after a tab, read exactly as `barred` reads it. Output names a term by its entry number only. It never prints a term, a matched text or the control phrase.

You give it one declaration file. The declaration names everything the run depends on, so the same file can be run again and cited. The output starts with the declaration's sha256.

## A worked example

The files are made up. Make a folder with these four.

`terms.txt`, the list (the tab before `word` is a real tab):

    orbit-lantern
    velvet compass
    quill	word
    lanternfish

`notes/vendors.txt` holds `Approved vendors: Example Corp and Sample Ltd.`, `notes/plan.txt` holds `The team sharpened its quills before the review.`, and `summary.txt` holds `A quarterly summary of invented work.`

`absence.txt`, the declaration:

    label: no-vendor-terms
    list: terms.txt
    search:
      notes
      summary.txt
    place: notes/vendors.txt
    control: approved vendors

`label` names the run. `search` lists the files and folders to search; a folder is searched in full, hidden files included, and a file's name is searched too. `place` is a file or folder inside the search where the fact would live, and `control` is a phrase that must be found there: it proves the search could see that place. Paths are relative to the declaration's folder.

    track-record absence absence.txt
    declaration sha256 d0fd170273c50a854e05eac8261ba2fd2a66c506dddbd7121a323648fcdb373a
    files: found 3, read 3, excluded 0, unreadable 0, links not followed 0
    CLEAN  no-vendor-terms: 0 hits in 3 files, 0 links not followed, control found

`quills` is not a hit, because entry 3 carries the `word` flag.

## Exclusions

Add `exclusions:` to the declaration, with one `path | reason` item per line, to leave a path out. The reason is required and is never printed. An excluded path is still read, and the output says how many hits it held, as a number:

    excluded notes/archive: 2 hits in 1 files, 0 not read

So an exclusion shows how much it hid. A file inside an exclusion that cannot be read is counted as not read and does not stop the run.

## The result

- `CLEAN` means no hit outside the exclusions. Exit 0.
- `FOUND` means a term appears. Each path that holds one is listed by its name and the entry numbers. A path whose own name matches an entry is listed as `file #<n>`, by its place in the search order, never by its name. Exit 1.
- `DEAD` means the search could not see, and proves nothing: no file was found, the place is outside the search or inside an exclusion, a file could not be read, or the control was not found at the place. A DEAD run reports no hits. Exit 2, which is not a pass.

A run that cannot go ahead, for example a declaration with a problem or counts that do not reconcile, writes nothing to standard output and says why on standard error. Exit 2.

## Known limits

- It cannot see words inside a file that is not text, such as an image or an archive. Such a file counts as read, and its name is still searched.
- Symbolic links are counted and not followed. The output says how many.

Spec: [docs/specs/absence.md](../specs/absence.md).
