import requests


class PostProcessor:
    def __init__(self, config: dict):
        self.model = config["ollama_model"]
        self.url = config["ollama_url"]
        self.prompt = config["postprocess_prompt"]

    def process(self, text: str) -> str:
        if not text:
            return text

        try:
            resp = requests.post(
                f"{self.url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self.prompt},
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
            # If Ollama is unavailable, return raw Whisper output
            return text
