"""Personal Knowledge Bank — MCP server.

Exposes a local folder of Markdown notes to an AI assistant through MCP,
using FastMCP over Streamable HTTP. The server offers read tools, workflow
prompts, resource access, and two constrained write tools. Every file access
is sandboxed to the knowledge-bank folder.
"""

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
import re
from typing import Literal
from urllib.parse import unquote

from fastmcp import FastMCP
import yaml

# Root of the knowledge bank — the hard sandbox boundary.
# Resolve once so every later check compares against an absolute, real path.
KB_ROOT = (Path(__file__).parent / "developer-knowledge-bank").resolve()
HTTP_HOST = "127.0.0.1"
HTTP_PORT = 8000
RESERVED_METADATA_FILES = {"index.md", "log.md"}
LINK_PATTERN = re.compile(r"\[[^\]]+\]\((?![a-z]+:|#)([^)]+\.md(?:#[^)]+)?)\)", re.IGNORECASE)
PLACEHOLDER_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bTODO\b",
        r"\bTBD\b",
        r"\bFIXME\b",
        r"YYYY-WW",
        r"\bActie\s+\d+\b",
        r"\bPunt\s+\d+\b",
        r"\btag\d+\b",
        r"\bTitel\b",
        r"^-\s*$",
    )
]

mcp = FastMCP(
    "developer-knowledge-bank",
    instructions=(
        "Use the search and metadata tools before reading many files. "
        "Read tools are sandboxed to Markdown files inside the knowledge bank. "
        "Use append_to_log, capture_inbox_note or template creation tools for writes; "
        "do not expect arbitrary file writes."
    ),
)


# --- internal logic (plain functions, easy to test) -----------------------

def _safe_path(relative_path: str) -> Path:
    """Resolve a requested path and ensure it stays inside KB_ROOT.

    This is the path-traversal guard: a request such as
    ``../../etc/passwd`` resolves to a path outside the knowledge bank and
    is rejected before any file is opened.
    """
    candidate = (KB_ROOT / relative_path).resolve()
    if not candidate.is_relative_to(KB_ROOT):
        raise ValueError("Access outside the knowledge bank is not allowed.")
    return candidate


def _safe_markdown_path(relative_path: str) -> Path:
    path = _safe_path(relative_path)
    if path.suffix != ".md":
        raise ValueError("Only Markdown files inside the knowledge bank are allowed.")
    return path


def _relative(path: Path) -> str:
    return path.relative_to(KB_ROOT).as_posix()


def _split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}, text
    return _parse_frontmatter(parts[1]), parts[2]


def _parse_frontmatter(frontmatter: str) -> dict:
    try:
        metadata = yaml.safe_load(frontmatter) or {}
    except yaml.YAMLError as error:
        return {"__frontmatter_error": str(error)}
    if not isinstance(metadata, dict):
        return {"__frontmatter_error": "Frontmatter must be a YAML mapping."}
    return metadata


def _format_metadata_value(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if value is None:
        return ""
    return str(value)


def _normalize_tags(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _parse_timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _metadata_for(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    metadata, body = _split_frontmatter(text)
    title = metadata.get("title") or _first_heading(body) or path.stem.replace("-", " ").title()
    return {
        "file": _relative(path),
        "folder": path.parent.relative_to(KB_ROOT).as_posix() if path.parent != KB_ROOT else ".",
        "title": _format_metadata_value(title),
        "type": _format_metadata_value(metadata.get("type", "")),
        "description": _format_metadata_value(metadata.get("description", "")),
        "tags": _normalize_tags(metadata.get("tags", [])),
        "timestamp": _format_metadata_value(metadata.get("timestamp", "")),
    }


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _list() -> list[str]:
    return [_relative(path) for path in sorted(KB_ROOT.rglob("*.md"))]


def _read(relative_path: str) -> str:
    path = _safe_markdown_path(relative_path)
    if not path.is_file():
        raise ValueError("File not found in the knowledge bank.")
    return path.read_text(encoding="utf-8")


def _search(query: str) -> list[dict]:
    needle = query.lower()
    results: list[dict] = []
    for path in sorted(KB_ROOT.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        if needle in text.lower():
            snippet = next(
                (line.strip() for line in text.splitlines() if needle in line.lower()),
                "",
            )
            results.append({"file": _relative(path), "snippet": snippet})
    return results


def _knowledge_map() -> dict:
    folders: dict[str, list[dict]] = {}
    for path in sorted(KB_ROOT.rglob("*.md")):
        item = _metadata_for(path)
        folders.setdefault(item["folder"], []).append(item)
    return folders


def _list_tags() -> list[str]:
    tags: set[str] = set()
    for path in KB_ROOT.rglob("*.md"):
        for tag in _metadata_for(path).get("tags", []):
            tags.add(tag)
    return sorted(tags)


def _list_types() -> list[str]:
    types: set[str] = set()
    for path in KB_ROOT.rglob("*.md"):
        note_type = _metadata_for(path).get("type")
        if note_type:
            types.add(note_type)
    return sorted(types)


def _search_metadata(
    query: str = "",
    tag: str = "",
    note_type: str = "",
    folder: str = "",
    limit: int = 20,
) -> list[dict]:
    query_lower = query.lower().strip()
    tag_lower = tag.lower().strip()
    type_lower = note_type.lower().strip()
    folder_filter = folder.strip().strip("/")
    matches: list[dict] = []
    for path in sorted(KB_ROOT.rglob("*.md")):
        item = _metadata_for(path)
        searchable = " ".join(
            [
                item["file"],
                item["title"],
                item["type"],
                item["description"],
                " ".join(item["tags"]),
            ]
        ).lower()
        if query_lower and query_lower not in searchable:
            continue
        if tag_lower and tag_lower not in [existing.lower() for existing in item["tags"]]:
            continue
        if type_lower and item["type"].lower() != type_lower:
            continue
        if folder_filter and not item["file"].startswith(folder_filter + "/"):
            continue
        matches.append(item)
        if len(matches) >= limit:
            break
    return matches


def _resolve_markdown_link(source_path: Path, link_target: str) -> Path:
    clean_target = unquote(link_target.strip()).split("#", 1)[0]
    if clean_target.startswith("/"):
        return (KB_ROOT / clean_target.lstrip("/")).resolve()
    return (source_path.parent / clean_target).resolve()


def _extract_links(path: Path) -> list[dict]:
    links: list[dict] = []
    text = path.read_text(encoding="utf-8")
    for link_target in LINK_PATTERN.findall(text):
        linked_path = _resolve_markdown_link(path, link_target)
        exists = linked_path.is_relative_to(KB_ROOT) and linked_path.is_file()
        links.append(
            {
                "source": _relative(path),
                "target": _relative(linked_path) if exists else link_target,
                "raw_target": link_target,
                "exists": exists,
            }
        )
    return links


def _list_outgoing_links(relative_path: str) -> list[dict]:
    path = _safe_markdown_path(relative_path)
    if not path.is_file():
        raise ValueError("File not found in the knowledge bank.")
    return _extract_links(path)


def _find_backlinks(target_path: str) -> list[dict]:
    target = _safe_markdown_path(target_path)
    if not target.is_file():
        raise ValueError("File not found in the knowledge bank.")
    backlinks: list[dict] = []
    for path in sorted(KB_ROOT.rglob("*.md")):
        if path == target:
            continue
        for link in _extract_links(path):
            if link["exists"] and link["target"] == _relative(target):
                backlinks.append({"source": _relative(path), "raw_target": link["raw_target"]})
    return backlinks


def _find_orphan_notes() -> list[dict]:
    incoming_counts = {file: 0 for file in _list()}
    for path in sorted(KB_ROOT.rglob("*.md")):
        for link in _extract_links(path):
            if link["exists"] and link["target"] in incoming_counts:
                incoming_counts[link["target"]] += 1
    reserved = {"index.md", "log.md"}
    return [
        _metadata_for(KB_ROOT / file)
        for file, count in sorted(incoming_counts.items())
        if count == 0 and Path(file).name not in reserved
    ]


def _find_related_notes(relative_path: str, limit: int = 10) -> dict:
    path = _safe_markdown_path(relative_path)
    if not path.is_file():
        raise ValueError("File not found in the knowledge bank.")
    source_metadata = _metadata_for(path)
    source_tags = {tag.lower() for tag in source_metadata["tags"]}
    outgoing = [link for link in _extract_links(path) if link["exists"]]
    backlinks = _find_backlinks(relative_path)
    related: dict[str, dict] = {}

    for link in outgoing:
        related[link["target"]] = {"file": link["target"], "reasons": ["outgoing_link"]}
    for backlink in backlinks:
        item = related.setdefault(backlink["source"], {"file": backlink["source"], "reasons": []})
        item["reasons"].append("backlink")
    if source_tags:
        for candidate in sorted(KB_ROOT.rglob("*.md")):
            candidate_file = _relative(candidate)
            if candidate == path or candidate_file in related:
                continue
            candidate_metadata = _metadata_for(candidate)
            shared_tags = sorted(source_tags & {tag.lower() for tag in candidate_metadata["tags"]})
            if shared_tags:
                related[candidate_file] = {
                    "file": candidate_file,
                    "reasons": ["shared_tags"],
                    "shared_tags": shared_tags,
                }
            if len(related) >= limit:
                break
    return {"file": _relative(path), "related": list(related.values())[:limit]}


def _validate_knowledge_bank() -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    titles: dict[str, str] = {}
    for path in sorted(KB_ROOT.rglob("*.md")):
        relative_path = _relative(path)
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            errors.append(f"{relative_path}: empty file")
            continue

        metadata, _body = _split_frontmatter(text)
        if path.name not in RESERVED_METADATA_FILES:
            if not text.startswith("---\n"):
                errors.append(f"{relative_path}: missing YAML frontmatter")
            elif metadata.get("__frontmatter_error"):
                errors.append(f"{relative_path}: invalid frontmatter: {metadata['__frontmatter_error']}")
            elif not metadata:
                errors.append(f"{relative_path}: invalid or empty frontmatter block")
            for field in ("type", "title", "description", "timestamp"):
                if not metadata.get(field):
                    errors.append(f"{relative_path}: missing non-empty {field} field")
            if metadata.get("timestamp") and not _parse_timestamp(metadata["timestamp"]):
                errors.append(f"{relative_path}: timestamp is not a valid ISO date/time")
            tags = _normalize_tags(metadata.get("tags"))
            if not tags:
                errors.append(f"{relative_path}: missing non-empty tags list")

        title = metadata.get("title")
        if title:
            if title in titles:
                warnings.append(f"{relative_path}: duplicate title also used by {titles[title]}")
            titles[title] = relative_path

        for link_target in LINK_PATTERN.findall(text):
            linked_path = _resolve_markdown_link(path, link_target)
            if not linked_path.is_relative_to(KB_ROOT) or not linked_path.is_file():
                errors.append(f"{relative_path}: broken Markdown link to {link_target}")

    return {"valid": not errors, "errors": errors, "warnings": warnings}


def _find_stale_notes(days_old: int = 90, folder: str = "") -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_old)
    folder_filter = folder.strip().strip("/")
    stale_notes: list[dict] = []
    for path in sorted(KB_ROOT.rglob("*.md")):
        item = _metadata_for(path)
        if folder_filter and not item["file"].startswith(folder_filter + "/"):
            continue
        metadata, _body = _split_frontmatter(path.read_text(encoding="utf-8"))
        parsed = _parse_timestamp(metadata.get("timestamp"))
        if not parsed:
            continue
        if parsed < cutoff:
            item["age_days"] = (datetime.now(timezone.utc) - parsed).days
            stale_notes.append(item)
    stale_notes.sort(key=lambda note: note["timestamp"])
    return stale_notes


def _find_placeholder_text(folder: str = "", limit: int = 100) -> list[dict]:
    folder_filter = folder.strip().strip("/")
    findings: list[dict] = []
    for path in sorted(KB_ROOT.rglob("*.md")):
        relative_path = _relative(path)
        if folder_filter and not relative_path.startswith(folder_filter + "/"):
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if any(pattern.search(line) for pattern in PLACEHOLDER_PATTERNS):
                findings.append({"file": relative_path, "line": line_number, "text": line.strip()})
                if len(findings) >= limit:
                    return findings
    return findings


def _validate_index_coverage() -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    checked: list[str] = []
    for directory in sorted({path.parent for path in KB_ROOT.rglob("*.md")}):
        index_path = directory / "index.md"
        directory_label = directory.relative_to(KB_ROOT).as_posix() if directory != KB_ROOT else "."
        notes = [
            path
            for path in sorted(directory.glob("*.md"))
            if path.name not in {"index.md", "log.md", "README.md", "HOW_TO_USE.md", "inbox.md"}
        ]
        if not notes:
            continue
        if not index_path.is_file():
            errors.append(f"{directory_label}: missing index.md for {len(notes)} notes")
            continue
        checked.append(_relative(index_path))
        link_targets = {
            link["target"]
            for link in _extract_links(index_path)
            if link["exists"]
        }
        for note_path in notes:
            note_relative = _relative(note_path)
            if note_relative not in link_targets:
                errors.append(f"{_relative(index_path)}: missing link to {note_relative}")
    return {"valid": not errors, "errors": errors, "warnings": warnings, "checked_indexes": checked}


def _context_bundle(kind: Literal["project", "decision", "growth"]) -> dict:
    bundles = {
        "project": [
            "work/current-projects.md",
            "work/team-and-stakeholders.md",
            "work/ways-of-working.md",
            "work/tech-stack.md",
        ],
        "decision": [
            "decisions/technical-decisions.md",
            "work/ways-of-working.md",
            "learning/secure-coding.md",
            "templates/decision-template.md",
        ],
        "growth": [
            "goals/career-growth.md",
            "goals/skills-development.md",
            "learning/learning-plan.md",
            "decisions/career-decisions.md",
        ],
    }
    return {
        "kind": kind,
        "files": [{"file": file, "content": _read(file)} for file in bundles[kind]],
    }


def _learning_context(topic: str = "") -> dict:
    files = [
        "templates/learning-note-template.md",
        "learning/learning-plan.md",
        "learning/backend-development.md",
        "work/tech-stack.md",
    ]
    matching_notes = _search(topic)[:10] if topic.strip() else _search_metadata(folder="learning", limit=10)
    return {
        "topic": topic,
        "files": [{"file": file, "content": _read(file)} for file in files],
        "matching_notes": matching_notes,
    }


def _goal_alignment_context(proposal: str = "") -> dict:
    files = [
        "goals/career-growth.md",
        "goals/skills-development.md",
        "goals/work-life-balance.md",
        "goals/health-and-energy.md",
        "personal/values.md",
        "decisions/career-decisions.md",
        "learning/learning-plan.md",
        "routines/weekly-review.md",
    ]
    return {
        "proposal": proposal,
        "files": [{"file": file, "content": _read(file)} for file in files],
        "matching_notes": _search(proposal)[:10] if proposal.strip() else [],
    }


def _check_goal_alignment(proposal: str) -> dict:
    context = _goal_alignment_context(proposal)
    query_words = {word.lower() for word in re.findall(r"[a-zA-Z0-9-]{4,}", proposal)}
    signals: list[dict] = []
    for item in context["files"]:
        text = item["content"].lower()
        matches = sorted(word for word in query_words if word in text)
        if matches:
            signals.append({"file": item["file"], "matching_terms": matches[:10]})
    return {
        "proposal": proposal,
        "signals": signals,
        "context_files": [item["file"] for item in context["files"]],
        "matching_notes": context["matching_notes"],
    }


def _list_recent_notes(limit: int = 10, folder: str = "") -> list[dict]:
    folder_filter = folder.strip().strip("/")
    items: list[dict] = []
    for path in sorted(KB_ROOT.rglob("*.md")):
        metadata, _body = _split_frontmatter(path.read_text(encoding="utf-8"))
        item = _metadata_for(path)
        if folder_filter and not item["file"].startswith(folder_filter + "/"):
            continue
        parsed = _parse_timestamp(metadata.get("timestamp"))
        item["has_timestamp"] = parsed is not None
        item["sort_timestamp"] = parsed.isoformat() if parsed else ""
        items.append(item)
    items.sort(key=lambda item: (item["has_timestamp"], item["sort_timestamp"]), reverse=True)
    for item in items:
        item.pop("has_timestamp", None)
        item.pop("sort_timestamp", None)
    return items[:limit]


def _daily_briefing_context() -> dict:
    files = [
        "log.md",
        "work/current-projects.md",
        "goals/index.md",
        "routines/daily-routine.md",
        "decisions/index.md",
    ]
    return {"files": [{"file": file, "content": _read(file)} for file in files], "recent_notes": _list_recent_notes(5)}


def _weekly_review_context() -> dict:
    files = [
        "goals/index.md",
        "work/index.md",
        "decisions/index.md",
        "routines/weekly-review.md",
        "routines/daily-routine.md",
        "log.md",
    ]
    return {"files": [{"file": file, "content": _read(file)} for file in files], "recent_notes": _list_recent_notes(10)}


def _append_to_log(entry: str, heading: str = "MCP note") -> dict:
    log_path = _safe_markdown_path("log.md")
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n## {timestamp} - {heading}\n{entry.strip()}\n")
    return {"file": "log.md", "timestamp": timestamp, "heading": heading}


def _capture_inbox_note(entry: str, source: str = "MCP", tags: list[str] | None = None) -> dict:
    inbox_path = _safe_markdown_path("inbox.md")
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    if not inbox_path.exists():
        inbox_path.write_text(
            "---\n"
            "type: Inbox\n"
            "title: Inbox\n"
            "description: Quick raw captures waiting to be curated into OKF notes.\n"
            "tags: [inbox, capture]\n"
            f"timestamp: {timestamp}\n"
            "---\n\n"
            "# Inbox\n",
            encoding="utf-8",
        )
    tag_text = ", ".join(tags or [])
    tag_suffix = f"\nTags: {tag_text}" if tag_text else ""
    with inbox_path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n## {timestamp}\nSource: {source}{tag_suffix}\n\n{entry.strip()}\n")
    return {"file": "inbox.md", "timestamp": timestamp, "source": source, "tags": tags or []}


def _resolve_template(template: str) -> Path:
    template_name = template.strip()
    candidates = [template_name]
    if not template_name.endswith(".md"):
        candidates.extend([f"{template_name}.md", f"templates/{template_name}.md"])
    if not template_name.startswith("templates/"):
        candidates.append(f"templates/{template_name}")
    for candidate in candidates:
        path = _safe_path(candidate)
        if path.suffix != ".md":
            continue
        if path.is_file():
            return path
    raise ValueError("Template not found in the knowledge bank.")


def _render_template(template: str, title: str) -> tuple[Path, str]:
    template_path = _resolve_template(template)
    content = template_path.read_text(encoding="utf-8")
    content = re.sub(r"^# .*$", f"# {title}", content, count=1, flags=re.MULTILINE)
    if "# " not in content:
        content = f"# {title}\n\n{content}"
    return template_path, content


def _list_templates() -> list[dict]:
    return _search_metadata(tag="template", folder="templates", limit=100)


def _preview_note_from_template(template: str, title: str, target_path: str = "") -> dict:
    template_path, content = _render_template(template, title)
    if target_path:
        _safe_markdown_path(target_path)
    return {
        "template": _relative(template_path),
        "target_path": target_path,
        "content": content,
        "would_overwrite": bool(target_path and _safe_markdown_path(target_path).exists()),
    }


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "untitled"


def _create_note_from_template(
    template: str,
    target_path: str,
    title: str,
    overwrite: bool = False,
) -> dict:
    template_path, content = _render_template(template, title)
    target = _safe_markdown_path(target_path)
    if target.exists() and not overwrite:
        raise ValueError("Target note already exists. Set overwrite to true to replace it.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"file": _relative(target), "template": _relative(template_path), "overwritten": overwrite}


def _create_learning_note(topic: str, target_path: str = "", overwrite: bool = False) -> dict:
    target = target_path or f"learning/{_slugify(topic)}.md"
    return _create_note_from_template("learning-note-template", target, topic, overwrite)


def _create_project_note(project_name: str, target_path: str = "", overwrite: bool = False) -> dict:
    target = target_path or f"work/{_slugify(project_name)}.md"
    return _create_note_from_template("project-brief-template", target, project_name, overwrite)


def _create_decision_note(decision_title: str, target_path: str = "", overwrite: bool = False) -> dict:
    target = target_path or f"decisions/{_slugify(decision_title)}.md"
    return _create_note_from_template("decision-template", target, decision_title, overwrite)


def _read_tool_annotations(title: str) -> dict:
    return {
        "title": title,
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }


def _write_tool_annotations(title: str, destructive: bool = False) -> dict:
    return {
        "title": title,
        "readOnlyHint": False,
        "destructiveHint": destructive,
        "idempotentHint": False,
        "openWorldHint": False,
    }


# --- MCP surface (tools, resources and prompts) ---------------------------

@mcp.tool(
    description="List every Markdown file available in the sandboxed knowledge bank. Returns relative paths only.",
    annotations=_read_tool_annotations("List Knowledge Files"),
)
def list_knowledge_files() -> list[str]:
    """List all Markdown files available in the knowledge bank."""
    return _list()


@mcp.tool(
    description="Read one Markdown file by relative path. Rejects non-Markdown files and paths outside the knowledge bank.",
    annotations=_read_tool_annotations("Read Knowledge File"),
)
def read_knowledge_file(relative_path: str) -> str:
    """Read one Markdown file from the knowledge bank.

    Args:
        relative_path: Path relative to the knowledge-bank root,
            e.g. ``work/current-projects.md``.
    """
    return _read(relative_path)


@mcp.tool(
    description="Search note contents case-insensitively. Returns matching file paths with the first matching line as a snippet.",
    annotations=_read_tool_annotations("Search Knowledge Bank"),
)
def search_knowledge_bank(query: str) -> list[dict]:
    """Search titles, tags and content across the knowledge bank.

    Returns a list of ``{"file": ..., "snippet": ...}`` matches, where the
    snippet is the first line in the file that contains the query.
    """
    return _search(query)


@mcp.tool(
    description="Return a folder-by-folder map of Markdown notes with frontmatter metadata for orientation before deeper reads.",
    annotations=_read_tool_annotations("Get Knowledge Map"),
)
def get_knowledge_map() -> dict:
    """Return the Markdown knowledge bank grouped by folder with metadata."""
    return _knowledge_map()


@mcp.tool(
    description="List unique frontmatter tags used across Markdown notes. Use before metadata filtering by tag.",
    annotations=_read_tool_annotations("List Knowledge Tags"),
)
def list_knowledge_tags() -> list[str]:
    """List unique frontmatter tags used by Markdown files in the knowledge bank."""
    return _list_tags()


@mcp.tool(
    description="List unique frontmatter type values used across Markdown notes. Use before filtering by note_type.",
    annotations=_read_tool_annotations("List Knowledge Types"),
)
def list_knowledge_types() -> list[str]:
    """List unique frontmatter type values used by Markdown files in the knowledge bank."""
    return _list_types()


@mcp.tool(
    description="Search note paths and frontmatter without reading full contents. Supports query, tag, type, folder and limit filters.",
    annotations=_read_tool_annotations("Search Knowledge Metadata"),
)
def search_knowledge_metadata(
    query: str = "",
    tag: str = "",
    note_type: str = "",
    folder: str = "",
    limit: int = 20,
) -> list[dict]:
    """Search Markdown frontmatter and paths without reading full note contents.

    Args:
        query: Optional text to match against file path, title, type, description or tags.
        tag: Optional exact tag filter, case-insensitive.
        note_type: Optional exact frontmatter type filter, case-insensitive.
        folder: Optional folder filter such as business, goals, templates or learning.
        limit: Maximum number of metadata results to return.
    """
    return _search_metadata(query=query, tag=tag, note_type=note_type, folder=folder, limit=limit)


@mcp.tool(
    description="Validate OKF Markdown health: frontmatter, timestamps, tags, duplicate titles and local Markdown links.",
    annotations=_read_tool_annotations("Validate Knowledge Bank"),
)
def validate_knowledge_bank() -> dict:
    """Validate OKF Markdown structure, frontmatter, duplicate titles and local links."""
    return _validate_knowledge_bank()


@mcp.tool(
    description="Find notes whose frontmatter timestamp is older than days_old. Optionally restrict to one folder.",
    annotations=_read_tool_annotations("Find Stale Notes"),
)
def find_stale_notes(days_old: int = 90, folder: str = "") -> list[dict]:
    """Find notes whose frontmatter timestamp is older than a threshold.

    Args:
        days_old: Minimum age in days before a note is considered stale.
        folder: Optional folder filter such as business, goals or learning.
    """
    return _find_stale_notes(days_old, folder)


@mcp.tool(
    description="Find unfinished placeholders such as TODO, TBD, YYYY-WW, empty bullets and template residue. Returns file, line and text.",
    annotations=_read_tool_annotations("Find Placeholder Text"),
)
def find_placeholder_text(folder: str = "", limit: int = 100) -> list[dict]:
    """Find unfinished placeholder text such as TODO, TBD, YYYY-WW or empty bullets."""
    return _find_placeholder_text(folder, limit)


@mcp.tool(
    description="Check that each folder index.md links to the Markdown notes in that folder. Returns missing index/link errors.",
    annotations=_read_tool_annotations("Validate Index Coverage"),
)
def validate_index_coverage() -> dict:
    """Check that each folder index.md links to the Markdown notes in that folder."""
    return _validate_index_coverage()


@mcp.tool(
    description="List Markdown links from one note and whether each link resolves inside the knowledge bank.",
    annotations=_read_tool_annotations("List Outgoing Links"),
)
def list_outgoing_links(relative_path: str) -> list[dict]:
    """List Markdown links from one knowledge-bank note and whether each target exists."""
    return _list_outgoing_links(relative_path)


@mcp.tool(
    description="Find notes that link to a target Markdown file. Use to see where a concept is referenced.",
    annotations=_read_tool_annotations("Find Backlinks"),
)
def find_backlinks(target_path: str) -> list[dict]:
    """Find notes that link to a given Markdown file in the knowledge bank."""
    return _find_backlinks(target_path)


@mcp.tool(
    description="Find non-index Markdown notes with no incoming links. Useful for improving knowledge-bank navigation.",
    annotations=_read_tool_annotations("Find Orphan Notes"),
)
def find_orphan_notes() -> list[dict]:
    """Find Markdown notes that no other note links to, excluding index.md and log.md."""
    return _find_orphan_notes()


@mcp.tool(
    description="Find related notes by outgoing links, backlinks and shared tags. Returns reasons for each relation.",
    annotations=_read_tool_annotations("Find Related Notes"),
)
def find_related_notes(relative_path: str, limit: int = 10) -> dict:
    """Find notes related by outgoing links, backlinks or shared frontmatter tags."""
    return _find_related_notes(relative_path, limit)


@mcp.tool(
    description="Return the core notes for understanding the current project: tasks, team, ways of working and tech stack.",
    annotations=_read_tool_annotations("Prepare Project Context"),
)
def prepare_project_context() -> dict:
    """Return notes for understanding the current project, team and ways of working."""
    return _context_bundle("project")


@mcp.tool(
    description="Return technical-decision, ways-of-working, secure-coding and decision-template notes for reasoning about a technical choice.",
    annotations=_read_tool_annotations("Prepare Technical Decision Context"),
)
def prepare_technical_decision_context() -> dict:
    """Return notes used to reason about a technical decision."""
    return _context_bundle("decision")


@mcp.tool(
    description="Return career-growth, skills, learning-plan and career-decision notes for reflecting on professional growth.",
    annotations=_read_tool_annotations("Prepare Growth Context"),
)
def prepare_growth_context() -> dict:
    """Return notes used to reflect on career growth and skills development."""
    return _context_bundle("growth")


@mcp.tool(
    description="Return the learning-note template, learning plan, backend notes, tech stack and matching topic notes for studying a topic.",
    annotations=_read_tool_annotations("Prepare Learning Context"),
)
def prepare_learning_context(topic: str = "") -> dict:
    """Return template, plan, tech stack and matching notes for studying a topic."""
    return _learning_context(topic)


@mcp.tool(
    description="Return goals, values, decisions, learning and routine notes for checking whether a choice fits your goals.",
    annotations=_read_tool_annotations("Prepare Goal Alignment Context"),
)
def prepare_goal_alignment_context(proposal: str = "") -> dict:
    """Return goals, values, decisions and routine notes for checking goal fit."""
    return _goal_alignment_context(proposal)


@mcp.tool(
    description="Return lightweight evidence signals showing how a proposal overlaps with saved goals, decisions and routines.",
    annotations=_read_tool_annotations("Check Goal Alignment"),
)
def check_goal_alignment(proposal: str) -> dict:
    """Return evidence signals for how a proposal overlaps with saved goals and rules."""
    return _check_goal_alignment(proposal)


@mcp.tool(
    description="List notes ordered by frontmatter timestamp, newest first. Optionally restrict to one folder.",
    annotations=_read_tool_annotations("List Recent Notes"),
)
def list_recent_notes(limit: int = 10, folder: str = "") -> list[dict]:
    """List notes ordered by frontmatter timestamp, optionally filtered by folder."""
    return _list_recent_notes(limit, folder)


@mcp.tool(
    description="Return log, current project, goals, weekly routine, decisions and recent notes for a daily briefing.",
    annotations=_read_tool_annotations("Get Daily Briefing Context"),
)
def get_daily_briefing_context() -> dict:
    """Return log, current project, goals, routines and recent notes for a daily briefing."""
    return _daily_briefing_context()


@mcp.tool(
    description="Return goals, work, decisions, weekly review routine, daily routine, log and recent notes for a weekly review.",
    annotations=_read_tool_annotations("Get Weekly Review Context"),
)
def get_weekly_review_context() -> dict:
    """Return goals, work, decisions, routines, log and recent notes for a weekly review."""
    return _weekly_review_context()


@mcp.tool(
    description="Append a dated Markdown entry to log.md only. Does not edit arbitrary files.",
    annotations=_write_tool_annotations("Append To Log"),
)
def append_to_log(entry: str, heading: str = "MCP note") -> dict:
    """Append a dated entry to log.md without editing arbitrary files.

    Args:
        entry: Markdown content to append to the root knowledge-bank log.
        heading: Short heading for the log entry.
    """
    return _append_to_log(entry=entry, heading=heading)


@mcp.tool(
    description="Append a raw capture to inbox.md only, preserving it for later curation into structured OKF notes.",
    annotations=_write_tool_annotations("Capture Inbox Note"),
)
def capture_inbox_note(entry: str, source: str = "MCP", tags: list[str] | None = None) -> dict:
    """Append a raw capture to inbox.md for later curation into structured OKF notes.

    Args:
        entry: Raw Markdown capture text.
        source: Short source label, such as MCP, meeting, idea or training.
        tags: Optional lightweight tags for the capture.
    """
    return _capture_inbox_note(entry=entry, source=source, tags=tags)


@mcp.tool(
    description="Create a Markdown note inside the knowledge bank from an existing template. Refuses overwrite unless overwrite is true.",
    annotations=_write_tool_annotations("Create Note From Template"),
)
def create_note_from_template(
    template: str,
    target_path: str,
    title: str,
    overwrite: bool = False,
) -> dict:
    """Create a Markdown note inside the knowledge bank from an existing template.

    Args:
        template: Template path or name, such as templates/decision-template.md or decision-template.
        target_path: New Markdown path inside the knowledge bank.
        title: Replacement title for the first top-level Markdown heading.
        overwrite: Whether to replace an existing target note.
    """
    return _create_note_from_template(template, target_path, title, overwrite)


@mcp.tool(
    description="List Markdown templates available for safe note creation. Use before previewing or creating from a template.",
    annotations=_read_tool_annotations("List Templates"),
)
def list_templates() -> list[dict]:
    """List Markdown templates available for safe note creation."""
    return _list_templates()


@mcp.tool(
    description="Preview generated Markdown from a template without writing a file. Reports whether target_path would overwrite.",
    annotations=_read_tool_annotations("Preview Note From Template"),
)
def preview_note_from_template(template: str, title: str, target_path: str = "") -> dict:
    """Preview Markdown that would be created from a template without writing a file."""
    return _preview_note_from_template(template, title, target_path)


@mcp.tool(
    description="Create a learning note from the learning-note template, using a safe learning/{slug}.md path by default.",
    annotations=_write_tool_annotations("Create Learning Note"),
)
def create_learning_note(topic: str, target_path: str = "", overwrite: bool = False) -> dict:
    """Create a learning note from the learning-note template."""
    return _create_learning_note(topic, target_path, overwrite)


@mcp.tool(
    description="Create a project brief note from the project brief template, using work/{slug}.md by default.",
    annotations=_write_tool_annotations("Create Project Note"),
)
def create_project_note(project_name: str, target_path: str = "", overwrite: bool = False) -> dict:
    """Create a project brief note from the project brief template."""
    return _create_project_note(project_name, target_path, overwrite)


@mcp.tool(
    description="Create a decision note from the decision template, using decisions/{slug}.md by default.",
    annotations=_write_tool_annotations("Create Decision Note"),
)
def create_decision_note(decision_title: str, target_path: str = "", overwrite: bool = False) -> dict:
    """Create a decision note from the decision template."""
    return _create_decision_note(decision_title, target_path, overwrite)


@mcp.resource(
    "knowledge://{path*}",
    name="Knowledge Bank Markdown File",
    description="Read a Markdown file from the sandboxed personal knowledge bank.",
    mime_type="text/markdown",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
)
def knowledge_file_resource(path: str) -> str:
    """Read a Markdown file as a knowledge:// resource."""
    return _read(path)


@mcp.prompt
def standup_update() -> str:
    """Bonus: surface the saved standup prompt as a reusable MCP prompt.

    Demonstrates the third MCP building block — a Prompt — sourced directly
    from the knowledge bank so there is a single source of truth.
    """
    return _read("agents/standup-helper-prompt.md")


@mcp.prompt
def weekly_review() -> str:
    """Start a weekly review using goals, routines and the weekly review template."""
    return (
        "Use my knowledge bank to guide a weekly review. Read templates/weekly-review-template.md, "
        "current goals, routines/weekly-review.md and log.md. Help me reflect on results, energy, "
        "decisions, learning and focus for next week."
    )


@mcp.prompt
def learning_design(topic: str = "") -> str:
    """Plan a learning note using the learning-note template and learning notes."""
    topic_line = f" for {topic}" if topic else ""
    return (
        f"Plan a focused learning note{topic_line}. Use templates/learning-note-template.md, "
        "learning/learning-plan.md and relevant learning notes. Return a clear summary with what "
        "to learn, why it matters, an example and follow-up questions."
    )


@mcp.prompt
def one_on_one_prep(context: str = "") -> str:
    """Prepare a 1-on-1 with your lead using career and team notes."""
    return (
        "Help me prepare a 1-on-1 with my lead using templates/one-on-one-template.md, "
        "goals/career-growth.md and work/team-and-stakeholders.md. "
        f"Context: {context}"
    )


@mcp.prompt
def project_kickoff(request: str = "") -> str:
    """Prepare for a new project using project, technical-decision and growth context."""
    return (
        "Help me prepare for a new project using prepare_project_context, "
        "prepare_technical_decision_context and prepare_growth_context. Give advice on tasks, "
        f"risks, dependencies and next questions. Request: {request}"
    )


if __name__ == "__main__":
    # Streamable HTTP endpoint: http://127.0.0.1:8000/mcp
    mcp.run(transport="http", host=HTTP_HOST, port=HTTP_PORT)
