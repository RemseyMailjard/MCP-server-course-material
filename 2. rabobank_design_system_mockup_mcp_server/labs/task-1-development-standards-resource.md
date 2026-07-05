# Task 1: Create a Design Guidance Resource

## Learning goal

In this exercise, you will learn how to expose static design knowledge through an MCP server. You will add a reusable resource that helps an AI client make better design decisions when generating or explaining UI output.

## Context

This MCP server already returns components, themes, and documentation topics. What is still missing is a single reusable resource that explains how to make good design choices across those outputs. In a real team, that kind of guidance helps keep generated UI consistent, reviewable, and aligned with a design system.

## Assignment

Create a resource called `design-guidance` and expose it through your MCP server.

The resource must contain practical design guidance that helps developers and AI clients choose the right structure, styling, and composition for UI output. At minimum, include guidance on:

- when to use a component such as a card, feature panel, button, or navbar
- how to combine components without losing hierarchy
- how to use token themes consistently
- what accessibility checks should always be considered

## What you should build

Your implementation should:

- define the guidance in a clear, structured format
- expose it as an MCP resource
- return content that is easy for both developers and AI clients to interpret
- make the resource discoverable through the server
- make it directly useful for prompts about components, themes, and page composition

## Recommended approach

Work through the task in these steps:

1. Choose a resource name and URI that clearly describe the design guidance.
2. Write the guidance in a consistent structure, for example as markdown or JSON.
3. Keep each rule short, specific, and actionable.
4. Make sure the guidance reflects the components and themes that already exist in this server.
5. Register the resource in your MCP server.
6. Test whether the resource can be retrieved successfully from an MCP client.

## Example structure

You may use a structure like this:

```md
# Design Guidance

## Component selection
- Use a button for a single clear action.
- Use a card for short summaries or grouped information.
- Use a feature panel when content needs hierarchy, explanation, and more than one action.
- Use a navbar only when the page contains multiple destinations or sections.

## Composition
- Keep one primary action per section.
- Combine components in a clear reading order: navigation, headline, content, action.
- Preserve enough whitespace between sections so the layout does not feel crowded.

## Token usage
- Apply one token theme consistently across the full page.
- Do not mix accents from different themes in the same component composition.
- Use tokens for colors, radius, and shadows instead of hardcoded one-off values.

## Accessibility checks
- Ensure interactive elements keep visible focus states.
- Check that text remains readable against the selected theme.
- Use descriptive labels for actions and links.
```

## Why this is a good resource exercise

This task is a better fit for learning resources because the content is stable reference material. It does not perform an action or calculate a result. Instead, it gives reusable design knowledge that an AI client can consult before choosing a component, combining layouts, or generating a preview page.

## Acceptance criteria

Your task is complete when:

- the MCP server exposes a resource named `design-guidance`
- the resource contains at least the four required guidance areas
- the guidance clearly relates to this design-oriented MCP server
- the content is concise, readable, and practically usable
- the resource can be retrieved without errors from the MCP server

## Stretch goal

If you finish early, extend the resource with one or two extra design topics, such as:

- motion guidance for subtle interaction feedback
- content density rules for dashboard-like layouts
- guidance for combining a navbar with a feature panel or card grid

## Reflection question

After implementing the task, explain in 2 to 3 sentences:

- why this information belongs in a resource rather than a tool
- how an AI client could use this resource before calling `get_component_bundle`, `get_design_tokens`, or `build_component_story_page`