"""Integration test for main image generation"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import ebooklib
from ebooklib import epub

from automation.config import config
from automation.database import DatabaseManager
from automation.image import generate_main_image

# Find a book with summary_text
db = DatabaseManager()
books = db.get_all_books()
target_book = None
for b in books:
    if b.summary_text and b.status == "completed" and b.filename:
        target_book = b
        print(f"Found book: {b.id[:8]}")
        print(f"  filename: {b.filename}")
        print(f"  title: {b.title[:60]}")
        print(f"  summary_len: {len(b.summary_text)}")
        break

if not target_book:
    print("No book with summary_text found!")
    sys.exit(1)

base_name = Path(target_book.filename).stem
meta_dir = Path(config.output_dir) / f"{base_name}_metadata"
meta_dir.mkdir(parents=True, exist_ok=True)
cover_path = meta_dir / "cover.jpg"

# Try to find cover from EPUB (try multiple sources)
input_paths_to_try = [
    Path(config.input_dir) / target_book.filename,
    Path("E:/ebooks/input") / target_book.filename,
    Path("E:/ebooks") / target_book.filename,
]

found_cover = False
for epub_path in input_paths_to_try:
    if epub_path.exists():
        print(f"\nChecking EPUB: {epub_path}")
        book = epub.read_epub(str(epub_path))
        biggest_img = None
        biggest_size = 0
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_IMAGE:
                name_lower = item.get_name().lower()
                content = item.get_content()
                # Check for cover by name or largest image
                if "cover" in name_lower:
                    cover_path.write_bytes(content)
                    print(f"Found cover: {item.get_name()} ({len(content)} bytes)")
                    found_cover = True
                    break
                if len(content) > biggest_size:
                    biggest_size = len(content)
                    biggest_img = item
        if not found_cover and biggest_img:
            # Use largest image as cover
            content = biggest_img.get_content()
            cover_path.write_bytes(content)
            print(f"Using largest image as cover: {biggest_img.get_name()} ({len(content)} bytes)")
            found_cover = True
        if found_cover:
            break

if not found_cover:
    print(f"\nNo cover found, will generate text-only images")

# Delete old main images
deleted = 0
for f in meta_dir.glob("main_image_*.jpg"):
    f.unlink()
    deleted += 1
if deleted:
    print(f"Deleted {deleted} old image(s)")

# Run image generation
print("\n--- Running image generation ---")
import time
start = time.time()
result = generate_main_image(target_book.id)
elapsed = time.time() - start
print(f"Image generation result: {result} (took {elapsed:.1f}s)")

# Show results
print(f"\n--- Output files in {meta_dir} ---")
images = sorted(meta_dir.glob("main_image_*.jpg"))
for f in images:
    size_kb = f.stat().st_size / 1024
    print(f"  {f.name} ({size_kb:.1f} KB)")
print(f"\nTotal images generated: {len(images)}")
print(f"Cover existed: {cover_path.exists()} ({cover_path.stat().st_size} bytes)" if cover_path.exists() else "Cover existed: False")