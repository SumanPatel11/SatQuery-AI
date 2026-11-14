"""Shared local Ollama HTTP client for SatQuery AI."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OllamaError(RuntimeError):
    """Raised when the local Ollama request fails."""


class OllamaClient:

    def __init__(self, base_url="http://localhost:11434", timeout=180):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def chat(self, model, messages, format_schema=None, temperature=0):
        payload = {
            "model": model,
            "stream": False,
            "messages": messages,
            "options": {"temperature": temperature},
        }

        if format_schema is not None:
            payload["format"] = format_schema

        body = json.dumps(payload).encode("utf-8")

        request = Request(
            f"{self.base_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))

        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise OllamaError(
                f"Ollama HTTP {exc.code}: {detail}"
            ) from exc

        except (URLError, TimeoutError) as exc:
            raise OllamaError(
                f"Cannot connect to Ollama or request timed out: {exc}"
            ) from exc

        except (json.JSONDecodeError, KeyError) as exc:
            raise OllamaError(
                "Invalid response received from Ollama."
            ) from exc

        message = result.get("message")

        if not isinstance(message, dict):
            raise OllamaError("Ollama response has no valid message.")

        content = message.get("content")

        if not isinstance(content, str) or not content.strip():
            raise OllamaError("Ollama returned empty content.")

        return content.strip()
