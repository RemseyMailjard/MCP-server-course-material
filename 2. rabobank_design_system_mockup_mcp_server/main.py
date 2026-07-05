from __future__ import annotations

from copy import deepcopy
import logging
import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

SERVER_NAME = "Design Styling MCP"
SERVER_VERSION = "0.2.0"
SERVER_OWNER = "Rabobank design demo maintainers"
READ_ONLY_TOOL_ANNOTATIONS = {
  "readOnlyHint": True,
  "destructiveHint": False,
  "idempotentHint": True,
  "openWorldHint": False,
}
SENSITIVE_FIELD_MARKERS = ("token", "secret", "password", "key", "authorization", "cookie", "credential")
MAX_QUERY_LENGTH = 80
MAX_TITLE_LENGTH = 80
LOGGER = logging.getLogger("design_styling_mcp")

if not LOGGER.handlers:
  handler = logging.StreamHandler()
  handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
  LOGGER.addHandler(handler)

LOGGER.setLevel(logging.INFO)

mcp = FastMCP(
  SERVER_NAME,
  version=SERVER_VERSION,
  instructions=(
    "This MCP server is read-only. It exposes design-system components, documentation, prompts, "
    "and accessibility references for demos and reviews. Use the discovery tools first when you "
    "need to understand the available surfaces. Do not expect this server to create, modify, or "
    "delete files, credentials, or external system data."
  ),
  strict_input_validation=True,
)


def _normalize_identifier(value: str) -> str:
  return value.strip().lower()


def _sanitize_log_value(field_name: str, value: Any) -> Any:
  # Learning goal: show that observability and data minimization belong together.
  # We still log enough to debug tool calls, but we aggressively trim or redact
  # values so the server never turns logs into a second data store.
  normalized_field = field_name.lower()
  if any(marker in normalized_field for marker in SENSITIVE_FIELD_MARKERS):
    return "<redacted>"

  if isinstance(value, str):
    compact_value = " ".join(value.split())
    if len(compact_value) > 120:
      return f"{compact_value[:117]}..."
    return compact_value

  if isinstance(value, dict):
    return {key: _sanitize_log_value(key, nested_value) for key, nested_value in value.items()}

  if isinstance(value, (list, tuple, set)):
    return f"{type(value).__name__}(len={len(value)})"

  return value


def _safe_log(event: str, **details: Any) -> None:
  if not LOGGER.isEnabledFor(logging.INFO):
    return

  safe_details = {key: _sanitize_log_value(key, value) for key, value in details.items()}
  LOGGER.info("%s %s", event, safe_details)


def _error_response(
  error: str,
  next_step: str,
  *,
  field: str | None = None,
  allowed_values: list[str] | None = None,
  provided_value: str | None = None,
) -> dict[str, Any]:
  response: dict[str, Any] = {
    "error": error,
    "next_step": next_step,
  }

  if field:
    response["field"] = field

  if allowed_values is not None:
    response["allowed_values"] = allowed_values

  if provided_value and field and not any(marker in field.lower() for marker in SENSITIVE_FIELD_MARKERS):
    response["provided_value"] = provided_value

  return response


def _validate_non_empty_text(field_name: str, value: str, *, max_length: int) -> tuple[str | None, dict[str, Any] | None]:
  # Learning goal: validate at the boundary of the tool call, not deep in the
  # rendering logic. That keeps later functions simpler because they can assume
  # they receive already-normalized input.
  candidate = " ".join(value.split())
  if not candidate:
    return None, _error_response(
      f"{field_name.replace('_', ' ').capitalize()} cannot be empty.",
      f"Provide a concise {field_name.replace('_', ' ')} value.",
      field=field_name,
    )

  if len(candidate) > max_length:
    return None, _error_response(
      f"{field_name.replace('_', ' ').capitalize()} must be {max_length} characters or fewer.",
      f"Shorten the {field_name.replace('_', ' ')} and try again.",
      field=field_name,
    )

  return candidate, None


def _validate_catalog_identifier(
  field_name: str,
  raw_value: str,
  allowed_values: list[str],
  *,
  next_step: str,
) -> tuple[str | None, dict[str, Any] | None]:
  # This helper turns user input into a stable catalog key and returns a
  # structured error when the lookup fails. For developers, this is the useful
  # pattern: keep validation reusable and keep failure messages actionable.
  normalized_value, error = _validate_non_empty_text(field_name, raw_value, max_length=MAX_QUERY_LENGTH)
  if error:
    return None, error

  assert normalized_value is not None
  identifier = _normalize_identifier(normalized_value)
  if identifier not in allowed_values:
    return None, _error_response(
      f"Unknown {field_name.replace('_', ' ')} '{raw_value}'.",
      next_step,
      field=field_name,
      allowed_values=allowed_values,
      provided_value=raw_value,
    )

  return identifier, None


def _get_component(component_id: str) -> dict[str, Any] | None:
  return COMPONENTS.get(_normalize_identifier(component_id))


def _component_error(component_id: str) -> dict[str, Any]:
  return _error_response(
    f"Unknown component '{component_id}'.",
    "Use list_components() or search_components() to find a valid component id.",
    field="component_id",
    allowed_values=COMPONENT_ORDER,
    provided_value=component_id,
  )


def _documentation_error(topic: str) -> dict[str, Any]:
  return _error_response(
    f"Unknown documentation topic '{topic}'.",
    "Try the overview, html, css, javascript, accessibility, or composition topic.",
    field="topic",
    allowed_values=sorted(DOCUMENTATION_TOPICS.keys()),
    provided_value=topic,
  )


RESOURCE_DIR = Path(__file__).parent / "resources"
ACCESSIBILITY_GUIDANCE_FILES = [
  "accessibility-keyboard-navigation.md",
  "accessibility-focus-and-feedback.md",
  "accessibility-readable-content.md",
  "accessibility-forms-and-actions.md",
  "accessibility-inclusive-layouts.md",
]
RESOURCE_CATALOG = {
  "accessibility-guidance": {
    "uri": "resource://accessibility-guidance",
    "title": "Accessibility Guidance",
    "topic": "accessibility",
    "summary": "Use these five Rabobank-style markdown guides to keep demos calm, clear, and inclusive.",
    "kind": "markdown-reference-index",
    "backing_files": ACCESSIBILITY_GUIDANCE_FILES,
    "example_prompt": "What accessibility resources are available, and which one should I open for keyboard navigation?",
  }
}
PROMPT_CATALOG = [
  {
    "name": "Explain color blind contrast",
    "summary": "Review contrast risks and safer visual state patterns for a component and theme.",
    "arguments": {"component_id": "navbar", "theme": "ocean"},
  },
  {
    "name": "Audit keyboard journey",
    "summary": "Walk through keyboard order, focus flow, and likely interaction traps.",
    "arguments": {"component_id": "feature-panel"},
  },
  {
    "name": "Improve focus states",
    "summary": "Strengthen visible focus styling without breaking the component's visual language.",
    "arguments": {"component_id": "button", "theme": "ocean"},
  },
  {
    "name": "Rewrite UI microcopy for clarity",
    "summary": "Rewrite labels and supporting copy so the interface reads more clearly and confidently.",
    "arguments": {"component_id": "card", "audience": "retail banking customer"},
  },
  {
    "name": "Recommend the right component",
    "summary": "Choose the best component for a product goal and explain the tradeoffs.",
    "arguments": {"product_goal": "launch announcement"},
  },
  {
    "name": "Craft accessible call-to-action guidance",
    "summary": "Improve CTA wording and interaction details with accessibility in mind.",
    "arguments": {"component_id": "navbar", "action_goal": "start the demo"},
  },
  {
    "name": "Review story page hierarchy",
    "summary": "Review reading order, emphasis, and hierarchy inside a composed story page.",
    "arguments": {"component_id": "feature-panel", "topic": "composition", "theme": "ocean"},
  },
  {
    "name": "Compare theme readability",
    "summary": "Compare two themes for readability, contrast, and low-vision friendliness.",
    "arguments": {"component_id": "card", "theme_a": "ocean", "theme_b": "midnight"},
  },
  {
    "name": "Create design handoff summary",
    "summary": "Turn a component bundle into a concise implementation handoff.",
    "arguments": {"component_id": "card", "theme": "sunset"},
  },
  {
    "name": "Find the right accessibility guide",
    "summary": "Match a user need to the most relevant accessibility reference file.",
    "arguments": {"user_need": "keyboard navigation"},
  },
]

THEME_TOKENS: dict[str, dict[str, str]] = {
  "ocean": {
    "background": "#f8fafc",
    "surface": "#ffffff",
    "text": "#0f172a",
    "muted": "#475569",
    "primary": "#0f766e",
    "secondary": "#14b8a6",
    "radius": "1rem",
    "shadow": "0 18px 40px rgba(15, 23, 42, 0.1)",
  },
  "midnight": {
    "background": "#020617",
    "surface": "#0f172a",
    "text": "#e2e8f0",
    "muted": "#94a3b8",
    "primary": "#38bdf8",
    "secondary": "#60a5fa",
    "radius": "1rem",
    "shadow": "0 22px 45px rgba(2, 6, 23, 0.35)",
  },
  "sunset": {
    "background": "#fff7ed",
    "surface": "#ffffff",
    "text": "#1f2937",
    "muted": "#6b7280",
    "primary": "#c2410c",
    "secondary": "#fb923c",
    "radius": "1rem",
    "shadow": "0 22px 45px rgba(194, 65, 12, 0.18)",
  },
  "forest": {
    "background": "#f0fdf4",
    "surface": "#ffffff",
    "text": "#0f172a",
    "muted": "#475569",
    "primary": "#166534",
    "secondary": "#22c55e",
    "radius": "1rem",
    "shadow": "0 18px 40px rgba(22, 101, 52, 0.18)",
  },
}

TOOL_DISCOVERY_EXAMPLES = {
  "list_components": {"arguments": {}, "expected_output": "A compact catalog of component ids, names, purposes, and variants."},
  "search_components": {"arguments": {"query": "launch story"}, "expected_output": "The matching components plus their outlines and next step."},
  "get_component_outline": {"arguments": {"component_id": "feature-panel"}, "expected_output": "The component structure, notes, and suggested usage."},
  "list_design_topics": {"arguments": {}, "expected_output": "The supported documentation topics and one-line summaries."},
  "list_resources": {"arguments": {}, "expected_output": "The resource catalog with URIs and example prompts."},
  "list_prompt_templates": {"arguments": {}, "expected_output": "The reusable MCP prompt templates and their example arguments."},
  "describe_server_capabilities": {"arguments": {}, "expected_output": "A compact overview of components, topics, prompts, and resources."},
  "discover_server_tools": {"arguments": {}, "expected_output": "A self-describing tool catalog with when-to-use guidance and examples."},
  "get_server_governance": {"arguments": {}, "expected_output": "Read-only governance, environment, approval, and ownership guidance."},
  "get_design_documentation": {"arguments": {"topic": "accessibility"}, "expected_output": "Topic-specific guidance with summary, guidelines, and example prompt."},
  "get_component_bundle": {"arguments": {"component_id": "card"}, "expected_output": "HTML, CSS, JS, notes, and outline for one component."},
  "get_design_tokens": {"arguments": {"theme": "sunset"}, "expected_output": "A theme token set for colors, spacing tone, and shadows."},
  "build_component_page": {"arguments": {"component_id": "navbar", "title": "Launch demo", "theme": "midnight"}, "expected_output": "A standalone HTML preview page for one component."},
  "build_component_story_page": {"arguments": {"component_id": "feature-panel", "theme": "ocean", "topic": "composition", "title": "Launch review"}, "expected_output": "A richer review page that combines component preview and documentation."},
}

TOOL_DISCOVERY_SUMMARIES = {
  "list_components": "Browse the read-only component catalog before requesting a specific component.",
  "search_components": "Search by interaction or layout goal when you do not know the component id.",
  "get_component_outline": "Inspect the structure and usage notes for one component before loading the full code bundle.",
  "list_design_topics": "Browse the documentation topics available in this server.",
  "list_resources": "Discover the file-backed MCP resources exposed by this server.",
  "list_prompt_templates": "Discover the reusable user-facing MCP prompts exposed by this server.",
  "describe_server_capabilities": "Get a compact server overview with the main discovery surfaces.",
  "discover_server_tools": "Get a self-describing catalog of all tools, examples, and safety characteristics.",
  "get_server_governance": "Inspect read-only boundaries, environment guidance, approval policy, and maintenance ownership.",
  "get_design_documentation": "Read one documentation topic with practical design-system guidance.",
  "get_component_bundle": "Fetch one component's HTML, CSS, JavaScript, notes, and outline.",
  "get_design_tokens": "Fetch a theme token set for consistent styling decisions.",
  "build_component_page": "Generate a standalone HTML preview page for one component and theme.",
  "build_component_story_page": "Generate a richer story page that combines preview, theme, and documentation context.",
}

GOVERNANCE_PROFILE = {
  "owner": SERVER_OWNER,
  "version": SERVER_VERSION,
  "transport": "stdio",
  "environment_variable": "DESIGN_STYLING_MCP_ENV",
  "read_only_surface": True,
  "least_privilege_boundary": [
    "No file creation, update, or deletion tools are exposed.",
    "No credential, account, or customer data is stored or returned.",
    "Only the bundled component catalog, themes, documentation, prompts, and file-backed accessibility references are available.",
  ],
  "critical_action_policy": "No critical create, update, or delete actions are currently exposed. Any future mutating tool must be added as a separate tool with explicit approval and destructive metadata.",
  "safe_logging_policy": "Log tool names, outcome counts, and validated identifiers only. Never log HTML payloads, JavaScript payloads, file contents, or secrets.",
  "sensitive_data_policy": "Do not place credentials, internal identifiers, personal data, or production-only information in the component catalog, prompts, resources, or logs.",
  "environments": {
    "development": "Use sample-only content, exploratory prompts, and local resources.",
    "test": "Validate prompt flows, discovery, and example outputs with representative but non-sensitive data.",
    "production": "Expose only approved demo assets, reviewed documentation, and versioned prompt content.",
  },
  "maintainability": {
    "ownership": "The maintainers should review every new tool for naming, validation, read-only boundaries, and documentation coverage.",
    "monitoring": "Review server import health, tool registration, and safe logs during releases.",
    "versioning": "Bump the MCP server version whenever tools, prompts, resources, or return shapes change materially.",
    "approval_process": "Review and approve any new mutating or externally connected tool before release.",
  },
}


def _parse_markdown_guidance(file_path: Path) -> dict[str, Any]:
  # Learning goal: the markdown files act as content storage, while Python turns
  # that content into a predictable MCP payload. This separation lets developers
  # update guidance without having to rewrite the resource contract.
  content = file_path.read_text(encoding="utf-8")
  title = ""
  summary = ""
  guidelines: list[str] = []
  example_prompt = ""
  joke = ""
  current_section = ""

  for raw_line in content.splitlines():
    line = raw_line.strip()
    if not line:
      continue

    if line.startswith("# "):
      title = line[2:].strip()
      current_section = ""
      continue

    if line.startswith("Summary:"):
      summary = line.split(":", 1)[1].strip()
      current_section = ""
      continue

    if line == "## Guidelines":
      current_section = "guidelines"
      continue

    if line == "## Example Prompt":
      current_section = "example_prompt"
      continue

    if line == "## Joke":
      current_section = "joke"
      continue

    if current_section == "guidelines" and line.startswith("- "):
      guidelines.append(line[2:].strip())
      continue

    if current_section == "example_prompt":
      example_prompt = line
      current_section = ""
      continue

    if current_section == "joke":
      joke = line
      current_section = ""

  return {
    "title": title,
    "summary": summary,
    "guidelines": guidelines,
    "example_prompt": example_prompt,
    "joke": joke,
    "path": str(file_path.relative_to(Path(__file__).parent)).replace("\\", "/"),
    "markdown": content,
  }


def _load_accessibility_guidance_sections() -> list[dict[str, Any]]:
  return [_parse_markdown_guidance(RESOURCE_DIR / file_name) for file_name in ACCESSIBILITY_GUIDANCE_FILES]


def _load_accessibility_guidance_references() -> list[dict[str, str]]:
  # The resource returns file references instead of inlining every markdown file.
  # That keeps the index concise and teaches clients to discover deeper content
  # in steps instead of fetching one oversized payload.
  return [
    {
      "title": section["title"],
      "summary": section["summary"],
      "path": section["path"],
      "uri": (RESOURCE_DIR / section["path"].split("/", 1)[-1]).resolve().as_uri(),
    }
    for section in _load_accessibility_guidance_sections()
  ]


def _list_available_resources() -> list[dict[str, Any]]:
  resources: list[dict[str, Any]] = []
  for resource_id, resource in RESOURCE_CATALOG.items():
    resources.append(
      {
        "id": resource_id,
        "uri": resource["uri"],
        "title": resource["title"],
        "topic": resource["topic"],
        "summary": resource["summary"],
        "kind": resource["kind"],
        "file_count": len(resource["backing_files"]),
        "example_prompt": resource["example_prompt"],
      }
    )

  return resources


def _list_available_prompts() -> list[dict[str, Any]]:
  return [
    {
      "name": prompt["name"],
      "summary": prompt["summary"],
      "arguments": prompt["arguments"],
    }
    for prompt in PROMPT_CATALOG
  ]


COMPONENTS: dict[str, dict[str, Any]] = {
    "button": {
        "name": "Glass Accent Button",
        "purpose": "Primary call-to-action button for modern product interfaces.",
        "variant": "modern",
        "html": """<button class=\"ui-button\" type=\"button\" data-ui-button>
  <span>Continue</span>
</button>""",
        "css": """.ui-button {
  appearance: none;
  border: 0;
  border-radius: 999px;
  padding: 0.9rem 1.35rem;
  font: 600 1rem/1 system-ui, sans-serif;
  color: #fff;
  background: linear-gradient(135deg, #0f766e, #14b8a6);
  box-shadow: 0 16px 35px rgba(15, 118, 110, 0.28);
  cursor: pointer;
  transition: transform 160ms ease, box-shadow 160ms ease, filter 160ms ease;
}

.ui-button:hover {
  transform: translateY(-1px);
  filter: brightness(1.04);
  box-shadow: 0 20px 38px rgba(15, 118, 110, 0.34);
}

.ui-button:active {
  transform: translateY(0);
  box-shadow: 0 10px 24px rgba(15, 118, 110, 0.22);
}""",
        "js": """document.querySelectorAll('[data-ui-button]').forEach((button) => {
  button.addEventListener('click', () => {
    button.classList.add('is-pressed');
    window.setTimeout(() => button.classList.remove('is-pressed'), 180);
  });
});""",
        "notes": [
            "Use for primary actions only.",
            "Keep the label short and specific.",
        ],
    },
    "card": {
        "name": "Elevated Content Card",
        "purpose": "Reusable card for summaries, metrics, or feature highlights.",
        "variant": "editorial",
        "html": """<article class=\"ui-card\" data-ui-card>
  <p class=\"ui-card__eyebrow\">Workspace update</p>
  <h3>Design review ready</h3>
  <p>Ship a clean component preview with deliberate spacing, depth, and readable hierarchy.</p>
</article>""",
        "css": """.ui-card {
  max-width: 22rem;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 1.25rem;
  padding: 1.25rem;
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(12px);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.1);
}

.ui-card__eyebrow {
  margin: 0 0 0.5rem;
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: #0f766e;
}

.ui-card h3 {
  margin: 0 0 0.75rem;
  font-size: 1.25rem;
}

.ui-card p:last-child {
  margin: 0;
  color: #475569;
  line-height: 1.6;
}""",
        "js": """document.querySelectorAll('[data-ui-card]').forEach((card) => {
  card.addEventListener('mouseenter', () => card.setAttribute('data-hovered', 'true'));
  card.addEventListener('mouseleave', () => card.removeAttribute('data-hovered'));
});""",
        "notes": [
            "Best on light backgrounds or soft gradients.",
            "Mix title, supporting text, and an optional action.",
        ],
    },
    "feature-panel": {
        "name": "Feature Panel",
        "purpose": "Large composed block for product stories, onboarding flows, or launch announcements.",
        "variant": "composed",
        "html": """<section class=\"ui-feature-panel\" data-ui-feature-panel>
  <div class=\"ui-feature-panel__content\">
    <p class=\"ui-feature-panel__eyebrow\">New release</p>
    <h3>Launch-ready workflow</h3>
    <p>Combine context, action, and guidance in one component that reads well inside a story page.</p>
  </div>
  <div class=\"ui-feature-panel__actions\">
    <button class=\"ui-feature-panel__cta\" type=\"button\">Explore</button>
    <a class=\"ui-feature-panel__link\" href=\"#\">View details</a>
  </div>
</section>""",
        "css": """.ui-feature-panel {
  display: grid;
  grid-template-columns: 1.45fr auto;
  gap: 1rem;
  align-items: end;
  max-width: 42rem;
  padding: 1.4rem;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 1.5rem;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(236, 254, 255, 0.92));
  box-shadow: 0 20px 45px rgba(15, 23, 42, 0.1);
}

.ui-feature-panel__eyebrow {
  margin: 0 0 0.45rem;
  font-size: 0.78rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: #0f766e;
}

.ui-feature-panel h3 {
  margin: 0 0 0.7rem;
  font-size: clamp(1.4rem, 2vw, 1.9rem);
}

.ui-feature-panel p:last-child {
  margin: 0;
  color: #475569;
  line-height: 1.65;
}

.ui-feature-panel__actions {
  display: grid;
  justify-items: end;
  gap: 0.65rem;
}

.ui-feature-panel__cta {
  border: 0;
  border-radius: 999px;
  padding: 0.8rem 1.15rem;
  background: linear-gradient(135deg, #0f766e, #14b8a6);
  color: #fff;
  font-weight: 800;
}

.ui-feature-panel__link {
  color: #0f766e;
  font-weight: 700;
  text-decoration: none;
}""",
        "js": """document.querySelectorAll('[data-ui-feature-panel]').forEach((panel) => {
  panel.addEventListener('click', () => panel.toggleAttribute('data-highlighted'));
});""",
        "notes": [
            "Best for launch stories or onboarding summaries.",
            "Pairs well with one primary action and one supporting link.",
        ],
    },
    "navbar": {
        "name": "Floating Navbar",
        "purpose": "Compact top navigation with subtle glass styling.",
        "variant": "navigation",
        "html": """<header class=\"ui-navbar\">
  <a class=\"ui-navbar__brand\" href=\"#\">Northstar</a>
  <nav class=\"ui-navbar__links\">
    <a href=\"#overview\">Overview</a>
    <a href=\"#components\">Components</a>
    <a href=\"#tokens\">Tokens</a>
  </nav>
  <button class=\"ui-navbar__action\" type=\"button\">Try demo</button>
</header>""",
        "css": """.ui-navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.9rem 1.1rem;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 1rem;
  background: rgba(15, 23, 42, 0.78);
  color: #fff;
  backdrop-filter: blur(18px);
}

.ui-navbar__brand,
.ui-navbar__links a {
  color: inherit;
  text-decoration: none;
}

.ui-navbar__brand {
  font-weight: 800;
  letter-spacing: 0.02em;
}

.ui-navbar__links {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.ui-navbar__action {
  border: 0;
  border-radius: 999px;
  padding: 0.7rem 1rem;
  background: #f8fafc;
  color: #0f172a;
  font-weight: 700;
}""",
        "js": """document.querySelectorAll('.ui-navbar__action').forEach((button) => {
  button.addEventListener('click', () => {
    console.log('Demo CTA clicked');
  });
});""",
        "notes": [
            "Ideal for dashboards and product landing pages.",
            "Pair with a strong hero and clear page sections.",
        ],
    },
}

COMPONENT_ORDER = ["button", "card", "feature-panel", "navbar"]

DOCUMENTATION_TOPICS: dict[str, dict[str, Any]] = {
  "overview": {
    "title": "Design System Overview",
    "summary": "Use the demo components to keep layout, motion, and spacing consistent across small UI prototypes.",
    "guidelines": [
      "Prefer one clear primary action per screen.",
      "Use soft contrast, not harsh neon accents.",
      "Keep spacing generous and typography readable.",
      "Return HTML, CSS, and JS together when the component needs interaction.",
    ],
    "example_prompt": "Give me a button component with HTML, CSS, and JS.",
  },
  "html": {
    "title": "HTML Guidance",
    "summary": "Structure components with semantic elements and concise labels.",
    "guidelines": [
      "Use semantic tags like button, article, header, and nav.",
      "Keep HTML focused on structure rather than visual styling.",
      "Add data attributes only when the JavaScript needs a hook.",
    ],
    "example_prompt": "Show me a semantic card component in HTML.",
  },
  "css": {
    "title": "CSS Guidance",
    "summary": "Use a small token set, strong spacing rules, and deliberate visual hierarchy.",
    "guidelines": [
      "Define radius, color, and shadow values consistently.",
      "Prefer readable font sizes and line heights.",
      "Use transitions for subtle feedback, not constant motion.",
    ],
    "example_prompt": "Give me CSS guidance for a glass-style navbar.",
  },
  "javascript": {
    "title": "JavaScript Guidance",
    "summary": "Keep interaction small and purposeful.",
    "guidelines": [
      "Attach event listeners only where behavior is needed.",
      "Avoid framework assumptions in demo snippets.",
      "Use JS to enhance interaction, not to build layout.",
    ],
    "example_prompt": "Explain the JavaScript behavior for a button component.",
  },
  "accessibility": {
    "title": "Accessibility Guidance",
    "summary": "Design components that remain usable with keyboard, screen readers, and low vision.",
    "guidelines": [
      "Preserve native controls for interactive elements whenever possible.",
      "Keep visible focus states and sufficient contrast.",
      "Use descriptive labels and short text.",
    ],
    "example_prompt": "Give me accessibility notes for the navbar component.",
  },
  "composition": {
    "title": "Composition Guidance",
    "summary": "Use the demo components together without losing hierarchy.",
    "guidelines": [
      "Keep one primary action per surface.",
      "Balance text, whitespace, and supporting actions.",
      "Maintain visible focus states in every composed layout.",
      "Return a short explanation for how the pieces fit together.",
    ],
    "example_prompt": "Explain how to combine a hero and a button component.",
  },
}


COMPONENT_OUTLINES: dict[str, list[str]] = {
  "button": ["Action", "Label", "Interaction"],
  "card": ["Eyebrow", "Title", "Body", "Optional action"],
  "feature-panel": ["Eyebrow", "Title", "Body", "Primary action", "Secondary link"],
  "navbar": ["Brand", "Links", "Action"],
}


@mcp.tool(
  title="List Components",
  description="List the read-only demo components exposed by this MCP server. Use this before requesting a component outline or bundle when you want to browse the available component ids.",
  annotations=READ_ONLY_TOOL_ANNOTATIONS,
)
def list_components() -> list[dict[str, str]]:
    """List the demo design components that the server can return."""
    return [
        {
            "id": component_id,
            "name": COMPONENTS[component_id]["name"],
            "purpose": COMPONENTS[component_id]["purpose"],
            "variant": COMPONENTS[component_id]["variant"],
        }
        for component_id in COMPONENT_ORDER
    ]


@mcp.tool(
  title="Search Components",
  description="Search the read-only component catalog by layout goal, component name, usage notes, or outline terms. Use this when you know the design intent but not the component id.",
  annotations=READ_ONLY_TOOL_ANNOTATIONS,
)
def search_components(query: str) -> dict[str, Any]:
  """Search the demo catalog by component name, purpose, notes, or outline.

  Use this when you know the desired interaction or layout pattern but not the exact component id.
  """
  validated_query, error = _validate_non_empty_text("query", query, max_length=MAX_QUERY_LENGTH)
  if error:
    return error

  assert validated_query is not None
  normalized_query = validated_query.lower()
  _safe_log("search_components", query=validated_query)

  matches: list[dict[str, Any]] = []
  for component_id in COMPONENT_ORDER:
    component = COMPONENTS[component_id]
    outline = COMPONENT_OUTLINES.get(component_id, [])
    haystack = " ".join(
      [component_id, component["name"], component["purpose"], component["variant"], " ".join(component["notes"]), " ".join(outline)]
    ).lower()

    if normalized_query in haystack:
      matches.append(
        {
          "id": component_id,
          "name": component["name"],
          "purpose": component["purpose"],
          "variant": component["variant"],
          "outline": outline,
        }
      )

  return {
    "query": validated_query,
    "match_count": len(matches),
    "matches": matches,
    "next_step": "Use get_component_bundle() or get_component_outline() for the best match.",
  }


@mcp.tool(
  title="Get Component Outline",
  description="Return the structure, usage notes, and suggested fit for a single component. Use this when you want a compact overview before loading the full HTML, CSS, and JavaScript bundle.",
  annotations=READ_ONLY_TOOL_ANNOTATIONS,
)
def get_component_outline(component_id: str) -> dict[str, Any]:
  """Return the structure, notes, and suggested usage for one component.

  Use this when you need a compact overview before asking for the full HTML, CSS, and JS bundle.
  """
  normalized_id, error = _validate_catalog_identifier(
    "component_id",
    component_id,
    COMPONENT_ORDER,
    next_step="Use list_components() or search_components() to find a valid component id.",
  )
  if error:
    return error

  assert normalized_id is not None
  component = _get_component(normalized_id)
  if not component:
    return _component_error(component_id)

  _safe_log("get_component_outline", component_id=normalized_id)
  return {
    "component_id": normalized_id,
    "name": component["name"],
    "purpose": component["purpose"],
    "variant": component["variant"],
    "outline": COMPONENT_OUTLINES.get(normalized_id, []),
    "notes": component["notes"],
    "recommended_prompt": f"Use the {normalized_id} component for a polished design demo.",
  }


@mcp.tool(
  title="List Design Topics",
  description="List the documentation topics available in this read-only MCP server. Use this before requesting topic-specific design-system guidance.",
  annotations=READ_ONLY_TOOL_ANNOTATIONS,
)
def list_design_topics() -> list[dict[str, str]]:
  """List the available documentation topics in the demo server."""
  return [
    {
      "topic": topic,
      "title": documentation["title"],
      "summary": documentation["summary"],
    }
    for topic, documentation in DOCUMENTATION_TOPICS.items()
  ]


@mcp.tool(
  title="List Resources",
  description="List the file-backed MCP resources exposed by this server. Use this when you want to browse available references before opening a resource URI.",
  annotations=READ_ONLY_TOOL_ANNOTATIONS,
)
def list_resources() -> list[dict[str, Any]]:
  """List the MCP resources that this demo server exposes.

  Use this when you want to discover which reference-style resources are available before opening one.
  """
  return _list_available_resources()


@mcp.tool(
  title="List Prompt Templates",
  description="List the reusable user-facing MCP prompt templates exposed by this server. Use this when you want discovery help before selecting a prompt in an MCP client.",
  annotations=READ_ONLY_TOOL_ANNOTATIONS,
)
def list_prompt_templates() -> list[dict[str, Any]]:
  """List the user-facing MCP prompts exposed by this demo server.

  Use this when you want to discover reusable prompt workflows before selecting one in an MCP client.
  """
  return _list_available_prompts()


@mcp.tool(
  title="Describe Server Capabilities",
  description="Summarize the main discovery surfaces exposed by this MCP server, including components, topics, prompts, and resources. Use this when you need a compact overview instead of the full tool catalog.",
  annotations=READ_ONLY_TOOL_ANNOTATIONS,
)
def describe_server_capabilities() -> dict[str, Any]:
  """Summarize the discovery surfaces exposed by this MCP server.

  Use this when you want one compact overview of the available tools, prompts, resources, components, and topics.
  """
  return {
    "server_name": SERVER_NAME,
    "server_version": SERVER_VERSION,
    "transport": "stdio",
    "read_only": True,
    "component_count": len(COMPONENT_ORDER),
    "topic_count": len(DOCUMENTATION_TOPICS),
    "resource_count": len(RESOURCE_CATALOG),
    "prompt_count": len(PROMPT_CATALOG),
    "components": COMPONENT_ORDER,
    "topics": sorted(DOCUMENTATION_TOPICS.keys()),
    "resources": _list_available_resources(),
    "prompts": _list_available_prompts(),
    "recommended_start": [
      "Call discover_server_tools() to see the full tool catalog with examples.",
      "Call list_components() to browse the component catalog.",
      "Call list_design_topics() to inspect the documentation topics.",
      "Call list_resources() to discover reference-style MCP resources.",
      "Call list_prompt_templates() to discover reusable prompt workflows.",
    ],
    "governance_summary": {
      "owner": GOVERNANCE_PROFILE["owner"],
      "read_only_surface": GOVERNANCE_PROFILE["read_only_surface"],
      "approval_policy": GOVERNANCE_PROFILE["critical_action_policy"],
    },
  }


@mcp.tool(
  title="Discover Server Tools",
  description="Return a self-describing catalog of the tools exposed by this MCP server, including when to use each tool, example arguments, and expected outputs. Use this when the user asks what the server can do, which tools are available, or to show examples.",
  annotations=READ_ONLY_TOOL_ANNOTATIONS,
)
def discover_server_tools() -> dict[str, Any]:
  """Return a self-describing tool catalog with examples and safety notes."""
  tool_catalog = []
  for tool_name, summary in TOOL_DISCOVERY_SUMMARIES.items():
    example = TOOL_DISCOVERY_EXAMPLES[tool_name]
    tool_catalog.append(
      {
        "name": tool_name,
        "summary": summary,
        "read_only": True,
        "approval_required": False,
        "example_arguments": example["arguments"],
        "expected_output": example["expected_output"],
      }
    )

  return {
    "server_name": SERVER_NAME,
    "server_version": SERVER_VERSION,
    "what_it_can_do": [
      "Return reusable component bundles for demos and design handoffs.",
      "Explain design-system topics such as accessibility, composition, HTML, CSS, and JavaScript usage.",
      "Return theme tokens and build preview pages for design review flows.",
      "Expose prompts and accessibility resources so the server is easy to explore from within MCP clients.",
    ],
    "tool_count": len(tool_catalog),
    "tool_catalog": tool_catalog,
    "example_questions": [
      "What can this MCP server do?",
      "Which tools are available for component discovery?",
      "Show me an example for building a story page.",
    ],
    "next_step": "Start with list_components(), list_design_topics(), or get_server_governance() depending on whether you want content, documentation, or policy details.",
  }


@mcp.tool(
  title="Get Server Governance",
  description="Return governance and maintainability guidance for this MCP server, including read-only boundaries, environment separation, ownership, monitoring, and approval policy. Use this when reviewing the server against security or operational best practices.",
  annotations=READ_ONLY_TOOL_ANNOTATIONS,
)
def get_server_governance() -> dict[str, Any]:
  """Return governance, approval, and environment guidance for this server."""
  current_environment = _normalize_identifier(os.getenv(GOVERNANCE_PROFILE["environment_variable"], "development"))
  if current_environment not in GOVERNANCE_PROFILE["environments"]:
    current_environment = "development"

  return {
    **GOVERNANCE_PROFILE,
    "current_environment": current_environment,
    "environment_guidance": GOVERNANCE_PROFILE["environments"][current_environment],
  }


@mcp.prompt("Explain color blind contrast")
def explain_color_blind_contrast(component_id: str = "navbar", theme: str = "ocean") -> str:
  """Explain how a component should handle contrast and color-blind-friendly states."""
  return f"""Use this MCP server to explain color-blind-friendly contrast decisions for the {component_id} component in the {theme} theme.

Work method:
- Use get_component_bundle("{component_id}") to inspect the current structure and styling.
- Use get_design_tokens("{theme}") to review the active color system.
- Use get_design_documentation("accessibility") and accessibility_guidance to ground the advice in this server's accessibility guidance.

Response requirements:
- Explain which color combinations are likely to be fragile for color-blind users.
- Recommend safer contrast and state differentiation patterns without changing the component's overall tone.
- Suggest at least three practical improvements for hover, active, focus, or status states.
- Keep the tone calm, polished, and suitable for a Rabobank-style design review.
- End with a short implementation summary that a designer or frontend developer could act on immediately.
"""


@mcp.prompt("Audit keyboard journey")
def audit_keyboard_journey(component_id: str = "feature-panel") -> str:
  """Review a component from the perspective of keyboard-only interaction."""
  return f"""Audit the keyboard journey for the {component_id} component using this MCP server.

Work method:
- Use get_component_outline("{component_id}") to understand the structure.
- Use get_component_bundle("{component_id}") to inspect the actual HTML, CSS, and JS.
- Use accessibility_guidance and its linked references to identify relevant keyboard and focus advice.

Response requirements:
- Walk through the expected Tab order step by step.
- Call out any likely keyboard traps, weak focus states, or interaction ambiguity.
- Recommend concrete HTML, CSS, and JavaScript adjustments where needed.
- Separate the answer into: Current flow, Risks, Improvements, and Quick win.
"""


@mcp.prompt("Improve focus states")
def improve_focus_states(component_id: str = "button", theme: str = "ocean") -> str:
  """Produce focused guidance for stronger visible focus treatments."""
  return f"""Improve the visible focus states for the {component_id} component in the {theme} theme.

Use this MCP server as the source of truth:
- get_component_bundle("{component_id}") for the current UI code
- get_design_tokens("{theme}") for color and surface decisions
- accessibility_guidance for file-backed focus and feedback guidance

Response requirements:
- Diagnose how discoverable the current focus state is.
- Propose a stronger focus treatment that fits the existing visual language.
- Include one CSS-oriented recommendation and one interaction-oriented recommendation.
- Keep the advice concise, practical, and ready for a design handoff.
"""


@mcp.prompt("Rewrite UI microcopy for clarity")
def rewrite_ui_microcopy_for_clarity(component_id: str = "card", audience: str = "retail banking customer") -> str:
  """Refine labels and supporting text for clarity and confidence."""
  return f"""Rewrite the UI microcopy for the {component_id} component so it feels clearer for a {audience}.

Work method:
- Use get_component_bundle("{component_id}") to review the current copy in context.
- Use get_design_documentation("html") and get_design_documentation("accessibility") to keep the labels concise and usable.

Response requirements:
- Preserve the original intent of the component.
- Rewrite labels, headings, helper copy, and actions where needed.
- Explain why each rewrite improves clarity, confidence, or accessibility.
- Keep the tone direct, friendly, and professionally understated.
"""


@mcp.prompt("Recommend the right component")
def recommend_the_right_component(product_goal: str = "launch announcement") -> str:
  """Help a user choose the strongest component for a specific design goal."""
  return f"""Recommend the best component in this MCP server for the following goal: {product_goal}.

Work method:
- Start with list_components() or search_components("{product_goal}").
- Use get_component_outline() on the strongest candidates before choosing one.

Response requirements:
- Compare the top one to three candidate components.
- Recommend one best fit and explain why it wins.
- Mention any tradeoffs or risks if the weaker candidates were used instead.
- Finish with the exact next MCP call the user should make.
"""


@mcp.prompt("Craft accessible call-to-action guidance")
def craft_accessible_call_to_action_guidance(component_id: str = "navbar", action_goal: str = "start the demo") -> str:
  """Guide a user toward clearer, more accessible call-to-action wording and behavior."""
  return f"""Create accessible call-to-action guidance for the {component_id} component with the goal: {action_goal}.

Use this MCP server to inspect the component and supporting guidance:
- get_component_bundle("{component_id}")
- get_design_documentation("accessibility")
- accessibility_guidance

Response requirements:
- Evaluate whether the current call to action is descriptive enough.
- Suggest stronger CTA labels that describe the outcome instead of the click.
- Include guidance for focus, target size, and surrounding supporting text.
- Return the answer in three sections: Label options, Interaction notes, Accessibility checks.
"""


@mcp.prompt("Review story page hierarchy")
def review_story_page_hierarchy(component_id: str = "feature-panel", topic: str = "composition", theme: str = "ocean") -> str:
  """Review whether a story page keeps hierarchy and context intact."""
  return f"""Review the hierarchy of a story page built for the {component_id} component using the {topic} topic and the {theme} theme.

Work method:
- Use build_component_story_page("{component_id}", theme="{theme}", topic="{topic}") to inspect the current story page.
- Use get_design_documentation("{topic}") for the composition intent.

Response requirements:
- Assess whether the page has a clear reading order and primary action.
- Call out any hierarchy conflicts between hero content, supporting guidance, and the preview area.
- Suggest refinements for layout, copy emphasis, and supporting metadata.
- Keep the answer framed as a design review, not as generic web advice.
"""


@mcp.prompt("Compare theme readability")
def compare_theme_readability(component_id: str = "card", theme_a: str = "ocean", theme_b: str = "midnight") -> str:
  """Compare two themes from a readability and accessibility perspective."""
  return f"""Compare the readability of the {component_id} component between the {theme_a} and {theme_b} themes.

Work method:
- Use get_component_bundle("{component_id}") once for the component structure.
- Use get_design_tokens("{theme_a}") and get_design_tokens("{theme_b}") for the visual systems.
- Use get_design_documentation("css") and get_design_documentation("accessibility") for design criteria.

Response requirements:
- Compare readability, contrast, emphasis, and likely low-vision performance.
- Identify which theme is safer for dense information and which is stronger for visual impact.
- Recommend one theme for production-style clarity and explain why.
- End with a brief verdict table in plain text.
"""


@mcp.prompt("Create design handoff summary")
def create_design_handoff_summary(component_id: str = "card", theme: str = "sunset") -> str:
  """Turn the server output into a concise implementation handoff."""
  return f"""Create a design handoff summary for the {component_id} component in the {theme} theme.

Work method:
- Use get_component_bundle("{component_id}") for the implementation details.
- Use get_design_tokens("{theme}") for the visual system.
- Use get_component_outline("{component_id}") for the structural summary.

Response requirements:
- Summarize the component's purpose, structure, styling direction, and interaction behavior.
- List the critical implementation details a frontend developer must preserve.
- Include one short accessibility checklist tied to this component.
- Keep the result concise enough to paste into a handoff note or ticket.
"""


@mcp.prompt("Find the right accessibility guide")
def find_the_right_accessibility_guide(user_need: str = "keyboard navigation") -> str:
  """Help a user discover which accessibility reference file to open."""
  return f"""Use this MCP server to find the best accessibility resource for this need: {user_need}.

Work method:
- Start with list_resources() to discover the available MCP resources.
- Open accessibility_guidance to inspect the indexed references.
- Match the user's need to the most relevant referenced markdown guide.

Response requirements:
- Recommend the single best accessibility reference first.
- Explain why it matches the stated need.
- Mention one secondary guide if there is a useful companion resource.
- Finish with the exact resource path or URI the user should open next.
"""


@mcp.tool(
  title="Get Design Documentation",
  description="Return one documentation topic with practical design-system guidance. Use this when you need reference material for topics such as overview, HTML, CSS, JavaScript, accessibility, or composition.",
  annotations=READ_ONLY_TOOL_ANNOTATIONS,
)
def get_design_documentation(topic: str = "overview") -> dict[str, Any]:
  """Return documentation and usage guidance for the demo design system.

  Use this when you want a quick explanation of how to use the HTML, CSS, and JavaScript snippets in this server.
  """
  normalized_topic, error = _validate_catalog_identifier(
    "topic",
    topic,
    sorted(DOCUMENTATION_TOPICS.keys()),
    next_step="Try the overview, html, css, javascript, accessibility, or composition topic.",
  )
  if error:
    return error

  assert normalized_topic is not None
  documentation = DOCUMENTATION_TOPICS.get(normalized_topic)
  if not documentation:
    return _documentation_error(topic)

  _safe_log("get_design_documentation", topic=normalized_topic)

  return {
    "topic": normalized_topic,
    **documentation,
  }


@mcp.tool(
  title="Get Component Bundle",
  description="Return one component's HTML, CSS, JavaScript, notes, and outline. Use this when you want a ready-to-paste component bundle for a demo, prototype, or design handoff.",
  annotations=READ_ONLY_TOOL_ANNOTATIONS,
)
def get_component_bundle(component_id: str) -> dict[str, Any]:
    """Return a component bundle with HTML, CSS, JS, and usage notes.

    Use this when you want a ready-to-paste UI component for a demo, prototype, or design handoff.
    """
    normalized_id, error = _validate_catalog_identifier(
        "component_id",
        component_id,
        COMPONENT_ORDER,
        next_step="Use list_components() or search_components() to find a valid component id.",
    )
    if error:
      return error

    assert normalized_id is not None
    component = COMPONENTS.get(normalized_id)
    if not component:
      return _component_error(component_id)

    bundle = deepcopy(component)
    bundle["component_id"] = normalized_id
    bundle["outline"] = COMPONENT_OUTLINES.get(normalized_id, [])
    _safe_log("get_component_bundle", component_id=normalized_id)
    return bundle


@mcp.tool(
  title="Get Design Tokens",
  description="Return a compact theme token set for the demo UI system. Use this when you need colors, surfaces, and shared visual values to keep component previews aligned.",
  annotations=READ_ONLY_TOOL_ANNOTATIONS,
)
def get_design_tokens(theme: str = "ocean") -> dict[str, Any]:
    """Return a compact design token set for the demo UI system.

    Use this when you need colors, spacing, and typography values to keep multiple components visually aligned.
    """
    normalized_theme, error = _validate_catalog_identifier(
      "theme",
      theme,
      sorted(THEME_TOKENS.keys()),
      next_step="Try ocean, midnight, sunset, or forest.",
    )
    if error:
      return error

    assert normalized_theme is not None
    selected = THEME_TOKENS.get(normalized_theme)
    if not selected:
      return _error_response(
        f"Unknown theme '{theme}'.",
        "Try ocean, midnight, sunset, or forest.",
        field="theme",
        allowed_values=sorted(THEME_TOKENS.keys()),
        provided_value=theme,
      )

    _safe_log("get_design_tokens", theme=normalized_theme)

    return {
      "theme": normalized_theme,
        "tokens": selected,
    }


@mcp.tool(
  title="Build Component Page",
  description="Return a standalone HTML preview page for one component and theme. Use this when you want a single-page preview with embedded styling and behavior.",
  annotations=READ_ONLY_TOOL_ANNOTATIONS,
)
def build_component_page(component_id: str, title: str = "Design Demo", theme: str = "ocean") -> dict[str, Any]:
    """Return a complete HTML page that previews one of the demo components.

    Use this when you want the component rendered in a standalone page with embedded CSS and JS.
    """
    normalized_id, error = _validate_catalog_identifier(
      "component_id",
      component_id,
      COMPONENT_ORDER,
      next_step="Use list_components() or search_components() to find a valid component id.",
    )
    if error:
      return error

    validated_title, error = _validate_non_empty_text("title", title, max_length=MAX_TITLE_LENGTH)
    if error:
      return error

    assert normalized_id is not None
    assert validated_title is not None
    component = _get_component(normalized_id)
    if not component:
        return _component_error(component_id)

    selected_tokens = get_design_tokens(theme)
    if "error" in selected_tokens:
        return selected_tokens

    outline = COMPONENT_OUTLINES.get(normalized_id, [])
    _safe_log("build_component_page", component_id=normalized_id, theme=selected_tokens["theme"], title=validated_title)

    html = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{validated_title}</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, sans-serif;
      --bg: {selected_tokens['tokens']['background']};
      --surface: {selected_tokens['tokens']['surface']};
      --text: {selected_tokens['tokens']['text']};
      --muted: {selected_tokens['tokens']['muted']};
      --primary: {selected_tokens['tokens']['primary']};
      --secondary: {selected_tokens['tokens']['secondary']};
      --radius: {selected_tokens['tokens']['radius']};
      --shadow: {selected_tokens['tokens']['shadow']};
    }}

    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 2rem;
      background: radial-gradient(circle at top left, rgba(20, 184, 166, 0.2), transparent 36%),
                  linear-gradient(180deg, var(--bg), #ffffff);
      color: var(--text);
    }}

    .demo-shell {{
      width: min(100%, 56rem);
      display: grid;
      gap: 1.25rem;
    }}

    .demo-shell__meta {{
      display: flex;
      gap: 0.75rem;
      flex-wrap: wrap;
      margin-top: 0.75rem;
    }}

    .demo-shell__chip {{
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.4rem 0.7rem;
      border-radius: 999px;
      background: var(--surface);
      border: 1px solid rgba(15, 23, 42, 0.08);
      color: var(--muted);
      font-size: 0.85rem;
      box-shadow: var(--shadow);
    }}

    .demo-shell__header h1 {{
      margin: 0;
      font-size: clamp(2rem, 4vw, 3.25rem);
      line-height: 1.05;
    }}

    .demo-shell__header p {{
      max-width: 44rem;
      margin: 0.75rem 0 0;
      color: var(--muted);
      line-height: 1.7;
    }}

    .demo-shell__notes {{
      display: grid;
      gap: 0.75rem;
      padding: 1rem 1.1rem;
      border-radius: var(--radius);
      border: 1px solid rgba(15, 23, 42, 0.08);
      background: var(--surface);
      box-shadow: var(--shadow);
    }}

    .demo-shell__notes strong {{
      color: var(--primary);
    }}

    .demo-shell__notes ul {{
      margin: 0;
      padding-left: 1.2rem;
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <main class=\"demo-shell\">
    <section class=\"demo-shell__header\">
      <h1>{validated_title}</h1>
      <p>{component["purpose"]}</p>
      <div class=\"demo-shell__meta\">
        <span class=\"demo-shell__chip\">Theme: {selected_tokens['theme']}</span>
        <span class=\"demo-shell__chip\">Variant: {component['variant']}</span>
        <span class=\"demo-shell__chip\">Outline: {len(outline)} parts</span>
      </div>
    </section>
    <section>
      {component["html"]}
    </section>
    <section class=\"demo-shell__notes\">
      <strong>Component outline</strong>
      <ul>
        {''.join(f'<li>{item}</li>' for item in outline)}
      </ul>
    </section>
  </main>
  <script>
{component["js"]}
  </script>
</body>
</html>"""

    return {
        "html": html,
        "css": component["css"],
        "js": component["js"],
        "theme": selected_tokens["theme"],
        "outline": outline,
    }


@mcp.tool(
  title="Build Component Story Page",
  description="Return a richer HTML story page that combines one component, one theme, and one documentation topic. Use this when you want a fuller design review page instead of a plain preview.",
  annotations=READ_ONLY_TOOL_ANNOTATIONS,
)
def build_component_story_page(component_id: str, theme: str = "ocean", topic: str = "overview", title: str = "Design Story") -> dict[str, Any]:
    """Return a story page that combines a component, theme, outline, and documentation.

    Use this when you want a richer design review page instead of a plain component preview.
    """
    normalized_id, error = _validate_catalog_identifier(
      "component_id",
      component_id,
      COMPONENT_ORDER,
      next_step="Use list_components() or search_components() to find a valid component id.",
    )
    if error:
      return error

    validated_title, error = _validate_non_empty_text("title", title, max_length=MAX_TITLE_LENGTH)
    if error:
      return error

    normalized_topic, error = _validate_catalog_identifier(
      "topic",
      topic,
      sorted(DOCUMENTATION_TOPICS.keys()),
      next_step="Try the overview, html, css, javascript, accessibility, or composition topic.",
    )
    if error:
      return error

    assert normalized_id is not None
    assert validated_title is not None
    assert normalized_topic is not None
    component = _get_component(normalized_id)
    if not component:
        return _component_error(component_id)

    selected_tokens = get_design_tokens(theme)
    if "error" in selected_tokens:
        return selected_tokens

    documentation = DOCUMENTATION_TOPICS.get(normalized_topic)
    if not documentation:
        return _documentation_error(topic)

    outline = COMPONENT_OUTLINES.get(normalized_id, [])
    preview = build_component_page(normalized_id, title=f"{validated_title}: {component['name']}", theme=theme)
    _safe_log("build_component_story_page", component_id=normalized_id, theme=selected_tokens["theme"], topic=normalized_topic, title=validated_title)

    html = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{validated_title} - {component['name']}</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, sans-serif;
      --bg: {selected_tokens['tokens']['background']};
      --surface: {selected_tokens['tokens']['surface']};
      --text: {selected_tokens['tokens']['text']};
      --muted: {selected_tokens['tokens']['muted']};
      --primary: {selected_tokens['tokens']['primary']};
      --secondary: {selected_tokens['tokens']['secondary']};
      --radius: {selected_tokens['tokens']['radius']};
      --shadow: {selected_tokens['tokens']['shadow']};
    }}

    body {{
      margin: 0;
      min-height: 100vh;
      padding: 2rem;
      background: linear-gradient(180deg, var(--bg), #ffffff);
      color: var(--text);
    }}

    .story-shell {{
      width: min(100%, 74rem);
      margin: 0 auto;
      display: grid;
      gap: 1.25rem;
    }}

    .story-hero, .story-card {{
      background: var(--surface);
      border: 1px solid rgba(15, 23, 42, 0.08);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 1.2rem;
    }}

    .story-hero h1 {{
      margin: 0;
      font-size: clamp(2rem, 4vw, 3.4rem);
      line-height: 1.05;
    }}

    .story-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      margin-top: 0.85rem;
    }}

    .story-meta span {{
      padding: 0.4rem 0.7rem;
      border-radius: 999px;
      background: rgba(15, 118, 110, 0.08);
      color: var(--primary);
      font-size: 0.86rem;
      font-weight: 700;
    }}

    .story-grid {{
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 1rem;
      align-items: start;
    }}

    .story-card h2 {{
      margin: 0 0 0.75rem;
      font-size: 1.15rem;
    }}

    .story-card p, .story-card li {{ color: var(--muted); line-height: 1.65; }}

    .story-card ul {{ margin: 0; padding-left: 1.2rem; }}

    .story-preview {{
      display: grid;
      gap: 0.8rem;
    }}

    .story-preview__frame {{
      padding: 1rem;
      border-radius: var(--radius);
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0.76));
      border: 1px solid rgba(15, 23, 42, 0.08);
      box-shadow: var(--shadow);
    }}

    {preview['css']}
  </style>
</head>
<body>
  <main class=\"story-shell\">
    <section class=\"story-hero\">
      <h1>{validated_title}: {component['name']}</h1>
      <p>{documentation['summary']}</p>
      <div class=\"story-meta\">
        <span>Theme: {selected_tokens['theme']}</span>
        <span>Topic: {normalized_topic}</span>
        <span>Variant: {component['variant']}</span>
        <span>Outline parts: {len(outline)}</span>
      </div>
    </section>

    <div class=\"story-grid\">
      <section class=\"story-card\">
        <h2>Why this works</h2>
        <ul>
          {''.join(f'<li>{item}</li>' for item in documentation['guidelines'])}
        </ul>
        <h2>Component outline</h2>
        <ul>
          {''.join(f'<li>{item}</li>' for item in outline)}
        </ul>
      </section>

      <aside class=\"story-preview\">
        <section class=\"story-card\">
          <h2>Preview data</h2>
          <p><strong>Prompt:</strong> {documentation['example_prompt']}</p>
          <p><strong>Outline:</strong> {', '.join(outline)}</p>
        </section>
        <section class=\"story-preview__frame\">
          {component['html']}
        </section>
      </aside>
    </div>
  </main>
  <script>
{preview['js']}
  </script>
</body>
</html>"""

    return {
        "html": html,
        "css": preview["css"],
        "js": preview["js"],
        "component_id": normalized_id,
        "theme": selected_tokens["theme"],
        "topic": normalized_topic,
        "outline": outline,
        "documentation": documentation,
    }

@mcp.resource("resource://accessibility-guidance")
def accessibility_guidance() -> dict[str, Any]:
  """Return accessibility guidance for the demo design system.

  Use this when you want to ensure your design demos are usable by everyone, including people with disabilities.
  """
  # Learning goal: this resource is intentionally an index. It demonstrates a
  # common MCP design choice for developers: keep the first response small,
  # discoverable, and explicit about where richer source material lives.
  resource = RESOURCE_CATALOG["accessibility-guidance"]
  references = _load_accessibility_guidance_references()

  return {
    "topic": resource["topic"],
    "title": resource["title"],
    "summary": f"{resource['summary']} This resource is the index; the guidance itself lives in the referenced files.",
    "guidelines": [
      "Open the keyboard navigation guide when the interaction flow depends on Tab order, skip links, or escape routes.",
      "Use the focus and feedback guide when states, confirmations, or dynamic updates need to stay visible and understandable.",
      "Check the readable content guide when labels, contrast, or supporting copy need a clarity pass.",
      "Reach for the forms and actions guide when fields, errors, or call-to-action labels need more precision.",
      "Use the inclusive layouts guide when zoom, mobile stacking, or composed surfaces start to strain the layout.",
    ],
    "example_prompt": resource["example_prompt"],
    "uri": resource["uri"],
    "kind": resource["kind"],
    "references": references,
    "joke": "Accessibility is a bit like good signage in a station: if nobody gets lost, the design has done its job.",
  }
  



def main() -> None:
  # A minimal entrypoint keeps local execution obvious for developers and for
  # VS Code MCP registrations that simply need a Python module to launch.
    mcp.run()


if __name__ == "__main__":
    main()