"""Smoke tests for the knowledge-bank MCP server logic."""

import pytest

import server


def test_lists_all_markdown_files():
    files = server._list()
    assert "index.md" in files
    assert "work/current-projects.md" in files
    assert all(file.endswith(".md") for file in files)


def test_reads_a_known_file():
    content = server._read("work/current-projects.md")
    assert "# Active projects" in content


def test_search_finds_okf():
    hits = server._search("OKF")
    assert any(h["file"] == "references/okf-principles.md" for h in hits)


def test_path_traversal_is_blocked():
    with pytest.raises(ValueError):
        server._read("../../etc/passwd")


def test_non_markdown_is_rejected():
    with pytest.raises(ValueError):
        server._read("../pyproject.toml")


def test_lists_frontmatter_tags_and_types():
    assert "template" in server._list_tags()
    assert "Template" in server._list_types()


def test_search_metadata_filters_by_tag_and_folder():
    hits = server._search_metadata(tag="template", folder="templates")
    assert any(hit["file"] == "templates/weekly-review-template.md" for hit in hits)


def test_knowledge_map_groups_files_by_folder():
    knowledge_map = server._knowledge_map()
    assert "work" in knowledge_map
    assert any(item["file"] == "work/current-projects.md" for item in knowledge_map["work"])


def test_validation_reports_current_bank_status():
    result = server._validate_knowledge_bank()
    assert result["valid"] is True
    assert result["errors"] == []


def test_frontmatter_parser_supports_yaml_timestamps():
    metadata = server._metadata_for(server.KB_ROOT / "work" / "current-projects.md")
    assert metadata["timestamp"]
    assert "work" in metadata["tags"]


def test_project_context_bundle_includes_work_notes():
    bundle = server._context_bundle("project")
    files = [item["file"] for item in bundle["files"]]
    assert "work/current-projects.md" in files
    assert "work/ways-of-working.md" in files


def test_link_graph_finds_outgoing_links_and_backlinks():
    outgoing = server._list_outgoing_links("learning/learning-plan.md")
    assert any(link["target"] == "learning/cloud-and-azure.md" for link in outgoing)

    backlinks = server._find_backlinks("learning/learning-plan.md")
    assert any(backlink["source"] == "learning/index.md" for backlink in backlinks)


def test_related_notes_include_link_or_tag_reasons():
    related = server._find_related_notes("learning/learning-plan.md")
    assert related["file"] == "learning/learning-plan.md"
    assert any(item["reasons"] for item in related["related"])


def test_find_orphan_notes_returns_metadata():
    orphans = server._find_orphan_notes()
    assert all("file" in note and "title" in note for note in orphans)


def test_goal_alignment_context_and_signals():
    context = server._goal_alignment_context("career growth")
    files = [item["file"] for item in context["files"]]
    assert "goals/career-growth.md" in files

    signals = server._check_goal_alignment("career growth")
    assert "context_files" in signals


def test_recent_notes_are_timestamp_ordered():
    recent = server._list_recent_notes(limit=3)
    assert len(recent) == 3
    assert all("timestamp" in note for note in recent)


def test_find_stale_notes_uses_frontmatter_timestamp(tmp_path, monkeypatch):
    old_note = tmp_path / "old.md"
    old_note.write_text(
        "---\ntype: Note\ntitle: Old\ndescription: Old note\ntags: [note]\ntimestamp: 2020-01-01T00:00:00Z\n---\n\n# Old\n",
        encoding="utf-8",
    )
    fresh_note = tmp_path / "fresh.md"
    fresh_note.write_text(
        "---\ntype: Note\ntitle: Fresh\ndescription: Fresh note\ntags: [note]\ntimestamp: 2999-01-01T00:00:00Z\n---\n\n# Fresh\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "KB_ROOT", tmp_path.resolve())

    stale = server._find_stale_notes(days_old=90)

    assert [note["file"] for note in stale] == ["old.md"]


def test_find_placeholder_text_reports_unfinished_lines(tmp_path, monkeypatch):
    note = tmp_path / "note.md"
    note.write_text("# Note\n\n- \n\nTODO: finish this\n", encoding="utf-8")
    monkeypatch.setattr(server, "KB_ROOT", tmp_path.resolve())

    findings = server._find_placeholder_text()

    assert any(finding["text"] == "TODO: finish this" for finding in findings)
    assert any(finding["text"] == "-" for finding in findings)


def test_validate_index_coverage_finds_missing_links(tmp_path, monkeypatch):
    folder = tmp_path / "work"
    folder.mkdir()
    (folder / "index.md").write_text("# Work\n", encoding="utf-8")
    (folder / "current-projects.md").write_text("# Current projects\n", encoding="utf-8")
    monkeypatch.setattr(server, "KB_ROOT", tmp_path.resolve())

    result = server._validate_index_coverage()

    assert result["valid"] is False
    assert result["errors"] == ["work/index.md: missing link to work/current-projects.md"]


def test_validate_index_coverage_accepts_linked_notes(tmp_path, monkeypatch):
    folder = tmp_path / "work"
    folder.mkdir()
    (folder / "index.md").write_text("# Work\n\n- [Current projects](current-projects.md)\n", encoding="utf-8")
    (folder / "current-projects.md").write_text("# Current projects\n", encoding="utf-8")
    monkeypatch.setattr(server, "KB_ROOT", tmp_path.resolve())

    result = server._validate_index_coverage()

    assert result["valid"] is True
    assert result["checked_indexes"] == ["work/index.md"]


def test_learning_context_includes_learning_materials():
    context = server._learning_context("backend")
    files = [item["file"] for item in context["files"]]
    assert "templates/learning-note-template.md" in files
    assert "learning/learning-plan.md" in files
    assert "work/tech-stack.md" in files


def test_capture_inbox_note_creates_frontmatter_safe_inbox(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "KB_ROOT", tmp_path.resolve())

    result = server._capture_inbox_note("Idea for a refactor", "meeting", ["idea"])
    content = (tmp_path / "inbox.md").read_text(encoding="utf-8")

    assert result["file"] == "inbox.md"
    assert "type: Inbox" in content
    assert "Idea for a refactor" in content
    assert server._validate_knowledge_bank()["valid"] is True


def test_template_listing_and_preview_do_not_write(tmp_path, monkeypatch):
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "learning-note-template.md").write_text(
        "---\ntype: Template\ntitle: Learning note template\ndescription: Demo\ntags: [template]\ntimestamp: 2026-06-17T00:00:00Z\n---\n\n# Old title\n\nBody",
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "KB_ROOT", tmp_path.resolve())

    templates_list = server._list_templates()
    preview = server._preview_note_from_template(
        "learning-note-template",
        "Previewed Note",
        "learning/previewed-note.md",
    )

    assert templates_list[0]["file"] == "templates/learning-note-template.md"
    assert preview["content"].count("# Previewed Note") == 1
    assert not (tmp_path / "learning" / "previewed-note.md").exists()


def test_append_to_log_writes_only_log_file(tmp_path, monkeypatch):
    (tmp_path / "log.md").write_text("# Log\n", encoding="utf-8")
    monkeypatch.setattr(server, "KB_ROOT", tmp_path.resolve())

    result = server._append_to_log("- captured insight", "Test entry")

    assert result["file"] == "log.md"
    assert "Test entry" in (tmp_path / "log.md").read_text(encoding="utf-8")
    assert "captured insight" in (tmp_path / "log.md").read_text(encoding="utf-8")


def test_create_note_from_template_creates_markdown_inside_bank(tmp_path, monkeypatch):
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "learning-note-template.md").write_text("# Old title\n\nBody", encoding="utf-8")
    monkeypatch.setattr(server, "KB_ROOT", tmp_path.resolve())

    result = server._create_note_from_template(
        "learning-note-template",
        "learning/copilot-finance.md",
        "Copilot Finance",
    )

    created = tmp_path / "learning" / "copilot-finance.md"
    assert result["file"] == "learning/copilot-finance.md"
    assert created.read_text(encoding="utf-8").startswith("# Copilot Finance")


def test_create_note_from_template_refuses_path_traversal(tmp_path, monkeypatch):
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "decision-template.md").write_text("# Old title\n", encoding="utf-8")
    monkeypatch.setattr(server, "KB_ROOT", tmp_path.resolve())

    with pytest.raises(ValueError):
        server._create_note_from_template("decision-template", "../outside.md", "Nope")


def test_specific_create_helpers_choose_safe_default_paths(tmp_path, monkeypatch):
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "learning-note-template.md").write_text("# Old title\n", encoding="utf-8")
    (templates / "project-brief-template.md").write_text("# Old title\n", encoding="utf-8")
    (templates / "decision-template.md").write_text("# Old title\n", encoding="utf-8")
    monkeypatch.setattr(server, "KB_ROOT", tmp_path.resolve())

    learning = server._create_learning_note("Power Automate Basics")
    project = server._create_project_note("Contoso Portal")
    decision = server._create_decision_note("Accept Managed Services")

    assert learning["file"] == "learning/power-automate-basics.md"
    assert project["file"] == "work/contoso-portal.md"
    assert decision["file"] == "decisions/accept-managed-services.md"
