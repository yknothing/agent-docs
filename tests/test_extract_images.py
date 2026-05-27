"""Tests for `agent_docs.ingest.media.extract_images` deduplication."""

from __future__ import annotations

from agent_docs.ingest.media import extract_images, infer_image_ext


class TestExtractImages:
    def test_extract_markdown_image(self) -> None:
        md = "hello ![alt](https://example.com/x.png) world"
        imgs = extract_images(md, "https://example.com")
        assert len(imgs) == 1
        src, marker = imgs[0]
        assert src == "https://example.com/x.png"
        assert marker == "![alt](https://example.com/x.png)"

    def test_extract_html_image(self) -> None:
        md = '<img src="https://example.com/y.png" alt="y">'
        imgs = extract_images(md, "https://example.com")
        assert len(imgs) == 1
        assert imgs[0][0] == "https://example.com/y.png"

    def test_dedup_same_url(self) -> None:
        md = "![a](https://example.com/x.png)\n\n![b](https://example.com/x.png)"
        imgs = extract_images(md, "https://example.com")
        # Same URL appears twice in source; dedup keeps only one.
        assert len(imgs) == 1

    def test_relative_url_resolved(self) -> None:
        md = "![rel](/static/img.png)"
        imgs = extract_images(md, "https://example.com/docs/page")
        assert imgs[0][0].startswith("https://example.com/")
        assert imgs[0][0].endswith("/static/img.png")

    def test_mixed_markdown_and_html(self) -> None:
        md = '![a](https://example.com/a.png) <img src="https://example.com/b.png">'
        imgs = extract_images(md, "https://example.com")
        srcs = {src for src, _ in imgs}
        assert srcs == {"https://example.com/a.png", "https://example.com/b.png"}

    def test_no_images(self) -> None:
        assert extract_images("plain text", "https://example.com") == []

    def test_html_image_src_with_line_break(self) -> None:
        md = "<img src='https://www-\ncdn.anthropic.com/static/images/foo.svg' alt='x'>"
        imgs = extract_images(md, "https://example.com")
        assert len(imgs) == 1
        assert imgs[0][0] == "https://www-cdn.anthropic.com/static/images/foo.svg"

    def test_markdown_image_url_with_line_break(self) -> None:
        md = "![alt](https://www-\ncdn.anthropic.com/static/images/foo.png)"
        imgs = extract_images(md, "https://example.com")
        assert len(imgs) == 1
        assert imgs[0][0] == "https://www-cdn.anthropic.com/static/images/foo.png"


class TestInferImageExt:
    def test_from_url_suffix(self) -> None:
        assert infer_image_ext("", "https://example.com/x.png") == ".png"
        assert infer_image_ext("", "https://example.com/x.JPG") == ".jpg"

    def test_from_content_type_image(self) -> None:
        assert infer_image_ext("image/png", "https://example.com/no-ext") == ".png"
        assert infer_image_ext("image/webp; charset=utf-8", "https://example.com") == ".webp"

    def test_svg_special(self) -> None:
        assert infer_image_ext("image/svg+xml", "https://example.com/x") == ".svg"

    def test_fallback_bin(self) -> None:
        assert infer_image_ext("application/octet-stream", "https://example.com/blob") == ".bin"
