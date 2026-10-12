"""Small HTTP helper shared by the ECW CI smoke workflow's scripts."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

# The default urllib User-Agent ("Python-urllib/x.y") is blocked by the WAF
# in front of the dev/staging backends, so every request needs a UA that
# doesn't match that bot signature.
USER_AGENT = "ecw-ci-smoke-script"


def request_json(
    url: str,
    api_key: str,
    *,
    method: str = "GET",
    params: dict | None = None,
    body: dict | None = None,
    timeout: float = 10,
) -> dict:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    headers = {"X-API-Key": api_key, "User-Agent": USER_AGENT}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def request_bytes(url: str, api_key: str, *, timeout: float = 30) -> bytes:
    request = urllib.request.Request(
        url, headers={"X-API-Key": api_key, "User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def write_github_output(name: str, value: str) -> None:
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output_file:
        output_file.write(f"{name}={value}\n")


def write_github_env(name: str, value: str) -> None:
    with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as env_file:
        env_file.write(f"{name}={value}\n")
