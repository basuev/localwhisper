from pathlib import Path


def test_config_example_path_prefers_repo_file():
    from localwhisper.paths import config_example_path

    path = config_example_path()
    assert path == Path(__file__).resolve().parent.parent / "config.example.yaml"


def test_executable_path_returns_path_instance():
    from localwhisper.paths import executable_path

    path = executable_path()
    assert isinstance(path, Path)
