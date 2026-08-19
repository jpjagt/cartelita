from __future__ import annotations
import datetime as dt
from dataclasses import dataclass, field


@dataclass
class RawImage:
    """One downloaded image of a captured post."""
    url: str  # source CDN URL
    content_type: str
    data: bytes


@dataclass
class CapturedPost:
    """One Instagram post as captured from the timeline XHR, before download."""
    shortcode: str
    handle: str
    caption: str | None
    posted_at: dt.datetime | None  # tz-aware when present
    image_urls: list[str]  # ordered as posted
    # Filled once each image is downloaded; each image's url matches an entry
    # of image_urls. Empty until download runs.
    images: list[RawImage] = field(default_factory=list)
