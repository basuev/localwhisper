import pytest


def pytest_addoption(parser):
    parser.addoption("--run-slow", action="store_true", default=False, help="Run slow tests")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-slow"):
        skip_slow = pytest.mark.skip(reason="Need --run-slow to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)


@pytest.fixture
def default_config():
    from localwhisper.config import DEFAULT_CONFIG

    return dict(DEFAULT_CONFIG)
