"""Minimal GitHub issues client for scraper health (REST API via httpx).

`make_tracker()` returns a real client when GITHUB_TOKEN and
GITHUB_REPOSITORY are set, else a LoggingTracker that only logs the intended
actions (local dev). Tests use their own fake implementing IssueTracker.
"""
from __future__ import annotations

import logging
from typing import Protocol

import httpx
from decouple import config

logger = logging.getLogger(__name__)

API = "https://api.github.com"


class IssueTracker(Protocol):
    repo: str | None

    def open_issue(self, title: str, body: str, labels: list[str]) -> int | None:
        """Create an issue; returns its number (None when not really created)."""
        ...

    def comment(self, number: int, body: str) -> None: ...

    def update_issue(self, number: int, title: str, labels: list[str]) -> None:
        """Retitle and replace the labels."""
        ...

    def close_issue(self, number: int) -> None: ...

    def is_open(self, number: int) -> bool: ...


class GitHubTracker:
    def __init__(self, token: str, repo: str, client: httpx.Client | None = None):
        self.repo = repo
        self._client = client or httpx.Client(
            base_url=API,
            timeout=30,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    def _issues(self, suffix: str = "") -> str:
        return f"/repos/{self.repo}/issues{suffix}"

    def open_issue(self, title: str, body: str, labels: list[str]) -> int | None:
        r = self._client.post(self._issues(), json={"title": title, "body": body, "labels": labels})
        r.raise_for_status()
        return r.json()["number"]

    def comment(self, number: int, body: str) -> None:
        self._client.post(self._issues(f"/{number}/comments"), json={"body": body}).raise_for_status()

    def update_issue(self, number: int, title: str, labels: list[str]) -> None:
        self._client.patch(
            self._issues(f"/{number}"), json={"title": title, "labels": labels}
        ).raise_for_status()

    def close_issue(self, number: int) -> None:
        self._client.patch(
            self._issues(f"/{number}"), json={"state": "closed", "state_reason": "completed"}
        ).raise_for_status()

    def is_open(self, number: int) -> bool:
        r = self._client.get(self._issues(f"/{number}"))
        r.raise_for_status()
        return r.json().get("state") == "open"


class LoggingTracker:
    """Stand-in when GitHub isn't configured: logs what it would do."""
    repo: str | None = None

    def open_issue(self, title: str, body: str, labels: list[str]) -> int | None:
        logger.warning("[github disabled] would open issue %r labels=%s\n%s", title, labels, body)
        return None

    def comment(self, number: int, body: str) -> None:
        logger.warning("[github disabled] would comment on #%s:\n%s", number, body)

    def update_issue(self, number: int, title: str, labels: list[str]) -> None:
        logger.warning("[github disabled] would retitle #%s to %r labels=%s", number, title, labels)

    def close_issue(self, number: int) -> None:
        logger.warning("[github disabled] would close #%s", number)

    def is_open(self, number: int) -> bool:
        return True


def make_tracker() -> IssueTracker:
    token = config("GITHUB_TOKEN", default="")
    repo = config("GITHUB_REPOSITORY", default="")
    if token and repo:
        return GitHubTracker(token, repo)
    return LoggingTracker()
