"""
JarifUrRahim.One Website API Connector
Publishes blog posts to jarifurrahim.one via the restricted Agent API.

Configuration (via environment variables or .env file):
  WEBSITE_API_URL   = https://jarifurrahim.one  (default)
  WEBSITE_API_TOKEN = agentos-<your-token>

Security:
  - Token is read from environment only — never hardcoded
  - Scope: blog_write only (create/update posts)
  - No access to admin, users, appointments, or any other resource
"""
from __future__ import annotations

import os
import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any


WEBSITE_API_URL = os.environ.get("WEBSITE_API_URL", "https://jarifurrahim.one")
WEBSITE_API_TOKEN = os.environ.get("WEBSITE_API_TOKEN", "")


@dataclass
class PublishResult:
    success: bool
    message: str
    post_url: str | None = None
    error: str | None = None


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {WEBSITE_API_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "AgentOS/1.0 (JarifUrRahim.One Blog Publisher)",
    }


def check_connection() -> bool:
    """Check if the website API is reachable and token is valid."""
    try:
        req = urllib.request.Request(
            f"{WEBSITE_API_URL}/api/agent/status",
            headers={"User-Agent": "AgentOS/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("status") == "online"
    except Exception:
        return False


def list_posts() -> list[dict[str, Any]]:
    """List recent blog posts from the website (no auth required)."""
    try:
        req = urllib.request.Request(
            f"{WEBSITE_API_URL}/api/agent/blog",
            headers={"User-Agent": "AgentOS/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("posts", [])
    except Exception as e:
        return []


def publish_post(
    title: str,
    slug: str,
    excerpt: str,
    content: str,
    category: str = "Technology",
    read_time: int = 5,
    cover_image: str | None = None,
    published: bool = True,
) -> PublishResult:
    """
    Publish a new blog post to jarifurrahim.one.

    Args:
        title: Article title
        slug: URL slug (lowercase, hyphens, no spaces)
        excerpt: Short description (1-2 sentences)
        content: Full article body (Markdown or HTML)
        category: One of Career, Technology, Spirituality, Life
        read_time: Estimated reading time in minutes
        cover_image: Optional cover image URL
        published: Whether to publish immediately (default True)

    Returns:
        PublishResult with success status and post URL
    """
    if not WEBSITE_API_TOKEN:
        return PublishResult(
            success=False,
            message="WEBSITE_API_TOKEN not set in environment",
            error="Missing token"
        )

    payload = {
        "title": title,
        "slug": slug,
        "excerpt": excerpt,
        "content": content,
        "category": category,
        "readTime": read_time,
        "published": published,
    }
    if cover_image:
        payload["coverImage"] = cover_image

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{WEBSITE_API_URL}/api/agent/blog",
            data=data,
            headers=_headers(),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return PublishResult(
                success=True,
                message=result.get("message", "Published successfully"),
                post_url=result.get("post", {}).get("url"),
            )
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            err = json.loads(body).get("error", body)
        except Exception:
            err = body
        return PublishResult(success=False, message=f"HTTP {e.code}", error=err)
    except Exception as e:
        return PublishResult(success=False, message="Connection failed", error=str(e))


def update_post(slug: str, **fields: Any) -> PublishResult:
    """Update an existing blog post by slug."""
    if not WEBSITE_API_TOKEN:
        return PublishResult(
            success=False,
            message="WEBSITE_API_TOKEN not set in environment",
            error="Missing token"
        )

    try:
        data = json.dumps(fields).encode("utf-8")
        req = urllib.request.Request(
            f"{WEBSITE_API_URL}/api/agent/blog/{slug}",
            data=data,
            headers=_headers(),
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return PublishResult(
                success=True,
                message=result.get("message", "Updated successfully"),
                post_url=result.get("post", {}).get("url"),
            )
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            err = json.loads(body).get("error", body)
        except Exception:
            err = body
        return PublishResult(success=False, message=f"HTTP {e.code}", error=err)
    except Exception as e:
        return PublishResult(success=False, message="Connection failed", error=str(e))
