import os

from proofstate import ProofState
from proofstate.logger import proofstate_logger

"""
Level	Numeric value
logging.DEBUG	10
logging.INFO	20
logging.WARNING	30
logging.ERROR	40
"""


def test_default_proofstate():
    ProofState()

    assert proofstate_logger.level == 30


def test_via_env():
    os.environ["PROOFSTATE_DEBUG"] = "True"

    ProofState()

    assert proofstate_logger.level == 10

    os.environ.pop("PROOFSTATE_DEBUG")


def test_debug_proofstate():
    ProofState(debug=True)
    assert proofstate_logger.level == 10

    # Reset
    proofstate_logger.setLevel("WARNING")
