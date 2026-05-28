import os
import sys
import tempfile
import zipfile
import shutil
import re
from pathlib import Path
from collections import defaultdict

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from bs4 import XMLParsedAsHTMLWarning
import warnings

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class EPUBSplitter:
    def __init__(self, epub_path: str):
        self.epub_path = epub_path
        self.book = None
        self.doc_items = []
        self.resource_items = []
        self.metadata = {}
        self._item_map = {}

    def analyze(self) -> dict:
        self.book = epub.read_epub(self.epub_path)
        self._extract_items()
        self._extract_metadata()
        return {
            'title': self.metadata.get('title', ''),
            'author': self.metadata.get('author', ''),
            'doc_count': len(self.doc_items),
            'resource_count': len(self.resource_items),
        }

    def _extract_items(self):
        self.doc_items = []
        self.resource_items = []
        self._item_map = {}
        for item in self.book.get_items():
            self._item_map[item.get_name()] = item
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                self.doc_items.append(item)
            else:
                self.resource_items.append(item)

    def _extract_metadata(self):
        title_data = self.book.get_metadata('DC', 'title')
        self.metadata['title'] = title_data[0][0] if title_data else 'Unknown'

        author_data = self.book.get_metadata('DC', 'creator')
        self.metadata['author'] = author_data[0][0] if author_data else 'Unknown'

        lang_data = self.book.get_metadata('DC', 'language')
        self.metadata['language'] = lang_data[0][0] if lang_data else 'en'

        self.metadata['identifier'] = getattr(self.book, 'id', 'unknown')

    def _find_opf_path(self, extracted_dir):
        for root, dirs, files in os.walk(extracted_dir):
            for f in files:
                if f.endswith('.opf'):
                    return os.path.join(root, f)
        return None

    def _find_content_dir(self, extracted_dir):
        opf = self._find_opf_path(extracted_dir)
        if opf:
            return os.path.dirname(opf)
        return extracted_dir

    def _get_all_manifest_paths(self, extracted_dir, content_dir):
        all_paths = set()
        for root, dirs, files in os.walk(extracted_dir):
            for f in files:
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, extracted_dir)
                all_paths.add(rel_path)
        return all_paths

    def _build_zip_to_disk_map(self, extract_dir, content_dir_name, opf_rel):
        opf_path = os.path.join(extract_dir, opf_rel)
        name_to_zip_path = {}
        if os.path.exists(opf_path):
            try:
                with open(opf_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                soup = BeautifulSoup(content, 'lxml-xml')
                opf_base = os.path.dirname(opf_rel)
                for item in soup.find_all('item'):
                    href = item.get('href', '')
                    if href:
                        full_path = os.path.join(opf_base, href) if opf_base else href
                        full_path = os.path.normpath(full_path)
                        name_to_zip_path[href.split('/')[-1]] = full_path
            except:
                pass
        return name_to_zip_path

    def split(self, output_dir: str, num_parts: int = 10) -> list[str]:
        self.book = epub.read_epub(self.epub_path)
        self._extract_items()
        self._extract_metadata()

        if not self.doc_items:
            raise ValueError("No document items found in EPUB")

        groups = self._distribute_docs(num_parts)

        os.makedirs(output_dir, exist_ok=True)
        output_paths = []

        base_name = Path(self.epub_path).stem
        base_name = re.sub(r'[<>:"/\\|?*]', '_', base_name)

        with tempfile.TemporaryDirectory(prefix='epub_split_') as temp_base:
            extract_dir = os.path.join(temp_base, 'extracted')
            with zipfile.ZipFile(self.epub_path, 'r') as zf:
                zf.extractall(extract_dir)

            content_dir = self._find_content_dir(extract_dir)
            content_dir_name = os.path.basename(content_dir)
            opf_rel = os.path.relpath(self._find_opf_path(extract_dir), extract_dir)

            for i, group_indices in enumerate(groups):
                part_num = i + 1
                part_docs = [self.doc_items[idx] for idx in group_indices]
                if not part_docs:
                    continue

                output_name = f"{base_name}_part{part_num:02d}.epub"
                output_path = os.path.join(output_dir, output_name)

                self._create_part_from_extracted(
                    extract_dir,
                    content_dir,
                    content_dir_name,
                    opf_rel,
                    output_path,
                    part_docs,
                    part_num,
                    num_parts,
                )
                output_paths.append(output_path)

        return output_paths

    def _distribute_docs(self, num_parts: int) -> list[list[int]]:
        total_docs = len(self.doc_items)
        if total_docs == 0:
            return [[] for _ in range(num_parts)]

        base_count = total_docs // num_parts
        remainder = total_docs % num_parts

        groups = []
        idx = 0
        for i in range(num_parts):
            extra = 1 if i < remainder else 0
            count = base_count + extra
            group = list(range(idx, idx + count))
            idx += count
            groups.append(group)

        return groups

    def _create_part_from_extracted(self, extract_dir, content_dir, content_dir_name, opf_rel, output_path, part_docs, part_num, total_parts):
        new_epub_dir = tempfile.mkdtemp(prefix='epub_part_')
        try:
            zip_path_map = self._build_zip_to_disk_map(extract_dir, content_dir_name, opf_rel)
            doc_names = set()
            for d in part_docs:
                basename = d.get_name()
                zip_rel = zip_path_map.get(basename, os.path.join(content_dir_name, basename))
                doc_names.add(zip_rel)

            used_resources = self._collect_used_resources(part_docs)
            css_from_opf = self._get_css_files_from_opf(extract_dir, opf_rel)

            needed = set()
            needed.add(opf_rel)
            needed.add('mimetype')
            needed.add(os.path.join('META-INF', 'container.xml'))

            for name in doc_names:
                needed.add(name)

            doc_dir = content_dir
            for res in used_resources:
                res_path = os.path.normpath(os.path.join(doc_dir, res))
                res_rel = os.path.relpath(res_path, extract_dir)
                needed.add(res_rel)

            for res in css_from_opf:
                opf_base = os.path.dirname(opf_rel)
                res_path = os.path.normpath(os.path.join(opf_base, res)) if opf_base else res
                needed.add(res_path)

            for fname in needed:
                src = os.path.join(extract_dir, fname)
                dst = os.path.join(new_epub_dir, fname)
                if os.path.exists(src) and not os.path.isdir(src):
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)

            self._rewrite_opf(new_epub_dir, opf_rel, doc_names, part_num, total_parts)
            self._rewrite_nav(new_epub_dir, content_dir_name, doc_names)

            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(new_epub_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, new_epub_dir)
                        zf.write(file_path, arcname)
        finally:
            shutil.rmtree(new_epub_dir, ignore_errors=True)

    def _collect_used_resources(self, part_docs):
        used = set()
        for doc in part_docs:
            try:
                content = doc.get_content().decode('utf-8', errors='ignore')
                soup = BeautifulSoup(content, 'lxml')
                for img in soup.find_all('img'):
                    src = img.get('src', '')
                    if src:
                        used.add(src)
                for link in soup.find_all('link'):
                    href = link.get('href', '')
                    if href:
                        used.add(href)
            except:
                pass
        return used

    def _get_css_files_from_opf(self, extract_dir, opf_rel):
        css_files = []
        opf_path = os.path.join(extract_dir, opf_rel)
        if not os.path.exists(opf_path):
            return css_files
        try:
            with open(opf_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            soup = BeautifulSoup(content, 'lxml-xml')
            for item in soup.find_all('item'):
                media_type = item.get('media-type', '')
                href = item.get('href', '')
                if 'css' in media_type.lower() and href:
                    css_files.append(href)
        except:
            pass
        return css_files

    def _rewrite_opf(self, new_epub_dir, opf_rel, doc_names, part_num, total_parts):
        opf_path = os.path.join(new_epub_dir, opf_rel)
        if not os.path.exists(opf_path):
            return

        with open(opf_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        soup = BeautifulSoup(content, 'lxml-xml')

        manifest = soup.find('manifest')
        spine = soup.find('spine')

        doc_ids_in_manifest = set()
        opf_base = os.path.dirname(opf_rel)
        if manifest:
            for item in list(manifest.find_all('item')):
                href = item.get('href', '')
                href_full = os.path.normpath(os.path.join(opf_base, href)) if opf_base else href
                if href_full not in doc_names:
                    item.decompose()
                else:
                    doc_ids_in_manifest.add(item.get('id'))

        if spine:
            toc_attr = spine.get('toc', '')
            if toc_attr and toc_attr not in doc_ids_in_manifest:
                del spine['toc']

            for itemref in list(spine.find_all('itemref')):
                idref = itemref.get('idref', '')
                if idref:
                    found = idref in doc_ids_in_manifest
                    if not found:
                        itemref.decompose()

        dc_title = soup.find('dc:title')
        if dc_title and dc_title.string:
            dc_title.string = f"{self.metadata.get('title', 'Unknown')} - Part {part_num}/{total_parts}"

        with open(opf_path, 'w', encoding='utf-8') as f:
            f.write(str(soup))

    def _rewrite_nav(self, new_epub_dir, content_dir_name, doc_names):
        nav_path = None
        for root, dirs, files in os.walk(new_epub_dir):
            for fname in files:
                if 'nav' in fname.lower() and (fname.endswith('.xhtml') or fname.endswith('.html')):
                    nav_path = os.path.join(root, fname)
                    break
            if nav_path:
                break

        if not nav_path:
            return

        try:
            with open(nav_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            soup = BeautifulSoup(content, 'lxml')

            for li in list(soup.find_all('li')):
                a_tag = li.find('a')
                if not a_tag:
                    continue
                href = a_tag.get('href', '').split('#')[0].split('/')[-1]
                if href and href not in doc_names:
                    li.decompose()
                    continue

                for child_li in list(li.find_all('li')):
                    child_a = child_li.find('a')
                    if child_a:
                        child_href = child_a.get('href', '').split('#')[0].split('/')[-1]
                        if child_href and child_href not in doc_names:
                            child_li.decompose()

            with open(nav_path, 'w', encoding='utf-8') as f:
                f.write(str(soup))
        except:
            pass
