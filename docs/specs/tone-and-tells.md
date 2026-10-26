# Tone and tells check: behaviour spec

Status: accepted.
Date: 2026-10-25.
Revision: 6. Answers to the build questions are folded in (sections 3 to 7, 10 and 11). Revision 3 adds output that cannot be written and a closed standard error (section 7), with known answers 11.49 to 11.51. Revision 4 has the tests write the file of 11.34 at run time. Revision 5 makes repeated flags harmless (section 3.0), escapes printed paths (section 7), and states that the run stops at the first failing stage (section 7), with known answers 11.52 to 11.54. Revision 6 states Python's rule for `$` in a regex rule (section 4), reads PDF inputs as their extracted text (sections 3.2, 6 and 7), and adds `-h` and `--help`, with a fixed summary (sections 3.0, 3.3 and 7) and known answers in section 11 (11.55 to 11.71).

The command is `<cli> tone`.

## 1. Purpose

Flag wording in résumé and profile copy that reads against the writer (hype, hedges, filler and the habits that make a reader doubt a claim), name the sentence it sits in and say why, and fail only on the rules the user has set as errors.

## 2. Scope

In:
- a rule file, written by the user or taken from the default set;
- one or more input files: text files and PDFs;
- two levels, `error` and `warn`;
- scoped exemptions, each tied to one exact sentence;
- a self-test of every rule against its own examples before any file is checked.

Out:
- rewriting or suggesting wording;
- judging truth: whether a claim is backed is another tool's job;
- any built-in word list beyond the default rule set in section 9. The user's own lists are data in a rule file.

## 3. Inputs

### 3.0 Options

| Option | Meaning |
|---|---|
| `--rules FILE` | The rule file. Given at most once. Without it, the shipped default rule file (section 9) is used. |
| `--warn-only` | Run only `warn` rules on the files (section 3.2). |
| `--stale-check` | Check exemptions for staleness (section 5). |
| `--print-defaults` | Write the shipped default rule file to standard output, byte for byte, and exit `0`. It reads no input file and no rule file, and it allows no other argument: anything else on the command line exits `2`, except `-h` or `--help`, which wins. This is how a user starts a rule file of their own. |
| `-h`, `--help` | Write the fixed summary of section 3.3 to standard output and exit `0`. It reads no rule file and no input file, and it wins over every other argument, `--print-defaults` included. An argument that is exactly `-h` or `--help` counts wherever it stands, even in the place of another option's value. After `--`, every argument is a file name, so `-- --help` checks a file named `--help`. The summary is fixed text, never built from the rules. |

Repeating `--warn-only` or `--stale-check` is harmless and changes nothing. Only `--rules` is limited to one use.

Every other argument is an input file.

### 3.1 The rule file

A UTF-8 JSON object whose only keys are `rules` and `exemptions`. `rules` is a non-empty array. `exemptions` is an array, which may be empty or absent.

Each rule is an object with these keys and no others:
- `id`: unique in the file; one or more lower-case letters, digits and hyphens;
- `level`: `error` or `warn`;
- `kind`: `phrase`, `char` or `regex`;
- `text`: what to match (see section 4). It is never empty. For `char` it is exactly one code point, so an em dash is allowed and a flag emoji, which is two code points, is not;
- `case`: `insensitive` (the default) or `sensitive`. It is allowed only on `phrase` and `regex` rules. A `char` rule always matches its exact code point, and giving it `case` is an error;
- `category`: optional. When present, a non-empty label printed with each finding (for example `hedge`, `filler` or `tell`). It may not contain `]`, a line feed or a carriage return;
- `rationale`: one line, printed with every finding. It is never empty and holds no line feed or carriage return;
- `must_fire`: a non-empty JSON array of non-empty strings, each an example text this rule must flag. A bare string is an error;
- `must_not`: the same shape, each an example text this rule may not flag.

Each exemption is an object with these keys and no others:
- `rule`: the id of an `error` rule;
- `anchor`: an exact sentence fragment. It is never empty;
- `reason`: one line. It is never empty and holds no line feed or carriage return.

Any departure from this section is a self-test failure (section 6, case 3).

### 3.2 Input files

Each named file is read as UTF-8 and checked as one body of text. A file that is not valid UTF-8 cannot be read (section 7). Nothing is normalised: the text is matched exactly as written, line endings and any byte-order mark included. A byte-order mark is not a word character and not a line break, so it never blocks a match at the start of a file and never moves a line number.

**PDFs.** A file whose name ends in `.pdf` (any case) is read as the text that `pdftotext` writes for it, in its default (non-layout) mode: the same extraction the barred check uses, so both tools start from the same text. The barred check then folds that text. This tool does not: it reads the extracted text as UTF-8 and from there treats it exactly as a text file, unnormalised, so case-sensitive rules, `char` rules, exemptions and stale anchors all see the text `pdftotext` wrote. A PDF cannot be read (section 7) when `pdftotext` is missing, fails, does not finish within the tool's time limit, or writes text that is not valid UTF-8. A form feed, which `pdftotext` writes between pages, is whitespace and not a line break, so a PDF's line numbers count line breaks alone.

**Known limit: PDF wraps inside a page.** In its default mode, `pdftotext` removes a line-end hyphen together with the line break wherever a line inside a page wraps after a letter or digit. So `detail-`, a line break, then `oriented` reaches the check as `detailoriented`, and a hyphenated phrase wrapped at its hyphen inside a page of a PDF is not matched. The barred check has the same limit. This is a stated limit of the extraction, not a rule of this tool.

**Line breaks.** For line numbers, sentences and blank lines, LF, CRLF and a lone CR each count as one line break. A **blank line** is a line holding nothing, or only spaces and tabs.

The same file named twice is checked twice and counted twice.

`--warn-only` runs only `warn` rules on every file of that run, so that published copy can be linted without failing on it. A file whose only matches are for `error` rules therefore prints `<file>: clean` under `--warn-only`. A wrapper that wants errors on drafts and warnings on published copy calls the tool twice. `--warn-only` never narrows the self-test, which always checks every rule, and never hides a stale exemption (section 5).

### 3.3 The help summary

The summary is the text below, byte for byte, ending in one line feed. `track-record` is the release's command name: if the name changes, the summary changes with it.

```text
usage: track-record tone [--rules FILE] [--warn-only] [--stale-check] FILE...
       track-record tone --print-defaults

Flag hype, hedges and filler in your copy.

  --rules FILE      the rule file (default: the shipped rules)
  --warn-only       run only warn rules
  --stale-check     check exemptions for staleness
  --print-defaults  write the shipped rule file and exit
  -h, --help        show this summary and exit

exit: 0 no errors, 1 errors found, 2 it cannot run
```

## 4. Matching

- **`phrase`:** the words in `text`, matched as whole words. A **word character** is a letter, a number (any Unicode category starting with L or N) or the underscore. At each end of the phrase whose own character is a word character, the text must have a boundary: the neighbouring character must not be a word character, or the match must sit at the start or end of the text. An end whose own character is not a word character needs no boundary. So `C++` matches in `I wrote C++ daily.`, `etc.` matches in `Go, etc. Then`, and `turnkey` does not match inside `éturnkey`. A space in `text` matches one or more whitespace characters, line breaks included. Every other character in `text` matches itself.
- **`char`:** the single code point in `text`, anywhere it occurs, case-sensitive.
- **`regex`:** `text` is a regular expression in Python syntax. It is the user's data, and the tool does not ship any. `case: insensitive` adds the ignore-case flag and nothing else. Unless the pattern sets its own inline flags, `^` matches only at the start of the text, and `.` does not match a line feed. `$` follows Python's rule: it matches at the end of the text and also just before a line feed that is the text's last character, so a file ending in one line feed still matches `done$` (11.55). It does not match before a final CRLF or before two final line feeds. `\Z` matches only at the very end. Compared with matching only at the very end, Python's rule can add a finding at the end of a file, never lose one. An empty match is never a finding. A regex that matches the empty string as a whole fails the self-test (section 6, case 3).
- Matches of one rule are found left to right, without overlap: the phrase `a a` in `a a a` gives one finding. Different rules are independent, so two rules may each flag the same span, as separate findings.
- Every occurrence is its own finding. Two occurrences of a phrase in one sentence give two findings.
- Findings for a file are listed in rule order (as the rules appear in the file), then by position.
- `case: sensitive` matches exactly. A sensitive rule for lower-case `we` does not flag `We` at the start of a sentence. `case: insensitive` uses full Unicode case folding.

## 5. Exemptions

- An `error` finding is dropped when the whole of its match lies inside an exact, case-sensitive occurrence of an exemption's `anchor` for that rule, in the same file. The anchor is matched exactly as written: a space in an anchor matches only a space, so an anchored sentence that wraps onto a second line in the file is not exempt. A finding inside several anchor occurrences is still dropped once.
- The same phrase anywhere else in the file is still an error, even in the sentence right after the anchor.
- An anchor matched in a different case (all lower case, say) does not exempt.
- **Stale anchors:** with `--stale-check`, an exemption whose anchor, matched the same exact way, appears in none of the run's files is itself an error. Without the flag no staleness is checked, because a run over a single file need not include the anchored one. A stale exemption prints `stale exemption: <rule id>` on a line of its own with no file prefix, one line per stale exemption, in exemption order, after every file's output and before the summary. Each counts as one error in the summary and makes the exit status `1`, with or without `--warn-only`.

## 6. Self-test (before any file is read)

The tool checks the rule file before it opens any input file, and so before it starts `pdftotext` for any PDF. It reports every failure it finds, one line each on standard error, naming the rule or exemption where there is one, and exits `2` with nothing on standard output, when:
1. a rule lacks `must_fire` or `must_not`, or either is empty;
2. a `must_fire` text gives that rule no finding, or a `must_not` text gives it one (the self-test applies case and word boundaries exactly as in section 4, but never exemptions). At least one finding per `must_fire` text is required. Exactly one is a property the default set happens to have (11.21), not a rule;
3. two rules share an id, a key is unknown, a required key is missing, or a value is outside section 3.1 (this includes a regex that matches the empty string);
4. a `regex` text does not compile;
5. an exemption names a rule that does not exist or is not an `error` rule.

A rule added without a working example therefore never runs.

## 7. Output and exit status

For each file, in argument order, either `<file>: clean` or, for each finding:

```text
<file>:<line>: <level> <rule id> [<category>]: <rationale>
    <sentence>
```

- `<line>` is the 1-based line on which the match begins.
- **A sentence end** is a `.`, `!` or `?`, followed by any number of closing quotes or brackets (`"`, `'`, `”`, `’`, `)`, `]`), followed by whitespace or the end of the file. An abbreviation such as `etc.` ends a sentence like any other mark: the sentence is for display only and changes no finding.
- **A sentence** runs from just after the previous sentence end (or the end of the previous blank line, or the start of the file) up to and including its own sentence end, closing quotes and brackets included (or up to the next blank line, or the end of the file).
- `<sentence>` is every sentence the match touches, from the start of the one where the match begins to the end of the one where it ends. So a match that runs across a sentence end prints both sentences. Every run of whitespace inside it, line breaks included, prints as one space, and leading and trailing whitespace is trimmed.
- `[<category>]` is printed only when the rule has one.
- `<file>` is the file's printed path (below).

**The printed path.** Wherever a file name is printed, on standard output or standard error, it is the path as given with these characters escaped:
- the backslash, as `\\`;
- line feed, carriage return and tab, as `\n`, `\r` and `\t`;
- every other control character (U+0000 to U+001F, U+007F, U+0080 to U+009F), as `\x` and two lowercase hex digits;
- the line separator and paragraph separator (U+2028, U+2029) and every format character (Unicode category Cf, including the direction overrides), as `\u` and four lowercase hex digits. Format characters above U+FFFF take `\U` and eight lowercase hex digits. The next-line character U+0085 is a C1 control, so it takes the `\x85` form above.

A path with none of these characters is printed exactly as given. Escaping exists so that no file name can forge or reorder an output line. It changes only what is printed: the file is always opened by the path as given.

Stale exemptions follow, as in section 5. The run then ends with the line `<n> file(s), <e> error(s), <w> warning(s)`, printed literally, `(s)` included.

When the run cannot go ahead, nothing goes to standard output, and the reasons go to standard error, one line each. The run checks in three stages, in this order: the command line (options, and whether any input file is named), then the rule file and its self-test (section 6), then the input files. It stops at the first stage that fails and reports every problem found in that stage. So a missing rule file with no input file named gives one line, saying no input file is named, because the rule file is never reached. All input files are opened before any output, so an unreadable file stops the run before any file is reported.

Its output cannot be written: standard output is closed, or a write to it fails (for example, a full disk, or a reader that closed the pipe). Then the run stops at once, exits `2` and writes one line to standard error, `cannot run: cannot write output`, with no traceback. Lines already written stay written, but the exit status is `2` whatever they said. This includes the help summary: a help write that fails exits `2` with this line.

A closed or failing standard error never changes the exit status. When a message can't be written there, it is dropped, and the run exits exactly as it would have with the message written.

Exit status: `0` with no errors (warnings allowed), `1` with at least one error (stale exemptions included), and `2` when it cannot run: the self-test fails; the rule file is missing, not valid UTF-8 or not valid JSON; an input file is missing, unreadable or not valid UTF-8, or is a PDF that cannot be read (section 3.2); no input file is named; an option is unknown (`-h` and `--help` are known options, section 3.0) or lacks its value, or `--rules` is given twice; or standard output cannot be written. The highest applies.

## 8. Rules that hold in every run

- It never edits a file or the rule file.
- It never suggests a replacement.
- A warning never changes the exit status.
- A closed or failing standard error never changes the exit status (section 7).

## 9. The default rule set

This ships as the tool's default rule file. Each rule is a `phrase`, case-insensitive.

| id | level | text | rationale | must fire | must not |
|---|---|---|---|---|---|
| `results-driven` | error | results-driven | A label the reader cannot check; show a result instead. | `A results-driven engineer.` | `The results drove the plan.` |
| `team-player` | error | team player | A claim every applicant makes; name what you did with the team. | `I am a team player.` | `The team played a part.` |
| `go-getter` | error | go-getter | Hype that reads as filler. | `A real go-getter.` | `We had to go get the data.` |
| `outside-the-box` | error | think outside the box | A cliché in place of the idea itself. | `I think outside the box.` | `The box shipped outside the window.` |
| `detail-oriented` | warn | detail-oriented | Shows care better than it claims it. | `Detail-oriented and fast.` | `Each detail was oriented to the user.` |
| `assisted-with` | warn | assisted with | Names a supporting role without saying what you did. | `I assisted with the launch.` | `The launch was assisted by a script.` |
| `various` | warn | various | A vague quantity; name the things or the number. | `Built various tools.` | `The variance was small.` |
| `etc` | warn | etc | A trailing list hides the item that mattered. | `Python, Go, etc.` | `The etching was fine.` |

Every row's two examples are also its `must_fire` and `must_not` texts, so the self-test proves the defaults.

## 10. Decisions

1. **Stale anchors on request.** The prior tool checked stale anchors only on its built-in set of files. This one checks them only with `--stale-check`, with the same intent: a single-file run can't know about every anchored file.
2. **The sentence, not a fixed window.** The prior tool printed 40 characters on each side of a match. This one prints the whole sentence, so the reader sees the context the rule judged. The parity comparison uses file, line, rule id and level only.
3. **Line numbers, new in this release.** The prior tool printed none.
4. **Exit 2, new in this release.** The prior tool had no cannot-run status: a bad rule list surfaced as an error exit of `1`. This one separates a bad run (`2`) from findings (`1`).
5. **Further differences from the prior tool**, which the parity run should expect:
   - Word characters are Unicode letters, numbers and the underscore. The prior tool's boundary knew only ASCII letters, digits and the underscore.
   - A phrase edge that is not a word character needs no boundary, so `C++` and `etc.` can match. Under the prior tool's boundary they could not.
   - An exemption needs the whole match inside the anchor. The prior tool checked only where the match began. Both agree whenever a match is no longer than the text it sits in.
   - A file that is not valid UTF-8 exits `2`. The prior tool replaced bad bytes and went on.

## 11. Acceptance tests (known answers)

The fixtures are invented. They live under `tests/fixtures/tone/`, except the file of 11.34, which is not valid UTF-8. The tests write that one at run time, because the repository's history scan refuses a file that isn't UTF-8. The PDFs of 11.57 to 11.64 are invented too, and the tests may write them at run time for the same reason. The PDF cases that need `pdftotext` are skipped where it is absent. Each text file ends with one LF unless stated.

**Rule file R1** (shown as a table; the fixture is the JSON form):

| id | level | kind | text | case | category | must fire | must not |
|---|---|---|---|---|---|---|---|
| `turnkey` | error | phrase | turnkey | insensitive | | `A turnkey plan.` | `A turn key plan.` |
| `no-em-dash` | error | char | — (an em dash) | | | `a — b` | `a – b` (an en dash) |
| `assisted-with` | warn | phrase | assisted with | insensitive | hedge | `I assisted with it.` | `It was assisted by me.` |
| `lower-we` | warn | phrase | we | sensitive | | `then we left` | `We left.` |
| `as-you-can-see` | warn | phrase | as you can see | insensitive | tell | `As you can see, yes.` | `You can see it.` |

Every R1 rule's rationale is the line `invented rationale`.

R1's one exemption: rule `turnkey`, anchor `Built the turnkey importer for Example Corp`, reason `invented reason`.

**Rule file R2**, every rule `warn`, case-insensitive, rationale `invented rationale`, no exemptions:

| id | kind | text | must fire | must not |
|---|---|---|---|---|
| `cpp` | phrase | C++ | `I wrote C++ daily.` | `I wrote C daily.` |
| `etc-dot` | phrase | etc. | `Go, etc. Then more.` | `The etc file.` |
| `aa` | phrase | a a | `a a` | `a b` |
| `done-next` | regex | `done\. next` | `It was done. Next came more.` | `done next` |

Each case is one file holding the text shown. Each is run with `--rules` naming R1, and without `--warn-only`, unless stated.

| Case | Text | Findings |
|---|---|---|
| 11.1 | `We shipped a Turnkey importer last spring.` | 1 error, `turnkey`; exit 1 |
| 11.2 | the same text, with `--warn-only` | clean; exit 0 |
| 11.3 | `Built the turnkey importer for Example Corp in a week.` | clean: exempt; exit 0 |
| 11.4 | `built the turnkey importer for example corp in a week.` | 1 error, `turnkey`: the anchor's case differs; exit 1 |
| 11.5 | `Built the turnkey importer for Example Corp. Also a turnkey dashboard.` | 1 error, `turnkey`, in the second sentence only; exit 1 |
| 11.6 | `fast — and more` | 1 error, `no-em-dash`; exit 1 |
| 11.7 | `Then we moved on. We stayed.` | 1 warning, `lower-we`; its sentence prints as `Then we moved on.`; exit 0 |
| 11.8 | `As you can see, it worked. I assisted with planning.` | 2 warnings, in rule order: `assisted-with [hedge]` (sentence 2), then `as-you-can-see [tell]` (sentence 1); exit 0 |
| 11.9 | `turnkey turnkey` | 2 errors, `turnkey`; exit 1 |
| 11.10 | sixty `x`, then `turnkey`, then sixty `y`, with no spaces | clean: no word boundary; exit 0 |
| 11.11 | `line one`, `assisted with`, `line three` on three lines | 1 warning at line 2; its sentence prints as `line one assisted with line three`; exit 0 |

Stale anchors:
- 11.12: the file `No anchor here.` with `--stale-check` gives 1 error, `stale exemption: turnkey`. Exit 1. The whole output is three lines: `<file>: clean`, then `stale exemption: turnkey`, then `1 file(s), 1 error(s), 0 warning(s)`.
- 11.13: the same file without `--stale-check` is clean. Exit 0.
- 11.14: the file of 11.3 with `--stale-check` is clean. Exit 0.

Self-test, each with a scratch rule file:
- 11.15: a rule with no `must_fire` exits 2 and names the rule.
- 11.16: a rule whose `must_fire` text does not fire exits 2 and names the rule.
- 11.17: a rule whose `must_not` text fires exits 2 and names the rule.
- 11.18: a duplicate id exits 2.
- 11.19: an exemption naming a `warn` rule exits 2.

Defaults:
- 11.20: the default rule set passes its own self-test.
- 11.21: each row of section 9 gives exactly one finding on its "must fire" text and none on its "must not" text.

Cannot run:
- 11.22: a missing rule file, a rule file that isn't JSON, a missing input file, or no input file named: exit 2 each.

Phrases, regexes and overlaps (R2):

| Case | Text | Findings |
|---|---|---|
| 11.23 | `I wrote C++ and C# daily.` | 1 warning, `cpp`; exit 0 |
| 11.24 | `Go, Rust, etc. Then more.` | 1 warning, `etc-dot`; its sentence prints as `Go, Rust, etc.`; exit 0 |
| 11.25 | `a a a` | 1 warning, `aa`: no overlap; exit 0 |
| 11.26 | `It was done. Next came more.` | 1 warning, `done-next`; its sentence prints as `It was done. Next came more.`; exit 0 |

Sentences, lines and anchors (R1):

| Case | Text | Findings |
|---|---|---|
| 11.27 | `He said "turnkey." Then he left.` | 1 error; its sentence prints as `He said "turnkey."`; exit 1 |
| 11.28 | `A`, two spaces, `turnkey`, two tabs, `plan.` | 1 error; its sentence prints as `A turnkey plan.`; exit 1 |
| 11.29 | `intro line`, then a line of three spaces, then `turnkey here` | 1 error at line 3; its sentence prints as `turnkey here`; exit 1 |
| 11.30 | `Built the turnkey importer for` and `Example Corp in a week.` on two lines | 1 error at line 1: the anchor does not match across a line break; exit 1 |
| 11.31 | 11.11's text with CRLF line endings | as 11.11 |
| 11.32 | 11.11's text with a lone CR ending each line | as 11.11 |
| 11.33 | `éturnkey`, then `٣turnkey`, then `_turnkey`, each on its own line | clean: each neighbour is a word character; exit 0 |
| 11.34 | `turnkey`, the byte 0xFF, then ` plan` | exit 2, nothing on standard output |

Options and output:
- 11.35: the file of 11.12 with `--warn-only --stale-check` gives the same three lines as 11.12. Exit 1.
- 11.36: the file of 11.1 named twice gives its finding twice and the summary `2 file(s), 2 error(s), 0 warning(s)`. Exit 1.
- 11.37: with no `--rules`, the file `I am a team player.` gives 1 error, `team-player`. Exit 1.
- 11.38: `--print-defaults` prints the shipped default rule file byte for byte. Exit 0. `--print-defaults` with an input file named exits 2.
- 11.39: `--rules` given twice, or an unknown option: exit 2.

Rule-file strictness. Each case is a scratch rule file, and each exits 2 with nothing on standard output, naming the rule or exemption where there is one:
- 11.40: an unknown key in a rule, in an exemption, and at the top level, as three files;
- 11.41: `must_fire` given as a bare string;
- 11.42: a `rationale` holding a line feed, and a `reason` holding a line feed;
- 11.43: a `category` holding `]`;
- 11.44: an empty `text`, and an empty `anchor`;
- 11.45: a `char` rule whose `text` is two code points, and a `char` rule that sets `case`;
- 11.46: an empty `rules` array;
- 11.47: a `regex` rule whose `text` is `x*`, which matches the empty string;
- 11.48: two broken rules in one file give two lines on standard error, one naming each rule.

Output failures:
- 11.49: the file of 11.1 with standard output closed: exit 2, and standard error is exactly `cannot run: cannot write output`.
- 11.50: no input file named, with standard error closed: exit 2.
- 11.51: the file of 11.1 with standard error closed: exit 1.

Options and names:
- 11.52: the file of 11.1 with `--warn-only` given twice gives the same result as with it given once.
- 11.53: the file of 11.1 copied to a file whose name holds a line feed (`bad` + LF + `name.txt`): its finding line starts `bad\nname.txt:`, and no output line starts with `name.txt`.
- 11.54: a missing `--rules` file and no input file named: exit 2, and exactly one line on standard error, saying no input file is named. The same missing `--rules` file with the file of 11.1 named: exit 2, and one line saying the rule file can't be read. The line need not print the file's path, and if it does, the path is printed by the printed-path rule (section 7).

Regex `$` (section 4). **Rule file R3**, both rules `warn`, `regex`, case-insensitive, rationale `invented rationale`, no exemptions: `end-dollar`, text `done$`, must fire `It was done`, must not `done here`; then `end-z`, text `done\Z`, with the same examples. Each run names R3.
- 11.55: `It was done` and one LF: 1 warning, `end-dollar`, at line 1; `end-z` gives none. Exit 0.
- 11.56: `It was done` and two LFs, and `It was done` and one CRLF, as two files: both clean. Exit 0.

PDF inputs (section 3.2), with R1 unless stated:
- 11.57: a PDF whose text is `A turnkey plan.`: 1 error, `turnkey`, at line 1. Exit 1.
- 11.58: the same PDF named with the extension `.PDF`: as 11.57.
- 11.59: a PDF whose text is `Then we moved on. We stayed.`: as 11.7. The text is not folded, so the case-sensitive rule still holds.
- 11.60: a two-page PDF whose second page begins `turnkey here`: the finding's line counts line breaks alone, the form feed adding none.
- 11.61: parity. For one invented PDF, the text this tool checks is byte for byte the text the barred check extracts for it before folding.
- 11.62: a PDF with `pdftotext` absent from `PATH`: exit 2, nothing on standard output.
- 11.63: a file named `fake.pdf` holding the text `not a pdf`, so `pdftotext` fails: exit 2, nothing on standard output. The same with a `pdftotext` stand-in that runs past the tool's time limit: exit 2, nothing on standard output.
- 11.64: the PDF of 11.62, again with `pdftotext` absent, and the scratch rule file of 11.15: exit 2, and standard error holds only the self-test line naming the rule. The self-test fails first, so the PDF is never read.

Help (section 3.3):
- 11.65: `--help` alone, and `-h` alone: exit 0, standard output is exactly the summary of section 3.3, standard error is empty.
- 11.66: `--help` with `--rules` naming a missing file: exit 0, the summary. This proves no rule file is read.
- 11.67: `--help` with no input file: exit 0, the summary.
- 11.68: `--help` with an unknown option: exit 0, the summary.
- 11.69: `--rules --help`: exit 0, the summary (help in a value's place).
- 11.70: `--help` with standard output closed: exit 2, and one line on standard error, `cannot run: cannot write output`.
- 11.71: `--print-defaults --help`: exit 0, the summary, not the defaults.
