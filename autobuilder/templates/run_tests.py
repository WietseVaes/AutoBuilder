import json
import os
import unittest

from gradescope_utils.autograder_utils.json_test_runner import JSONTestRunner

from autobuilder.attempts import make_post_processor

SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {} if default is None else default


def _flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _flatten(item)
        else:
            yield item


if __name__ == '__main__':
    config = _load_json(os.path.join(SOURCE_DIR, "rubric.json"))

    metadata = {}
    for candidate in ("/autograder/submission_metadata.json",
                      os.path.join(SOURCE_DIR, "..", "submission_metadata.json")):
        if os.path.exists(candidate):
            metadata = _load_json(candidate)
            break

    suite = unittest.defaultTestLoader.discover('tests')

    # discover() may import the test module under a different name than a
    # plain `import tests.test_rubric` would -- grab the actual class used
    # by the suite so ATTEMPT_STATUS mutations during run() are visible.
    attempt_status = {}
    for test in _flatten(suite):
        attempt_status = getattr(type(test), "ATTEMPT_STATUS", attempt_status)
        break

    post_processor = make_post_processor(config, metadata, attempt_status)

    with open('/autograder/results/results.json', 'w') as f:
        JSONTestRunner(visibility='visible', stream=f, buffer=False,
                        post_processor=post_processor).run(suite)
