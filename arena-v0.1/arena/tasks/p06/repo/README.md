# logrotate-lite

A tiny log rotation tool written in bash.

```
bin/rotate.sh [-n KEEP] [-d] DIR
```

For every non-empty `*.log` file directly inside `DIR` (not in sub-directories):

* `name.log.(k)` becomes `name.log.(k+1)` for k = KEEP-1 ... 1; anything beyond `name.log.KEEP` is dropped,
* `name.log` becomes `name.log.1` and a new, empty `name.log` is created.

Empty logs and files that do not end in `.log` are left alone.

Options:

* `-n KEEP` how many rotated files to keep per log (default 5, a positive integer)
* `-d` dry run: print `would rotate DIR/name.log` for every file that would be rotated (sorted by name), change nothing
* `-h` usage

Usage errors (unknown option, missing or extra arguments, DIR is not a directory, invalid KEEP) print
`rotate: <message>` on **stderr** and exit with status 2.

## Make targets

| target | does |
|---|---|
| `make test` | runs every test case in `test/cases/` |
| `make lint` | syntax-checks the scripts (`bash -n`) and checks that the scripts in `bin/` and `scripts/` are executable |
| `make dist` | builds `dist/logrotate-lite-<version>.tar.gz` (version from the `VERSION` file) |

The tarball contains a single top-level directory `logrotate-lite-<version>/` with `bin/`, `lib/`, `README.md` and `VERSION`
(no tests, no `dist/`).
