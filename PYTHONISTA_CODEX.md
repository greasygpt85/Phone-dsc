# Using GPT-5.1 Codex Max from Pythonista 3

The following example shows how to call OpenAI's Chat Completions API from Pythonista 3 on iOS using the **GPT-5.1 Codex Max** model. It is designed to be drop-in ready for the Python 3 runtime that ships with Pythonista 3.

## Setup
1. In Pythonista, create a new script (e.g., `codex_demo.py`).
2. Install the `requests` package if you do not already have it. The built-in `pip` utility in Pythonista can be used from the prompt:
   ```python
   import pip
   pip.main(["install", "requests"])
   ```
3. Set your OpenAI API key as an environment variable inside Pythonista before importing the script:
   ```python
   import os
   os.environ["OPENAI_API_KEY"] = "sk-..."
   ```
   Alternatively, replace `os.getenv("OPENAI_API_KEY")` in the script below with a hard-coded key (not recommended).

## Example script
Paste the following into `codex_demo.py`:

```python
import json
import os
import time
from typing import List

import requests

API_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-5.1-codex"


def chat(messages: List[dict], *, temperature: float = 0.2) -> str:
    """Send chat messages to GPT-5.1 Codex Max and return the text response."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set the OPENAI_API_KEY environment variable first.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
    }

    start = time.time()
    resp = requests.post(API_URL, headers=headers, data=json.dumps(payload), timeout=120)
    resp.raise_for_status()
    data = resp.json()

    choice = data["choices"][0]
    finish_reason = choice.get("finish_reason")
    if finish_reason == "length":
        print("Warning: response truncated (finish_reason=length)")

    latency = time.time() - start
    print(f"Latency: {latency:.2f}s")
    return choice["message"]["content"].strip()


if __name__ == "__main__":
    prompt = input("Prompt: ")
    response = chat([
        {"role": "system", "content": "You are a helpful coding assistant."},
        {"role": "user", "content": prompt},
    ])
    print("\n=== Response ===\n")
    print(response)
```

## Notes
- `requests` is used instead of `httpx` because it is bundled-friendly and works well on iOS.
- Timeouts are set to 120 seconds for long generations; adjust as needed.
- For single-turn completions, pass a list with just one user message.
- To preserve secrets, prefer setting `OPENAI_API_KEY` via environment variables or Pythonista keychain utilities rather than hard-coding.
