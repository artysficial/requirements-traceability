import pytest

from rtm.matrix import fetch_test_results, load_json

pytest_plugins = ["results_plugin"]


@pytest.fixture(scope="session")
def model():
    return load_json("requirements.json")


@pytest.fixture(scope="session")
def stories():
    return load_json("stories.json")


@pytest.fixture(scope="session")
def results():
    return fetch_test_results()[0]
