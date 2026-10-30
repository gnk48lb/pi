"""Runs test_spec and adds one ARENA_NOTE line saying which groups of cases failed (the report shows it for failing runs)."""
import collections
import re
import sys
import unittest

sys.path.insert(0, ".")
from tests_hidden import test_spec  # noqa: E402

suite = unittest.defaultTestLoader.loadTestsFromModule(test_spec)
result = unittest.TextTestRunner(stream=sys.stdout, verbosity=1).run(suite)
groups = collections.Counter()
for test, _ in result.failures + result.errors:
    m = re.match(r"test_([a-z_]+?)(?:_\d+)?$", test._testMethodName)
    groups[m.group(1) if m else test._testMethodName] += 1
if groups:
    print("ARENA_NOTE: failed %d/%d (%s)" % (sum(groups.values()), result.testsRun,
                                            ", ".join("%s %d" % kv for kv in groups.most_common())))
else:
    print("ARENA_NOTE: all %d hidden cases pass" % result.testsRun)
sys.exit(0 if result.wasSuccessful() else 1)
