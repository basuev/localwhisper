import yaml


def test_load_empty_dictionary(tmp_path):
    from localwhisper.dictionary import UserDictionary

    path = tmp_path / "dictionary.yaml"
    d = UserDictionary(path)
    assert d.entries == []


def test_load_existing_dictionary(tmp_path):
    from localwhisper.dictionary import UserDictionary

    path = tmp_path / "dictionary.yaml"
    path.write_text(yaml.dump([{"from": "деплой", "to": "deploy"}]))
    d = UserDictionary(path)
    assert len(d.entries) == 1
    assert d.entries[0] == ("деплой", "deploy")


def test_save_and_reload(tmp_path):
    from localwhisper.dictionary import UserDictionary

    path = tmp_path / "dictionary.yaml"
    d = UserDictionary(path)
    d.add("кластер", "cluster")
    d2 = UserDictionary(path)
    assert d2.entries == [("кластер", "cluster")]


def test_apply_simple_replacement(tmp_path):
    from localwhisper.dictionary import UserDictionary

    path = tmp_path / "dictionary.yaml"
    path.write_text(yaml.dump([{"from": "деплой", "to": "deploy"}]))
    d = UserDictionary(path)
    assert d.apply("деплой на сервер") == "deploy на сервер"


def test_apply_case_insensitive(tmp_path):
    from localwhisper.dictionary import UserDictionary

    path = tmp_path / "dictionary.yaml"
    path.write_text(yaml.dump([{"from": "деплой", "to": "deploy"}]))
    d = UserDictionary(path)
    assert d.apply("Деплой на сервер") == "deploy на сервер"


def test_apply_word_boundaries(tmp_path):
    from localwhisper.dictionary import UserDictionary

    path = tmp_path / "dictionary.yaml"
    path.write_text(yaml.dump([{"from": "кот", "to": "cat"}]))
    d = UserDictionary(path)
    assert d.apply("котик гуляет") == "котик гуляет"
    assert d.apply("кот гуляет") == "cat гуляет"


def test_apply_longer_match_first(tmp_path):
    from localwhisper.dictionary import UserDictionary

    path = tmp_path / "dictionary.yaml"
    path.write_text(
        yaml.dump(
            [
                {"from": "кубернетис кластер", "to": "Kubernetes cluster"},
                {"from": "кластер", "to": "cluster"},
            ]
        )
    )
    d = UserDictionary(path)
    assert d.apply("кубернетис кластер готов") == "Kubernetes cluster готов"


def test_apply_empty_dictionary(tmp_path):
    from localwhisper.dictionary import UserDictionary

    path = tmp_path / "dictionary.yaml"
    d = UserDictionary(path)
    assert d.apply("some text") == "some text"
