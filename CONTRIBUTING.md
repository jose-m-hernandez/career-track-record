# Contributing

**Pull requests are not being accepted yet.** Before any outside code can be
merged, a contributor licence agreement has to be in place, because the project
is offered under the AGPL and under a commercial licence. Until then, please
open an issue to report a bug or suggest a change, except for a security problem
(see [SECURITY.md](SECURITY.md)).

## How changes are made here

- Every change adds a line to `CHANGELOG.md` under `## [Unreleased]`.
- Every change that alters behaviour adds or updates a test.
- A change that sets a rule records it in `docs/decisions/`, one decision per
  file, named `YYYY-MM-DD-<slug>.md`.
- Commit messages read `<area>: <what changed>`, in the imperative.
- Nothing is committed straight to `main`. Every change, the maintainer's included,
  lands through a pull request.
- Every change is reviewed independently before it lands.
- Outside README § Development, when you mean `ci/barred_strings.py`, write "the maintainer barred-strings scan" at its first mention in a bullet or paragraph; later in that bullet or paragraph "the scan" is enough, and "barred-strings" is never written alone. A "barred entry" is a line in a private list, and "entry" alone is not used for anything else in the same bullet.
- A limit that is accepted rather than fixed gets a one-line `# Known limit:` comment beside the nearest test, not a separate doc file. A limit that a user of a tool can meet is also stated in that tool's spec or the README.
- A module that must start an outside program is the only module that starts it, makes one call, and is excused in the `ALLOW_LIST` of `tests/test_no_network.py` for importing `subprocess` and nothing else.
- Every committed file is valid UTF-8. A test that needs invalid bytes writes them at run time.
- A test module's `if __name__ == "__main__":` guard is its last statement.

## For the maintainer

- Before merging a pull request from a fork, fetch its head commit, run the maintainer barred-strings scan (`ci/barred_strings.py`) locally with the private list, and merge only if the scan is clean. CI cannot run the scan for a fork, because a fork does not get the repository's secrets.
- Approve an intentional use of a barred entry only in the private allow list, never in the repository.
