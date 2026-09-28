from importlib.metadata import version

import proofstate


def test_package_version_matches_distribution_metadata():
    assert proofstate.__version__ == version("proofstate")
