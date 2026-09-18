"""The one place that knows how to talk to a NIM.

Everything else says "here is a clip and a question" and gets a parsed answer back.
Ported from compliance_check.ipynb cell 5, with three additions: a shared client per
endpoint, a structured-output helper, and retries around transient HTTP errors.

Three details worth knowing:

1. Media is sent inline as base64 data URLs. Images go as `image_url` parts, the clip as
   a `video_url` part (the NIM samples video at 4 fps).
2. A JSON Schema passed via `guided_json` constrains generation, so the reply is always
   valid JSON with exactly our fields.
3. Reasoner models may emit `<think>...</think>`; we strip it before parsing.
"""

import base64
import json
import re
import time
from functools import lru_cache
from pathlib import Path

from openai import OpenAI

from . import config

_THINK_RE = re.compile(r"<think>.*?</think>", re.S)


@lru_cache(maxsize=4)
def _client(base_url: str, api_key: str) -> OpenAI:
    # Cached so all threads share one connection pool per endpoint.
    return OpenAI(base_url=base_url, api_key=api_key or "not-needed", timeout=180)


def video_client() -> OpenAI:
    return _client(config.NIM_BASE_URL, config.NIM_API_KEY)


def author_client() -> OpenAI:
    return _client(config.AUTHOR_BASE_URL, config.AUTHOR_API_KEY)


def to_data_url(path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(Path(path).read_bytes()).decode()


def extract_json(text: str) -> str:
    """The outermost {...} in a reply, tolerating ```json fences and chatter around it."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise json.JSONDecodeError("no JSON object in reply", text, 0)
    return text[start:end + 1]


def served_models(client: OpenAI) -> list[str]:
    return [m.id for m in client.models.list().data]


def ask(
    prompt: str,
    *,
    images=(),
    video=None,
    schema=None,
    model: str | None = None,
    client: OpenAI | None = None,
    max_tokens: int = 400,
    retries: int = 2,
    guided: bool = True,
):
    """Send text, optionally with images and one video. Returns a dict when `schema` is
    given, else the raw text.

    `guided=False` is for endpoints without `guided_json` (such as some hosted NIMs): the
    schema is then only used to decide that a JSON reply is expected, and the JSON object is
    pulled out of the reply text instead.
    """
    client = client or video_client()
    model = model or config.NIM_MODEL

    content = []
    if video is not None:
        content.append({"type": "video_url", "video_url": {"url": to_data_url(video, "video/mp4")}})
    for img in images:
        if img:
            content.append({"type": "image_url", "image_url": {"url": to_data_url(img, "image/png")}})
    content.append({"type": "text", "text": prompt})

    extra = {"guided_json": schema} if (schema and guided) else {}
    last_error = None

    for attempt in range(retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": content}],
                max_tokens=max_tokens,
                temperature=0.0,  # deterministic, so re-runs are comparable
                extra_body=extra,
            )
            text = _THINK_RE.sub("", resp.choices[0].message.content or "").strip()
            if not schema:
                return text
            return json.loads(text if guided else extract_json(text))
        except json.JSONDecodeError as exc:
            # The model answered, but not in our shape. Retrying sometimes fixes it.
            last_error = ValueError(f"Model did not return valid JSON: {text[:300]}")
        except Exception as exc:  # network, 5xx, timeout
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))

    raise last_error
