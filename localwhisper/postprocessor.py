import requests

from localwhisper import oauth


class PostProcessor:
    def __init__(self, config: dict):
        self.backend = config.get("postprocessor", "ollama")
        self.prompt = config["postprocess_prompt"]
        self.translate_to = config.get("translate_to")

        self.ollama_model = config["ollama_model"]
        self.ollama_url = config["ollama_url"]

        self.openai_model = config.get("openai_model", "gpt-5.4")

    def set_translate_to(self, language: str | None):
        self.translate_to = language

    def _build_prompt(self) -> str:
        if not self.translate_to:
            return self.prompt
        return (
            f"{self.prompt}\n\n"
            f"After all corrections, translate the entire result into {self.translate_to}. "
            f"Output only the translated text."
        )

    def switch(self, backend: str, model: str):
        self.backend = backend
        if backend == "openai":
            self.openai_model = model
        else:
            self.ollama_model = model

    def process(self, text: str) -> str:
        if not text:
            return text

        if self.backend == "openai":
            return self._process_openai(text)
        return self._process_ollama(text)

    def _process_ollama(self, text: str) -> str:
        try:
            resp = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.ollama_model,
                    "messages": [
                        {"role": "system", "content": self._build_prompt()},
                        {"role": "user", "content": text},
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0,
                    },
                },
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json().get("message", {}).get("content", "").strip()
            return result if result else text
        except Exception:
            return text

    def _process_openai(self, text: str) -> str:
        try:
            token = oauth.get_valid_token()
            if not token:
                return self._process_ollama(text)

            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "model": self.openai_model,
                    "messages": [
                        {"role": "system", "content": self._build_prompt()},
                        {"role": "user", "content": text},
                    ],
                    "temperature": 0,
                },
                timeout=30,
            )
            resp.raise_for_status()
            result = (
                resp.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            return result if result else text
        except Exception:
            return text
