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


def test_diff_simple_replacement():
    from localwhisper.dictionary import UserDictionary

    replacements = UserDictionary.diff("деплой на кубернетис", "deploy на Kubernetes")
    assert ("деплой", "deploy") in replacements
    assert ("кубернетис", "Kubernetes") in replacements
    assert len(replacements) == 2


def test_diff_no_changes():
    from localwhisper.dictionary import UserDictionary

    replacements = UserDictionary.diff("hello world", "hello world")
    assert replacements == []


def test_diff_ignores_insertions_and_deletions():
    from localwhisper.dictionary import UserDictionary

    replacements = UserDictionary.diff("a b c", "a x b c y")
    assert replacements == []


def test_diff_multiple_word_replacement():
    from localwhisper.dictionary import UserDictionary

    replacements = UserDictionary.diff("кубернетис кластер", "Kubernetes cluster")
    assert ("кубернетис", "Kubernetes") in replacements
    assert ("кластер", "cluster") in replacements


def test_add_conflict_returns_old_value(tmp_path):
    from localwhisper.dictionary import UserDictionary

    path = tmp_path / "dictionary.yaml"
    d = UserDictionary(path)
    assert d.add("деплой", "deploy") is None
    conflict = d.add("деплой", "деплою")
    assert conflict == "deploy"
    assert d.entries == [("деплой", "deploy")]


def test_add_same_value_no_conflict(tmp_path):
    from localwhisper.dictionary import UserDictionary

    path = tmp_path / "dictionary.yaml"
    d = UserDictionary(path)
    d.add("деплой", "deploy")
    assert d.add("деплой", "deploy") is None


def test_resolve_conflict(tmp_path):
    from localwhisper.dictionary import UserDictionary

    path = tmp_path / "dictionary.yaml"
    d = UserDictionary(path)
    d.add("деплой", "deploy")
    d.resolve_conflict("деплой", "деплою")
    assert d.entries == [("деплой", "деплою")]


def test_similarity_check():
    from localwhisper.dictionary import UserDictionary

    assert UserDictionary.is_similar("деплой на сервер", "deploy на сервер", 0.4)
    assert not UserDictionary.is_similar(
        "деплой на сервер", "совсем другой текст вообще не связан", 0.4
    )
