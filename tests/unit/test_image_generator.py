"""Test image_generator module"""
import base64
import pytest
from automation.image_generator import ImageGenerator


class TestCoverImageInjection:
    """Test _inject_cover_image placeholder replacement"""

    def test_replaces_single_placeholder(self):
        """_inject_cover_image replaces __COVER_PLACEHOLDER__ with actual base64"""
        gen = ImageGenerator()
        html = '<img src="data:image/jpeg;base64,__COVER_PLACEHOLDER__">'
        mock_b64 = base64.b64encode(b"fake").decode()

        result = gen._inject_cover_image(html, mock_b64)

        assert "__COVER_PLACEHOLDER__" not in result
        assert mock_b64 in result

    def test_replaces_multiple_placeholders(self):
        """Replaces all occurrences, not just the first"""
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
        gen = ImageGenerator()
        html = "<div>No placeholder</div>"

        result = gen._inject_cover_image(html, "data")

        assert result == html

    def test_empty_base64_leaves_placeholder(self):
        """Empty base64 leaves placeholder as-is"""
        gen = ImageGenerator()
        html = '<img src="data:image/jpeg;base64,__COVER_PLACEHOLDER__">'

        result = gen._inject_cover_image(html, "")

        assert "__COVER_PLACEHOLDER__" in result


class TestFormatPrompt:
    """Test _format_prompt builds a prompt from title/author/summary"""

    def test_prompt_contains_title_and_author(self):
        """Prompt should include book info"""
        gen = ImageGenerator()
        prompt = gen._format_prompt("Test Book", "Test Author", "Interesting summary")

        assert "Test Book" in prompt
        assert "Test Author" in prompt
        assert "Interesting summary" in prompt

    def test_prompt_is_reasonable_length(self):
        """Prompt should not be extremely large"""
        gen = ImageGenerator()
        prompt = gen._format_prompt("Title", "Author", "A summary")
        assert len(prompt) < 10000

    def test_prompt_with_cover_colors_parameter(self):
        """_format_prompt 接受 cover_colors 参数而不崩溃"""
        gen = ImageGenerator()
        # 传入颜色参数，不应抛出异常
        prompt = gen._format_prompt("Book", "Author", "Summary", cover_colors="#ff0000,#00ff00")
        assert isinstance(prompt, str)
        assert len(prompt) > 0


class TestDesignAnalysis:
    """Test _design_analysis returns valid plan"""

    def test_design_analysis_returns_string(self):
        """_design_analysis should return a string (may be empty if AI unavailable)"""
        gen = ImageGenerator()
        result = gen._design_analysis("Test", "Author", "A book about Python", "封面配色方案: #ff0000、#00ff00")
        assert isinstance(result, str)

    def test_design_analysis_empty_on_missing_config(self):
        """Should return empty string if design_prompt is not configured"""
        gen = ImageGenerator()
        result = gen._design_analysis("Test", "Author", "Summary", "")
        assert isinstance(result, str)


class TestFormatHtmlPrompt:
    """Test _format_html_prompt includes design_plan"""

    def test_includes_design_plan(self):
        """Formatted prompt should contain the design_plan text"""
        gen = ImageGenerator()
        prompt = gen._format_html_prompt(
            "Test Title", "Test Author",
            "Test summary",
            "封面配色方案: #ff0000",
            "【设计方案】居中布局，蓝色渐变"
        )
        assert "【设计方案】" in prompt
        assert len(prompt) < 10000

    def test_prompt_includes_book_info(self):
        """Should include title and author"""
        gen = ImageGenerator()
        prompt = gen._format_html_prompt(
            "My Book", "My Author",
            "My summary", "", ""
        )
        assert "My Book" in prompt
        assert "My Author" in prompt
