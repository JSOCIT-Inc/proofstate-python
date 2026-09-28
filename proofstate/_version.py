from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version


@lru_cache(maxsize=1)
def get_proofstate_version() -> str:
    try:
        return version("proofstate")
    except PackageNotFoundError:
        return "0.0.0"


__version__ = get_proofstate_version()
