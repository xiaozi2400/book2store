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

    def _reorder_docs_by_spine(self):
        with zipfile.ZipFile(self.epub_path, 'r') as zf:
            container = BeautifulSoup(zf.read('META-INF/container.xml'), 'lxml-xml')
            rootfile = container.find('rootfile')
            if rootfile is None:
                return
            opf_path = rootfile.get('full-path', '')
            if not opf_path:
                return
            opf_soup = BeautifulSoup(zf.read(opf_path), 'lxml-xml')
            manifest = opf_soup.find('manifest')
            spine = opf_soup.find('spine')
            if manifest is None or spine is None:
                return
            href_by_id = {}
            for item in manifest.find_all('item'):
                item_id = item.get('id', '')
                href = item.get('href', '')
                if item_id and href:
                    href_by_id[item_id] = href
            doc_by_name = {d.get_name(): d for d in self.doc_items}
            ordered = []
            seen = set()
            for itemref in spine.find_all('itemref'):
                idref = itemref.get('idref', '')
                if idref and idref in href_by_id:
                    basename = os.path.basename(href_by_id[idref])
                    if basename in doc_by_name and basename not in seen:
                        ordered.append(doc_by_name[basename])
                        seen.add(basename)
            for d in self.doc_items:
                if d not in ordered:
                    ordered.append(d)
            self.doc_items = ordered

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

    def split(self, output_dir: str) -> list[str]:
        self.book = epub.read_epub(self.epub_path)
        self._extract_items()
        self._reorder_docs_by_spine()
        self._extract_metadata()

        nav_docs = [d for d in self.doc_items if 'nav' in d.get_name().lower()]
        body_docs = [d for d in self.doc_items if d not in nav_docs]

        cover_doc = body_docs[:1]
        content_only = body_docs[1:]

        total_bytes = sum(len(d.get_content()) for d in content_only)
        target_bytes = max(1, (total_bytes + 19) // 20)

        kept = []
        cum = 0
        for d in content_only:
            kept.append(d)
            cum += len(d.get_content())
            if cum >= target_bytes:
                break

        if not kept:
            kept = content_only[:1]

        self.doc_items = cover_doc + kept + nav_docs

        if not self.doc_items:
            raise ValueError("No document items found in EPUB")

        os.makedirs(output_dir, exist_ok=True)

        base_name = Path(self.epub_path).stem
        base_name = re.sub(r'[<>:"/\\|?*]', '_', base_name)

        with tempfile.TemporaryDirectory(prefix='epub_split_') as temp_base:
            extract_dir = os.path.join(temp_base, 'extracted')
            with zipfile.ZipFile(self.epub_path, 'r') as zf:
                zf.extractall(extract_dir)

            content_dir = self._find_content_dir(extract_dir)
            content_dir_name = os.path.basename(content_dir)
            opf_rel = os.path.relpath(self._find_opf_path(extract_dir), extract_dir)

            output_name = f"{base_name}.epub"
            output_path = os.path.join(output_dir, output_name)

            self._create_part_from_extracted(
                extract_dir,
                content_dir,
                content_dir_name,
                opf_rel,
                output_path,
                self.doc_items,
            )

        return [output_path]

    def _create_part_from_extracted(self, extract_dir, content_dir, content_dir_name, opf_rel, output_path, part_docs):
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

            self._rewrite_opf(new_epub_dir, opf_rel, doc_names)
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
                for svg_img in soup.find_all('image'):
                    href = svg_img.get('xlink:href', '') or svg_img.get('href', '')
                    if href:
                        used.add(href)
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

    def _rewrite_opf(self, new_epub_dir, opf_rel, doc_names):
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

            doc_basenames = set(os.path.basename(n) for n in doc_names)

            for li in list(soup.find_all('li')):
                a_tag = li.find('a')
                if not a_tag:
                    continue
                href = a_tag.get('href', '').split('#')[0].split('/')[-1]
                if href and href not in doc_basenames:
                    li.decompose()
                    continue

                for child_li in list(li.find_all('li')):
                    child_a = child_li.find('a')
                    if child_a:
                        child_href = child_a.get('href', '').split('#')[0].split('/')[-1]
                        if child_href and child_href not in doc_basenames:
                            child_li.decompose()

            with open(nav_path, 'w', encoding='utf-8') as f:
                f.write(str(soup))
        except:
            pass
