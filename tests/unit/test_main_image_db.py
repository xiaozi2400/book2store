"""测试 BookOutput 新增 main_image_count 字段"""

from automation.models import BookOutput


class TestMainImageCount:
    def test_book_output_has_main_image_count(self, in_memory_db, sample_book):
        output = BookOutput(book_id=sample_book.id)
        in_memory_db.add(output)
        in_memory_db.commit()
        in_memory_db.refresh(output)

        assert hasattr(output, "main_image_count")
        assert output.main_image_count == 0

    def test_update_main_image_count(self, in_memory_db, sample_book):
        output = BookOutput(book_id=sample_book.id)
        in_memory_db.add(output)
        in_memory_db.commit()

        output.main_image_count = 3
        in_memory_db.commit()
        in_memory_db.refresh(output)

        assert output.main_image_count == 3
