"""翻译质量检查模块"""
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

from .config import config
from .utils import logger


# ============================================================
# 数据模型
# ============================================================

@dataclass
class DimensionResult:
    """单维度检查结果"""
    score: float
    issues: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityReport:
    """质量检查报告"""
    book_title: str
    overall_score: float
    overall_grade: str
    dimensions: Dict[str, DimensionResult]
    summary: str
    recommendation: str

    def to_dict(self) -> Dict:
        result = {
            "book_title": self.book_title,
            "overall_score": self.overall_score,
            "overall_grade": self.overall_grade,
            "summary": self.summary,
            "recommendation": self.recommendation,
            "dimensions": {}
        }
        for dim_name, dim_result in self.dimensions.items():
            result["dimensions"][dim_name] = asdict(dim_result)
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ============================================================
# 维度 7：翻译完整性检查
# ============================================================

class CompletenessChecker:
    """检查翻译完整性——所有源段落是否都已成功翻译，无遗漏"""

    def check(self, cache_data: Dict, source_paragraphs: List[str]) -> Dict:
        if not source_paragraphs:
            return {
                "score": 100,
                "source_paragraphs": 0,
                "translated_paragraphs": 0,
                "missing_count": 0,
                "empty_paragraphs": 0,
                "issues": []
            }

        translated_count = 0
        empty_count = 0
        missing_paragraphs = []

        for para in source_paragraphs:
            found = False
            for cache_key, cache_entry in cache_data.items():
                if cache_entry.get("source", "").strip() == para.strip():
                    found = True
                    translated_text = cache_entry.get("translated", "").strip()
                    if translated_text:
                        translated_count += 1
                    else:
                        empty_count += 1
                    break
            if not found:
                missing_paragraphs.append(para[:50])

        total = len(source_paragraphs)
        missing_count = total - translated_count - empty_count
        ratio = (translated_count / total) if total > 0 else 1.0
        score = round(ratio * 100, 1)

        issues = []
        if missing_count > 0:
            issues.append(f"有 {missing_count} 个段落未翻译（共 {total} 段）")
        if empty_count > 0:
            issues.append(f"有 {empty_count} 个段落译文为空")

        return {
            "score": score,
            "source_paragraphs": total,
            "translated_paragraphs": translated_count,
            "missing_count": missing_count,
            "empty_paragraphs": empty_count,
            "issues": issues
        }


# ============================================================
# 维度 8：PDF 目录链接检查
# ============================================================

class PdfTocLinkChecker:
    """检查 PDF 目录链接——解析 TOC 树并验证每个链接目标页是否存在"""

    def check(self, pdf_path: str) -> Dict:
        if not pdf_path or not Path(pdf_path).exists():
            return {
                "score": 0,
                "toc_entries": 0,
                "valid_links": 0,
                "broken_links": 0,
                "issues": ["PDF 文件不存在"]
            }

        try:
            import fitz
        except ImportError:
            return {
                "score": 0,
                "toc_entries": 0,
                "valid_links": 0,
                "broken_links": 0,
                "issues": ["pymupdf 库未安装，无法检查 PDF 目录"]
            }

        try:
            doc = fitz.open(pdf_path)
            total_pages = doc.page_count
            toc = doc.get_toc()

            if not toc:
                doc.close()
                return {
                    "score": 0,
                    "toc_entries": 0,
                    "valid_links": 0,
                    "broken_links": 0,
                    "issues": ["PDF 没有目录结构"]
                }

            valid = 0
            broken = 0
            broken_items = []

            for item in toc:
                level = item[0]
                title = item[1]
                page = item[2]

                if isinstance(page, int) and 1 <= page <= total_pages:
                    valid += 1
                else:
                    broken += 1
                    broken_items.append(f"'{title}' 目标页 {page} 超出范围 (1-{total_pages})")

            doc.close()

            total = valid + broken
            score = round((valid / total) * 100, 1) if total > 0 else 0

            issues = []
            if broken > 0:
                issues.append(f"有 {broken} 个目录链接目标页不存在")
                issues.extend(broken_items[:5])

            return {
                "score": score,
                "toc_entries": total,
                "valid_links": valid,
                "broken_links": broken,
                "issues": issues
            }

        except Exception as e:
            return {
                "score": 0,
                "toc_entries": 0,
                "valid_links": 0,
                "broken_links": 0,
                "issues": [f"PDF 解析失败: {str(e)}"]
            }


class FidelityChecker:
    """维度 1：忠实度检查——基于长度比例评估翻译忠实度"""

    def check(self, cache_data: Dict, source_paragraphs: List[str]) -> Dict:
        if not source_paragraphs:
            return {"score": 100, "missing_count": 0, "empty_count": 0,
                    "avg_length_ratio": 0, "issues": []}

        total = len(source_paragraphs)
        missing_count = 0
        empty_count = 0
        length_ratios = []

        for para in source_paragraphs:
            found = False
            for entry in cache_data.values():
                if entry.get("source", "").strip() == para.strip():
                    found = True
                    translated = entry.get("translated", "").strip()
                    if not translated:
                        empty_count += 1
                    else:
                        src_len = len(para)
                        tgt_len = len(translated)
                        ratio = tgt_len / src_len if src_len > 0 else 1
                        length_ratios.append(min(ratio, 3.0))
                    break
            if not found:
                missing_count += 1

        translated_count = total - missing_count - empty_count
        avg_length_ratio = (sum(length_ratios) / len(length_ratios)
                            if length_ratios else 0)

        score_parts = []
        score_parts.append((translated_count / total) * 40)
        score_parts.append(max(0, 30 - (empty_count / total) * 30))
        if length_ratios:
            ratio_score = min(30, (avg_length_ratio / 0.45) * 30)
            score_parts.append(ratio_score)
        else:
            score_parts.append(0)

        score = round(min(100, sum(score_parts)), 1)
        issues = []
        if missing_count > 0:
            issues.append(f"有 {missing_count}/{total} 个段落缺失翻译")
        if empty_count > 0:
            issues.append(f"有 {empty_count} 个段落译文为空")
        if length_ratios and (avg_length_ratio < 0.5 or avg_length_ratio > 3.0):
            issues.append(f"译文/原文长度比例异常: {avg_length_ratio:.2f}")

        return {
            "score": score, "missing_count": missing_count,
            "empty_count": empty_count, "avg_length_ratio": round(avg_length_ratio, 2),
            "issues": issues
        }


class FluencyChecker:
    """维度 2：流畅度检查——基于中文密度和遗留英文检测"""

    ENGLISH_WORD_PATTERN = re.compile(r'\b[a-zA-Z]{2,}\b')
    CHINESE_CHAR_PATTERN = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef]')

    def check(self, translated_text: str) -> Dict:
        if not translated_text or not translated_text.strip():
            return {"score": 100, "chinese_ratio": 1.0,
                    "english_word_count": 0, "issues": []}

        text = translated_text.strip()
        total_chars = len(text)
        chinese_chars = len(self.CHINESE_CHAR_PATTERN.findall(text))
        english_words = self.ENGLISH_WORD_PATTERN.findall(text)

        english_words = [w for w in english_words
                         if not w.startswith(('http', 'www'))]
        english_word_count = len(english_words)
        chinese_ratio = chinese_chars / total_chars if total_chars > 0 else 0

        score_parts = []
        score_parts.append(min(50, chinese_ratio * 50))
        if chinese_ratio > 0:
            density = chinese_chars / max(1, total_chars - english_word_count * 5)
            score_parts.append(min(30, density * 30))
        score_parts.append(max(0, 20 - english_word_count * 5))

        score = round(min(100, sum(score_parts)), 1)
        issues = []
        if chinese_ratio < 0.5:
            issues.append(f"中文字符占比偏低: {chinese_ratio:.1%}")
        if english_word_count > 0:
            issues.append(f"发现 {english_word_count} 个遗留英文词汇: {english_words[:5]}")

        return {
            "score": score, "chinese_ratio": round(chinese_ratio, 4),
            "english_word_count": english_word_count, "issues": issues
        }


class ConsistencyChecker:
    """维度 3：一致性检查——通过缓存检测同一英文术语是否翻译一致"""

    def check(self, cache_data: Dict) -> Dict:
        if not cache_data:
            return {"score": 100, "total_terms": 0,
                    "inconsistent_terms": 0, "issues": []}

        source_groups = {}
        for entry in cache_data.values():
            source = entry.get("source", "").strip().lower()
            translated = entry.get("translated", "").strip()
            if source and translated:
                if source not in source_groups:
                    source_groups[source] = set()
                source_groups[source].add(translated)

        multi_occurrence = {k: v for k, v in source_groups.items() if len(v) > 1}
        inconsistent_sources = []

        for source, translations in multi_occurrence.items():
            if len(translations) > 1:
                inconsistent_sources.append({
                    "source": source,
                    "translations": list(translations)
                })

        inconsistent_count = len(inconsistent_sources)
        total_terms = len(source_groups)

        if total_terms == 0:
            return {"score": 100, "total_terms": 0,
                    "inconsistent_terms": 0, "issues": []}

        score = round(max(0, 100 - (inconsistent_count / total_terms) * 100), 1)
        issues = []
        if inconsistent_count > 0:
            items = [f"'{s['source']}'→{s['translations']}"
                     for s in inconsistent_sources[:3]]
            issues.append(f"有 {inconsistent_count} 个术语翻译不一致: {', '.join(items)}")

        return {
            "score": score, "total_terms": total_terms,
            "inconsistent_terms": inconsistent_count, "issues": issues
        }


class FormatIntegrityChecker:
    """维度 4：格式完整性检查——段落结构、标题、列表保留情况"""

    LIST_PATTERN = re.compile(r'^[\s]*[-*]\s|\d+[.)]\s')
    HEADING_PATTERN = re.compile(r'^#{1,6}\s|^[A-Z][^。！？\n]{0,30}$', re.MULTILINE)

    def check(self, source_paragraphs: List[str],
              translated_paragraphs: List[str]) -> Dict:
        if not source_paragraphs and not translated_paragraphs:
            return {"score": 100, "para_count_match": True,
                    "issues": []}

        source_count = len(source_paragraphs)
        trans_count = len(translated_paragraphs)
        para_count_match = source_count == trans_count

        source_lists = sum(1 for p in source_paragraphs
                           if self.LIST_PATTERN.match(p))
        trans_lists = sum(1 for p in translated_paragraphs
                          if self.LIST_PATTERN.match(p))

        score_parts = []
        score_parts.append(40 if para_count_match else 0)
        if source_count > 0:
            match_ratio = min(source_count, trans_count) / max(source_count, 1)
            score_parts.append(match_ratio * 30)
        if source_lists > 0 or trans_lists > 0:
            list_ratio = min(source_lists, trans_lists) / max(source_lists, 1)
            score_parts.append(list_ratio * 30)
        else:
            score_parts.append(30)

        score = round(min(100, sum(score_parts)), 1)
        issues = []
        if not para_count_match:
            issues.append(f"段落数不匹配: 原文 {source_count} 段 ≠ 译文 {trans_count} 段")
        if source_lists != trans_lists:
            issues.append(f"列表项数不匹配: 原文 {source_lists} 个 ≠ 译文 {trans_lists} 个")

        return {
            "score": score, "para_count_match": para_count_match,
            "source_paragraphs": source_count, "translated_paragraphs": trans_count,
            "source_lists": source_lists, "translated_lists": trans_lists,
            "issues": issues
        }


class TerminologyChecker:
    """维度 5：术语准确性检查——预置术语库匹配"""

    TERM_DICT = {
        "api": "API",
        "database": "数据库",
        "server": "服务器",
        "client": "客户端",
        "interface": "接口",
        "module": "模块",
        "configuration": "配置",
        "function": "函数",
        "algorithm": "算法",
        "protocol": "协议",
        "authentication": "认证",
        "authorization": "授权",
    }

    def check(self, cache_data: Dict) -> Dict:
        if not cache_data:
            return {"score": 100, "total_terms": 0,
                    "matched_count": 0, "incorrect_count": 0, "issues": []}

        correct = 0
        incorrect = 0
        incorrect_items = []
        total = 0

        for entry in cache_data.values():
            source = entry.get("source", "").strip().lower()
            translated = entry.get("translated", "").strip().lower()
            if source in self.TERM_DICT and translated:
                total += 1
                expected = self.TERM_DICT[source]
                if expected.lower() in translated or translated in expected.lower():
                    correct += 1
                else:
                    incorrect += 1
                    incorrect_items.append(f"'{source}'→'{translated}' (期望: '{expected}')")

        if total == 0:
            return {"score": 100, "total_terms": 0,
                    "matched_count": 0, "incorrect_count": 0, "issues": []}

        score = round((correct / total) * 100, 1)
        issues = []
        if incorrect > 0:
            issues.append(f"有 {incorrect}/{total} 个术语翻译不准确: {'; '.join(incorrect_items[:3])}")

        return {
            "score": score, "total_terms": total,
            "matched_count": correct, "incorrect_count": incorrect,
            "issues": issues
        }


class CulturalAdaptationChecker:
    """维度 6：文化适配检查——日期格式、度量衡、货币符号检测"""

    WESTERN_DATE = re.compile(
        r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'
    )
    IMPERIAL_UNITS = re.compile(
        r'\b\d+\.?\d*\s*(inches?|inch|feet|foot|ft|pounds?|lbs?|'
        r'miles?|yards?|ounces?|oz|gallons?|gals?|fahrenheit|°f)\b',
        re.IGNORECASE
    )
    WESTERN_CURRENCY = re.compile(r'[\$€£¥]')

    def check(self, translated_text: str) -> Dict:
        if not translated_text or not translated_text.strip():
            return {"score": 100, "western_date_count": 0,
                    "imperial_units": 0, "western_currency": 0, "issues": []}

        text = translated_text.strip()
        western_dates = self.WESTERN_DATE.findall(text)
        imperial_units = self.IMPERIAL_UNITS.findall(text)
        western_currency = self.WESTERN_CURRENCY.findall(text)

        western_date_count = len(western_dates)
        imperial_count = len(imperial_units)
        currency_count = len(western_currency)
        total_issues = western_date_count + imperial_count + currency_count

        score = round(max(0, 100 - total_issues * 20), 1)
        issues = []
        if western_date_count > 0:
            issues.append(f"发现 {western_date_count} 处西式日期格式，建议改为中文格式")
        if imperial_count > 0:
            issues.append(f"发现 {imperial_count} 处英制度量衡，建议适配公制单位")
        if currency_count > 0:
            issues.append(f"发现 {currency_count} 处西式货币符号")

        return {
            "score": score, "western_date_count": western_date_count,
            "imperial_units": imperial_count, "western_currency": currency_count,
            "issues": issues
        }


class QualityChecker:
    """翻译质量检查主类——协调各维度检查并生成报告"""

    def __init__(self):
        self.enabled = config.get_quality_check_enabled()
        # 维度 1-6：程序化检查器
        self.fidelity_checker = FidelityChecker()
        self.fluency_checker = FluencyChecker()
        self.consistency_checker = ConsistencyChecker()
        self.format_checker = FormatIntegrityChecker()
        self.terminology_checker = TerminologyChecker()
        self.cultural_checker = CulturalAdaptationChecker()
        # 维度 7-8
        self.completeness_checker = CompletenessChecker()
        self.pdf_toc_checker = PdfTocLinkChecker()

    def check(self, book_title: str, book_id: str, output_dir: str,
              bilingual_pdf_path: Optional[str] = None,
              chinese_pdf_path: Optional[str] = None,
              cache_data: Optional[Dict] = None,
              source_paragraphs: Optional[List[str]] = None,
              translated_paragraphs: Optional[List[str]] = None) -> QualityReport:
        """执行全维度质量检查"""
        dimensions = {}
        all_scores = []

        # 维度 1：忠实度
        if cache_data is not None and source_paragraphs is not None:
            fidelity_result = self.fidelity_checker.check(cache_data, source_paragraphs)
            dimensions["fidelity"] = DimensionResult(
                score=fidelity_result["score"],
                issues=fidelity_result["issues"],
                details={
                    "missing_count": fidelity_result["missing_count"],
                    "empty_count": fidelity_result["empty_count"],
                    "avg_length_ratio": fidelity_result["avg_length_ratio"]
                }
            )
            all_scores.append(fidelity_result["score"])

        # 维度 2：流畅度
        if translated_paragraphs:
            full_text = "\n".join(translated_paragraphs)
            fluency_result = self.fluency_checker.check(full_text)
            dimensions["fluency"] = DimensionResult(
                score=fluency_result["score"],
                issues=fluency_result["issues"],
                details={
                    "chinese_ratio": fluency_result["chinese_ratio"],
                    "english_word_count": fluency_result["english_word_count"]
                }
            )
            all_scores.append(fluency_result["score"])

        # 维度 3：一致性
        if cache_data:
            consistency_result = self.consistency_checker.check(cache_data)
            dimensions["consistency"] = DimensionResult(
                score=consistency_result["score"],
                issues=consistency_result["issues"],
                details={
                    "total_terms": consistency_result["total_terms"],
                    "inconsistent_terms": consistency_result["inconsistent_terms"]
                }
            )
            all_scores.append(consistency_result["score"])

        # 维度 4：格式完整性
        if source_paragraphs is not None and translated_paragraphs is not None:
            format_result = self.format_checker.check(source_paragraphs, translated_paragraphs)
            dimensions["format"] = DimensionResult(
                score=format_result["score"],
                issues=format_result["issues"],
                details={
                    "para_count_match": format_result["para_count_match"],
                    "source_paragraphs": format_result["source_paragraphs"],
                    "translated_paragraphs": format_result["translated_paragraphs"]
                }
            )
            all_scores.append(format_result["score"])

        # 维度 5：术语准确性
        if cache_data:
            term_result = self.terminology_checker.check(cache_data)
            dimensions["terminology"] = DimensionResult(
                score=term_result["score"],
                issues=term_result["issues"],
                details={
                    "matched_count": term_result["matched_count"],
                    "incorrect_count": term_result["incorrect_count"]
                }
            )
            all_scores.append(term_result["score"])

        # 维度 6：文化适配
        if translated_paragraphs:
            full_text = "\n".join(translated_paragraphs)
            cultural_result = self.cultural_checker.check(full_text)
            dimensions["cultural"] = DimensionResult(
                score=cultural_result["score"],
                issues=cultural_result["issues"],
                details={
                    "western_date_count": cultural_result["western_date_count"],
                    "imperial_units": cultural_result["imperial_units"]
                }
            )
            all_scores.append(cultural_result["score"])

        # 维度 7：翻译完整性
        if cache_data is not None and source_paragraphs is not None:
            completeness_result = self.completeness_checker.check(
                cache_data, source_paragraphs
            )
            dimensions["completeness"] = DimensionResult(
                score=completeness_result["score"],
                issues=completeness_result["issues"],
                details={
                    "source_paragraphs": completeness_result["source_paragraphs"],
                    "translated_paragraphs": completeness_result["translated_paragraphs"],
                    "missing_count": completeness_result["missing_count"],
                    "empty_paragraphs": completeness_result["empty_paragraphs"]
                }
            )
            all_scores.append(completeness_result["score"])

        # 维度 8：PDF 目录链接检查
        pdf_paths = [p for p in [bilingual_pdf_path, chinese_pdf_path] if p]
        if pdf_paths:
            pdf_scores = []
            for pdf_path in pdf_paths:
                toc_result = self.pdf_toc_checker.check(pdf_path)
                pdf_scores.append(toc_result["score"])

            pdf_toc_details = {
                "checked_pdfs": pdf_paths,
                "scores_per_pdf": dict(zip(pdf_paths, pdf_scores))
            }
            avg_pdf_score = sum(pdf_scores) / len(pdf_scores) if pdf_scores else 0
            dimensions["pdf_toc_links"] = DimensionResult(
                score=avg_pdf_score,
                issues=[],
                details=pdf_toc_details
            )
            all_scores.append(avg_pdf_score)

        # 如果没有任何维度被评分，返回默认报告
        if not all_scores:
            return self._create_default_report(book_title, "无可用数据，无法完成质量评估")

        overall_score = self._calc_overall_score(dimensions)
        overall_grade = self._determine_grade(overall_score)

        # 生成总结和建议
        summary, recommendation = self._generate_summary_and_recommendation(
            overall_score, dimensions
        )

        return QualityReport(
            book_title=book_title,
            overall_score=overall_score,
            overall_grade=overall_grade,
            dimensions=dimensions,
            summary=summary,
            recommendation=recommendation
        )

    def _calc_overall_score(self, dimensions: Dict[str, "DimensionResult"]) -> float:
        """计算加权综合评分（目前等权平均）"""
        scores = [dim.score for dim in dimensions.values()]
        if not scores:
            return 0.0
        return round(sum(scores) / len(scores), 1)

    def _determine_grade(self, score: float) -> str:
        """根据分数确定等级"""
        excellent = config.get_quality_check_threshold("excellent", 90)
        good = config.get_quality_check_threshold("good", 75)
        passing = config.get_quality_check_threshold("pass", 60)

        if score >= excellent:
            return "优秀"
        elif score >= good:
            return "良好"
        elif score >= passing:
            return "合格"
        else:
            return "需改进"

    def _generate_summary_and_recommendation(self, overall_score: float,
                                              dimensions: Dict[str, "DimensionResult"]) -> tuple:
        """生成总结和建议"""
        all_issues = []
        for dim_name, dim_result in dimensions.items():
            if dim_result.issues:
                all_issues.extend(dim_result.issues)

        if overall_score >= 90:
            summary = "整体翻译质量优秀"
            recommendation = "可直接发布"
        elif overall_score >= 75:
            summary = f"整体翻译质量良好，存在 {len(all_issues)} 个可优化点"
            recommendation = "建议修复明显问题后发布"
        elif overall_score >= 60:
            summary = f"整体翻译质量合格，但有 {len(all_issues)} 个需要关注的问题"
            recommendation = "建议人工校对后发布"
        else:
            summary = f"整体翻译质量需要改进，发现 {len(all_issues)} 个问题"
            recommendation = "建议重新翻译或人工全面校对"

        if all_issues:
            summary += f"：{'；'.join(all_issues[:3])}"

        return summary, recommendation

    def _create_default_report(self, book_title: str, reason: str) -> QualityReport:
        """创建默认报告（无法评估时使用）"""
        return QualityReport(
            book_title=book_title,
            overall_score=0,
            overall_grade="无法评估",
            dimensions={},
            summary=f"质量检查无法完成: {reason}",
            recommendation="请检查翻译数据完整性后重试"
        )