"""python3 -m taskq.cli stats   -- tiny helper that prints the job counts of a JSON store file."""
import sys
from collections import Counter

from .store import JsonFileStore


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 2 or argv[0] != "stats":
        print("usage: python3 -m taskq.cli stats STORE.json", file=sys.stderr)
        return 2
    counts = Counter(job.state.value for job in JsonFileStore(argv[1]).all())
    for state, n in sorted(counts.items()):
        print("%-8s %d" % (state, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
