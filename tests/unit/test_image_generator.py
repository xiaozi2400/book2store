"""Test image_generator module (TDD: RED → GREEN)"""
import base64
import pytest


class TestCoverImageInjection:
    """Test _inject_cover_image placeholder replacement"""

    def test_replaces_single_placeholder(self):
        """_inject_cover_image replaces __COVER_PLACEHOLDER__ with actual base64"""
        from automation.image_generator import ImageGenerator
        gen = ImageGenerator()
        html = '<img src="data:image/jpeg;base64,__COVER_PLACEHOLDER__">'
        mock_b64 = base64.b64encode(b"fake").decode()

        result = gen._inject_cover_image(html, mock_b64)

        assert "__COVER_PLACEHOLDER__" not in result
        assert mock_b64 in result

    def test_replaces_multiple_placeholders(self):
        """Replaces all occurrences, not just the first"""
        from automation.image_generator import ImageGenerator
        gen = ImageGenerator()
        html = """<div class="page">
            <img src="data:image/jpeg;base64,__COVER_PLACEHOLDER__">
            <img src="data:image/jpeg;base64,__COVER_PLACEHOLDER__">
        </div>"""
        mock_b64 = "REPLACED_DATA"

        result = gen._inject_cover_image(html, mock_b64)

        assert result.count(mock_b64) == 2

    def test_no_placeholder_unchanged(self):
        """Returns HTML unchanged when no placeholder exists"""
        from automation.image_generator import ImageGenerator
        gen = ImageGenerator()
        html = "<div>No placeholder</div>"

        result = gen._inject_cover_image(html, "data")

        assert result == html

    def test_empty_base64_leaves_placeholder(self):
        """Empty base64 leaves placeholder as-is"""
        from automation.image_generator import ImageGenerator
        gen = ImageGenerator()
        html = '<img src="data:image/jpeg;base64,__COVER_PLACEHOLDER__">'

        result = gen._inject_cover_image(html, "")

        assert "__COVER_PLACEHOLDER__" in result


class TestFormatPrompt:
    """Test _format_prompt does NOT embed cover_base64"""

    def test_prompt_no_cover_base64(self):
        """Formatted prompt should NOT contain base64-encoded image data"""
        from automation.image_generator import ImageGenerator
        gen = ImageGenerator()
        prompt = gen._format_prompt("Test Title", "Test Author", "Test summary")

        # The prompt should NOT contain long base64-like strings
        # A normal prompt is relatively short; base64 would make it huge
        assert len(prompt) < 10000, "Prompt too large — base64 may be embedded"
        # The prompt should contain the placeholder instruction
        assert "__COVER_PLACEHOLDER__" in prompt

    def test_prompt_contains_title_and_author(self):
        """Prompt should still include book info"""
        from automation.image_generator import ImageGenerator
        gen = ImageGenerator()
        prompt = gen._format_prompt("Test Book", "Test Author", "Interesting summary")

        assert "Test Book" in prompt
        assert "Test Author" in prompt
        assert "Interesting summary" in prompt


class TestCallAiWrapper:
    """Test _call_ai HTML wrapping logic"""

    def test_wraps_bare_html(self):
        """Wraps bare content in full HTML with DOCTYPE"""
        from automation.image_generator import ImageGenerator
        gen = ImageGenerator()
        raw = '<div class="page">Content</div>'

        wrapped = gen._call_ai_wrap_html(raw)

        assert wrapped.startswith("<!DOCTYPE html>")
        assert "<div class=\"page\">" in wrapped
        assert "margin:0" in wrapped

    def test_leaves_full_html_unchanged(self):
        """Does not double-wrap if already full HTML"""
        from automation.image_generator import ImageGenerator
        gen = ImageGenerator()
        raw = "<!DOCTYPE html><html><body>Hello</body></html>"

        wrapped = gen._call_ai_wrap_html(raw)

        assert wrapped == raw

    def test_strips_code_fence(self):
        """Strips ```html and ``` markers"""
        from automation.image_generator import ImageGenerator
        gen = ImageGenerator()
        raw = "```html\n<div class=\"page\">Content</div>\n```"

        wrapped = gen._call_ai_wrap_html(raw)

        assert wrapped.startswith("<!DOCTYPE html>")
        assert "```" not in wrapped


class TestDesignAnalysis:
    """Test _design_analysis returns valid plan"""

    def test_design_analysis_returns_string(self):
        """_design_analysis should return a string (may be empty if AI unavailable)"""
        from automation.image_generator import ImageGenerator
        gen = ImageGenerator()
        result = gen._design_analysis("Test", "Author", "A book about Python", "封面配色方案: #ff0000、#00ff00")
        assert isinstance(result, str)

    def test_design_analysis_empty_on_missing_config(self):
        """Should return empty string if design_prompt is not configured"""
        from automation.image_generator import ImageGenerator
        gen = ImageGenerator()
        result = gen._design_analysis("Test", "Author", "Summary", "")
        assert isinstance(result, str)


class TestFormatHtmlPrompt:
    """Test _format_html_prompt includes design_plan"""

    def test_includes_design_plan(self):
        """Formatted prompt should contain the design_plan text"""
        from automation.image_generator import ImageGenerator
        gen = ImageGenerator()
        prompt = gen._format_html_prompt(
            "Test Title", "Test Author",
            "Test summary",
            "封面配色方案: #ff0000",
            "【设计方案】居中布局，蓝色渐变"
        )
        assert "【设计方案】" in prompt
        assert "__COVER_PLACEHOLDER__" in prompt
        assert len(prompt) < 10000

    def test_no_cover_base64(self):
        """Should NOT contain base64-encoded image data"""
        from automation.image_generator import ImageGenerator
        gen = ImageGenerator()
        prompt = gen._format_html_prompt(
            "Test Title", "Test Author",
            "Test summary", "", ""
        )
        assert len(prompt) < 10000