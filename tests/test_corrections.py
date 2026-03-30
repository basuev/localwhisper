import yaml


def test_load_empty_corrections(tmp_path):
    from localwhisper.corrections import CorrectionsStore

    path = tmp_path / "corrections.yaml"
    store = CorrectionsStore(path)
    assert store.entries == []


def test_add_and_reload(tmp_path):
    from localwhisper.corrections import CorrectionsStore

    path = tmp_path / "corrections.yaml"
    store = CorrectionsStore(path)
    store.add("деплой на сервер", "deploy на сервер")

    store2 = CorrectionsStore(path)
    assert len(store2.entries) == 1
    assert store2.entries[0].original == "деплой на сервер"
    assert store2.entries[0].corrected == "deploy на сервер"


def test_add_respects_max_entries(tmp_path):
    from localwhisper.corrections import CorrectionsStore

    path = tmp_path / "corrections.yaml"
    store = CorrectionsStore(path, max_entries=3)
    store.add("text 1", "corrected 1")
    store.add("text 2", "corrected 2")
    store.add("text 3", "corrected 3")
    store.add("text 4", "corrected 4")
    store.add("text 5", "corrected 5")

    assert len(store.entries) == 3
    assert store.entries[0].original == "text 3"
    assert store.entries[2].original == "text 5"


def test_add_deduplicates(tmp_path):
    from localwhisper.corrections import CorrectionsStore

    path = tmp_path / "corrections.yaml"
    store = CorrectionsStore(path)
    store.add("деплой на сервер", "deploy на сервер")
    store.add("другой текст", "other text")
    store.add("деплой на сервер", "deploy на сервер")

    assert len(store.entries) == 2
    assert store.entries[1].original == "деплой на сервер"


def test_get_recent(tmp_path):
    from localwhisper.corrections import CorrectionsStore

    path = tmp_path / "corrections.yaml"
    store = CorrectionsStore(path)
    store.add("text 1", "corrected 1")
    store.add("text 2", "corrected 2")
    store.add("text 3", "corrected 3")

    recent = store.get_recent(2)
    assert len(recent) == 2
    assert recent[0].original == "text 2"
    assert recent[1].original == "text 3"


def test_russian_text_roundtrip(tmp_path):
    from localwhisper.corrections import CorrectionsStore

    path = tmp_path / "corrections.yaml"
    store = CorrectionsStore(path)
    store.add("кубернетис кластер готов", "Kubernetes cluster готов")

    store2 = CorrectionsStore(path)
    assert store2.entries[0].original == "кубернетис кластер готов"
    assert store2.entries[0].corrected == "Kubernetes cluster готов"


def test_load_existing_file(tmp_path):
    from localwhisper.corrections import CorrectionsStore

    path = tmp_path / "corrections.yaml"
    data = [
        {
            "timestamp": "2026-03-30T12:00:00+00:00",
            "original": "test input",
            "corrected": "test output",
        }
    ]
    path.write_text(yaml.dump(data, allow_unicode=True))

    store = CorrectionsStore(path)
    assert len(store.entries) == 1
    assert store.entries[0].original == "test input"
    assert store.entries[0].corrected == "test output"


def test_get_relevant_returns_most_similar(tmp_path):
    from localwhisper.corrections import CorrectionsStore

    path = tmp_path / "corrections.yaml"
    store = CorrectionsStore(path)
    store.add("деплой на сервер", "deploy на сервер")
    store.add("купить молоко в магазине", "купить молоко в магазине")
    store.add("деплой на кубернетис кластер", "deploy на Kubernetes cluster")
    store.add("погода сегодня хорошая", "погода сегодня хорошая")

    relevant = store.get_relevant("деплой на стейджинг сервер", n=2)
    assert len(relevant) == 2
    originals = [e.original for e in relevant]
    assert "деплой на сервер" in originals
    assert "деплой на кубернетис кластер" in originals


def test_get_relevant_empty_store(tmp_path):
    from localwhisper.corrections import CorrectionsStore

    path = tmp_path / "corrections.yaml"
    store = CorrectionsStore(path)
    assert store.get_relevant("any text") == []


def test_get_relevant_limit(tmp_path):
    from localwhisper.corrections import CorrectionsStore

    path = tmp_path / "corrections.yaml"
    store = CorrectionsStore(path)
    for i in range(10):
        store.add(f"text {i}", f"corrected {i}")

    result = store.get_relevant("text 5", n=3)
    assert len(result) == 3
