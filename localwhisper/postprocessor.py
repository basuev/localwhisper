import json
import logging

import requests

from localwhisper import oauth

log = logging.getLogger(__name__)


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
            f"You are a post-processor for speech-to-text. "
            f"The input is a dictated message.\n\n"
            f"Rules:\n"
            f"1. Fix punctuation and capitalization.\n"
            f"2. Remove false starts, self-corrections, and word/phrase repetitions. "
            f"Keep the final version of each rephrased segment.\n"
            f"3. Translate the result into {self.translate_to}.\n\n"
            f"Output only the translated text, nothing else."
        )

    def switch(self, backend: str, model: str):
        self.backend = backend
        if backend == "openai":
            self.openai_model = model
        else:
            self.ollama_model = model

    def process(self, text: str, cancel_check=None) -> str:
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
            log.exception("ollama postprocess failed")
            return text

    def _process_openai(self, text: str) -> str:
        try:
            token = oauth.get_valid_token()
            if not token:
                log.error(
                    "OpenAI post-processing failed: "
                    "not logged in (use Login in the menu)"
                )
                return text

            headers = {"Authorization": f"Bearer {token}"}
            account_id = oauth.get_account_id()
            if account_id:
                headers["ChatGPT-Account-Id"] = account_id

            resp = requests.post(
                "https://chatgpt.com/backend-api/codex/responses",
                headers=headers,
                json={
                    "model": self.openai_model,
                    "instructions": self._build_prompt(),
                    "input": [{"role": "user", "content": text}],
                    "store": False,
                    "stream": True,
                },
                timeout=60,
                stream=True,
            )
            if not resp.ok:
                body = (
                    resp.text[:500]
                    if not resp.headers.get("transfer-encoding")
                    else resp.content[:500].decode(errors="replace")
                )
                log.error(
                    "OpenAI post-processing failed (HTTP %d): %s",
                    resp.status_code,
                    body,
                )
            resp.raise_for_status()
            return self._parse_sse_response(resp, text)
        except Exception:
            log.exception("OpenAI post-processing failed")
            return text

    @staticmethod
    def _parse_sse_response(resp, fallback: str) -> str:
        result = ""
        for raw_line in resp.iter_lines():
            line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
            if not line or not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                break
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "response.output_text.delta":
                result += event.get("delta", "")
            elif event.get("type") in ("response.completed", "response.done"):
                response_data = event.get("response", {})
                for item in response_data.get("output", []):
                    if item.get("type") == "message":
                        for content in item.get("content", []):
                            if content.get("type") == "output_text":
                                result = content.get("text", "").strip()
                                break
                        break
        return result.strip() if result.strip() else fallback
