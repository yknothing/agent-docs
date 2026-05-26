# Changelog

All notable changes to this project will be documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to semantic versioning once stable.

## [Unreleased]

### Added
- `npm run test:py` / `npm run lint:py` for Python unit tests and ruff lint.
- `LICENSE` (MIT) with non-commercial content notice for fetched third-party material.
- `pyproject.toml` declaring package metadata, Python `>=3.10`, console_scripts entry point, dev extras, and ruff/pytest config.
- `requirements-dev.txt` for dev tooling (pytest, ruff).
- `tests/` suite with high-ROI unit tests covering `feishu_folder_segments`, `parse_doc_id_from_output`, `parse_frontmatter`, `feishu_safe_name`, `pick_preferred_source_url`, `extract_images`, `PipelineLogger` sanitization, and the previously-inline Feishu path self-test.
- `skills/vendor-onboarding/SKILL.md` placeholder (Stage 2 planned).
- `CHANGELOG.md` (this file).
- ARCHITECTURE.md: `Known Limitations` section consolidating gaps documented across files.

### Changed
- `agent_docs/core/logging.py`: `PipelineLogger._sanitize` now scans string values for high-confidence secret patterns (Bearer tokens, OpenAI `sk-` keys, GitHub tokens, URL credential query params, common `authorization`/`x-api-key`/`app_secret` assignments) in addition to dropping dict keys whose name matches `LOG_SECRET_KEY_FRAGMENTS`.
- `agent_docs/core/config.py`: `UA` header now identifies the project (`agent-docs/<version> (+homepage)`).
- `agent_docs/__init__.py`: removed runtime `sys.path` mutation; preferred installation is `pip install -e ".[dev]"`. `scripts/anthropic_content_pipeline.py` still injects the repo root for backward compatibility with existing npm scripts.
- `agent_docs/ingest/media.py::extract_images`: removed dead `seen` set and consolidated dedup logic.
- `agent_docs/ingest/normalize.py`: removed unused `pathlib.Path` import.
- `.github/workflows/`: CI now runs `ruff`, `pytest`, `py_compile`, and the Feishu path self-test.
- `README.md`: clarified Stage 1 entry path (`anthropic:discover` first), reordered Quick Start, added non-commercial usage notice.
- `ARCHITECTURE.md`: removed stale `~1300 行` description; updated Extension Points table to reference `agent_docs.*` modules; added `Known Limitations` section.
- `EXPERIENCE.md`: added entry documenting this hardening pass.

### Removed
- `FEISHU_ALT_TEXT_MIN_LEN` / `FEISHU_ALT_TEXT_HINT_MAX_LEN` (unused dead config).

### Notes
- Crawl / QA / Feishu sync business logic unchanged. Intentional runtime deltas: HTTP `User-Agent`, `pipeline.log` secret scrubbing, `extract_images` empty-src skip, and package import path (prefer `pip install -e ".[dev]"`; npm wrapper still injects `sys.path`).
