import json
import os
import unittest

from gradescope_utils.autograder_utils.json_test_runner import JSONTestRunner

from autobuilder import attempt_recorder
from autobuilder.attempts import make_post_processor

SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


if __name__ == '__main__':
    config = _load_json(os.path.join(SOURCE_DIR, "rubric.json"))
    metadata = _load_json("/autograder/submission_metadata.json")

    attempt_recorder.clear()

    suite = unittest.defaultTestLoader.discover('tests')
    post_processor = make_post_processor(config, metadata)

    with open('/autograder/results/results.json', 'w') as f:
        JSONTestRunner(visibility='visible', stream=f, buffer=False,
                        post_processor=post_processor).run(suite)
