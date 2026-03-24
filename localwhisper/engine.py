from .events import EngineReady


class LocalWhisperEngine:
    def __init__(self, config: dict):
        self._config = config
