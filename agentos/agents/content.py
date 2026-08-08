"""Content Agent: drafts, publishing and the newsletter."""

from __future__ import annotations

from typing import Any

from agentos.agents.base import Agent, register_agent
from agentos.agents.workspace import listdir, read, resolve, slugify, today, write
from agentos.core.actions import ActionResult, ExecutionContext, registry
from agentos.core.permissions import RiskLevel
from agentos.connectors import website_api

AGENT = register_agent(
    Agent(
        name="content",
        title="Content Agent",
        mission="Writes drafts, publishes articles and assembles the newsletter.",
        keywords=("article", "post", "draft", "publish", "newsletter", "blog", "content"),
    )
)


@registry.register(
    "content.list",
    agent=AGENT.name,
    description="List drafts and published articles.",
    risk=RiskLevel.READ,
)
def list_content(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    return ActionResult(
        "Content inventory.",
        data={
            "drafts": listdir(ctx.workspace, "content/drafts"),
            "published": listdir(ctx.workspace, "content/published"),
        },
    )


@registry.register(
    "content.create_draft",
    agent=AGENT.name,
    description="Write a new draft article in the remembered house style.",
    risk=RiskLevel.LOW,
    required_params=("title",),
)
def create_draft(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    title = str(params["title"])
    tone = ctx.memory.recall("style", "tone", "clear and direct")
    body = params.get("body") or f"# {title}\n\n_Draft written in a {tone} tone._\n"
    relative = write(ctx.workspace, f"content/drafts/{slugify(title)}.md", str(body))
    return ActionResult(f"Draft '{title}' created.", files_modified=[relative])


@registry.register(
    "content.publish",
    agent=AGENT.name,
    description="Publish a draft article. Without a title the oldest draft is published.",
    risk=RiskLevel.LOW,
)
def publish(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    title = params.get("title")
    if title is None:
        drafts = listdir(ctx.workspace, "content/drafts")
        if not drafts:
            return ActionResult("There are no drafts to publish.")
        title = drafts[0].removeprefix("content/drafts/").removesuffix(".md")
    slug = slugify(str(title))
    draft = resolve(ctx.workspace, f"content/drafts/{slug}.md")
    if not draft.exists():
        return ActionResult(f"No draft named '{title}' to publish.")
    body = draft.read_text(encoding="utf-8")
    relative = write(
        ctx.workspace, f"content/published/{slug}.md", f"<!-- published: {today()} -->\n{body}"
    )
    draft.unlink()
    return ActionResult(
        f"Published '{title}'.",
        files_modified=[relative, f"content/drafts/{slug}.md"],
    )


@registry.register(
    "content.generate_newsletter",
    agent=AGENT.name,
    description="Assemble a newsletter from recently published articles.",
    risk=RiskLevel.LOW,
)
def generate_newsletter(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    published = listdir(ctx.workspace, "content/published")
    brand = ctx.memory.recall("brand", "name", "Our newsletter")
    lines = [f"# {brand} — {today()}", ""]
    for relative in published[-5:]:
        first_line = read(ctx.workspace, relative).splitlines()
        headline = next(
            (line.lstrip("# ") for line in first_line if line.startswith("#")), relative
        )
        lines.append(f"- {headline}")
    written = write(ctx.workspace, f"newsletters/{today()}.md", "\n".join(lines) + "\n")
    return ActionResult(
        f"Newsletter drafted from {len(published)} article(s).", files_modified=[written]
    )


@registry.register(
    "content.publish_to_website",
    agent=AGENT.name,
    description="Publish a draft article directly to jarifurrahim.one via the Agent API.",
    risk=RiskLevel.LOW,
    required_params=("title", "slug", "excerpt", "content"),
)
def publish_to_website(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    """
    Publish a blog post to jarifurrahim.one.
    Requires WEBSITE_API_TOKEN in environment (.env file).
    """
    title = str(params["title"])
    slug = str(params["slug"])
    excerpt = str(params["excerpt"])
    content = str(params["content"])
    category = str(params.get("category", "Technology"))
    read_time = int(params.get("read_time", 5))
    cover_image = params.get("cover_image")

    result = website_api.publish_post(
        title=title,
        slug=slug,
        excerpt=excerpt,
        content=content,
        category=category,
        read_time=read_time,
        cover_image=cover_image,
    )

    if result.success:
        return ActionResult(
            f"Published '{title}' to jarifurrahim.one. URL: {result.post_url}",
            data={"url": result.post_url, "slug": slug},
        )
    return ActionResult(
        f"Failed to publish '{title}': {result.error}",
        data={"error": result.error},
    )


@registry.register(
    "content.check_website_connection",
    agent=AGENT.name,
    description="Check if the website API is reachable and the token is valid.",
    risk=RiskLevel.READ,
)
def check_website_connection(ctx: ExecutionContext, params: dict[str, Any]) -> ActionResult:
    """Verify the website API connection is working."""
    online = website_api.check_connection()
    if online:
        posts = website_api.list_posts()
        return ActionResult(
            f"Website API is online. {len(posts)} recent post(s) found.",
            data={"online": True, "recent_posts": len(posts)},
        )
    return ActionResult(
        "Website API is unreachable. Check WEBSITE_API_URL and WEBSITE_API_TOKEN in .env",
        data={"online": False},
    )
