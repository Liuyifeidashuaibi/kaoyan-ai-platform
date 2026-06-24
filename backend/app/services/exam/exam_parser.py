"""
试卷结构化解析器 — 基于正则+规则引擎将 OCR 文本拆分为结构化题目。

输出标准 JSON:
{
    "sections": [
        {
            "type": "choice" | "fill" | "solution" | "reading" | "cloze" | "translation" | "writing" | "other",
            "title": "Section Title",
            "questions": [
                {
                    "id": "1",
                    "type": "choice",
                    "stem": "Question stem text...",
                    "options": ["A. ...", "B. ...", "C. ...", "D. ..."]
                }
            ]
        }
    ]
}
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field, asdict
from typing import Literal

logger = logging.getLogger(__name__)

# 题型标签映射
SECTION_TYPE_MAP = {
    "choice": ["选择题", "单项选择题", "多选题", "单项选择", "多项选择", "multiple choice", "选择题部分"],
    "fill": ["填空题", "fill in the blanks", "completion"],
    "solution": ["解答题", "计算题", "证明题", "论述题", "problem solving", "solution"],
    "reading": ["阅读理解", "reading comprehension", "reading", "passage"],
    "cloze": ["完形填空", "cloze", "cloze test"],
    "translation": ["翻译", "translation", "英译汉", "汉译英"],
    "writing": ["写作", "作文", "writing", "essay"],
}

# 中文题号模式: 1. 一、 (1) ① 第一题 等
_QUESTION_NUM_PATTERNS = [
    r"^(?:第[一二三四五六七八九十百零\d]+[题道])",
    r"^[\(（]?(\d{1,3})[\.、\)）]\s*",
    r"^[\(（]([一二三四五六七八九十]+)[\)）]\s*",
    r"^([A-Z])[\.、]\s*(?=[^\s])",  # A. B. C. D. 选项，不作为题号
]

# 选项模式
_OPTION_PATTERN = re.compile(
    r"^\s*([A-D])\s*[\.、\)]\s*(.+)",
    re.IGNORECASE,
)

# 大题型标题模式
_SECTION_TITLE_PATTERNS = []
for sec_type, keywords in SECTION_TYPE_MAP.items():
    for kw in keywords:
        # 匹配如 "一、选择题" "Part II Reading Comprehension" "选择题部分" 等
        _SECTION_TITLE_PATTERNS.append(
            (re.compile(rf"(?:^[一二三四五六七八九十]+[、.]\s*)?{re.escape(kw)}(?:部分)?(?:[\s（\(].*?[\)）])?\s*$", re.IGNORECASE), sec_type)
        )
        _SECTION_TITLE_PATTERNS.append(
            (re.compile(rf"^(?:Part\s+[IVX]+\s*)?{re.escape(kw)}\s*$", re.IGNORECASE), sec_type)
        )


@dataclass
class ExamQuestion:
    """单道题目。"""
    id: str                           # 题号
    type: str = "other"               # 题型标签
    stem: str = ""                    # 题干
    options: list[str] = field(default_factory=list)  # 选项（选择题）
    sub_questions: list[str] = field(default_factory=list)  # 子题（如阅读中的小题）

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "stem": self.stem,
            "options": self.options,
            "sub_questions": self.sub_questions,
        }


@dataclass
class ExamSection:
    """一个大题型分区。"""
    type: str = "other"
    title: str = ""
    questions: list[ExamQuestion] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "title": self.title,
            "questions": [q.to_dict() for q in self.questions],
        }


@dataclass
class ParsedExam:
    """解析后的完整试卷。"""
    sections: list[ExamSection] = field(default_factory=list)
    raw_text: str = ""
    subject: str = ""  # "english" | "math"

    def to_dict(self) -> dict:
        return {
            "sections": [s.to_dict() for s in self.sections],
            "subject": self.subject,
        }

    @property
    def total_questions(self) -> int:
        return sum(len(s.questions) for s in self.sections)


class ExamParser:
    """试卷结构化解析器。"""

    def __init__(self, subject: str = ""):
        self.subject = subject

    def parse(self, ocr_text: str) -> ParsedExam:
        """解析 OCR 文本为结构化试卷。"""
        result = ParsedExam(raw_text=ocr_text, subject=self.subject)
        lines = self._normalize_lines(ocr_text)

        if not lines:
            return result

        # 检测并拆分 sections
        sections_raw = self._split_into_sections(lines)

        for sec_title, sec_type, sec_lines in sections_raw:
            section = ExamSection(type=sec_type, title=sec_title)
            questions = self._extract_questions(sec_lines, sec_type)
            section.questions = questions
            result.sections.append(section)

        # 如果没有检测到任何 section，整段作为 other
        if not result.sections:
            section = ExamSection(type="other", title="试题")
            section.questions = self._extract_questions(lines, "other")
            result.sections.append(section)

        logger.info(
            "解析完成: %d sections, %d questions",
            len(result.sections),
            result.total_questions,
        )
        return result

    def _normalize_lines(self, text: str) -> list[str]:
        """标准化文本行：去空行、合并续行。"""
        lines = text.split("\n")
        normalized: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if normalized:
                    normalized.append("")  # 保留段落分隔
                continue
            normalized.append(stripped)
        return normalized

    def _detect_section_type(self, line: str) -> tuple[str, str] | None:
        """检测一行是否为大题型标题，返回 (title, type) 或 None。"""
        for pattern, sec_type in _SECTION_TITLE_PATTERNS:
            if pattern.search(line):
                return (line.strip(), sec_type)
        return None

    def _split_into_sections(
        self, lines: list[str]
    ) -> list[tuple[str, str, list[str]]]:
        """将行列表按大题型标题拆分为 sections。"""
        sections: list[tuple[str, str, list[str]]] = []
        current_title = ""
        current_type = "other"
        current_lines: list[str] = []

        for line in lines:
            detected = self._detect_section_type(line)
            if detected:
                # 保存上一个 section
                if current_lines:
                    sections.append((current_title, current_type, current_lines))
                current_title, current_type = detected
                current_lines = []
            else:
                if line.strip():  # 跳过空行作为 section 开头
                    current_lines.append(line)

        # 保存最后一个 section
        if current_lines:
            sections.append((current_title, current_type, current_lines))

        return sections

    def _extract_questions(
        self, lines: list[str], section_type: str
    ) -> list[ExamQuestion]:
        """从一个 section 的行中提取单道题目。"""
        questions: list[ExamQuestion] = []

        # 特殊处理：阅读理解通常是一个大题 + 多小题
        if section_type == "reading":
            return self._extract_reading_questions(lines)

        # 通用拆分：按题号拆分
        current_q: ExamQuestion | None = None
        q_counter = 0

        for line in lines:
            is_question_start, q_num = self._is_question_start(line)

            if is_question_start:
                if current_q:
                    questions.append(current_q)
                q_counter += 1
                current_q = ExamQuestion(
                    id=q_num or str(q_counter),
                    type=section_type,
                    stem=line,
                )
            elif current_q is not None:
                # 检查是否是选项
                option_match = _OPTION_PATTERN.match(line)
                if option_match and section_type == "choice":
                    opt_label = option_match.group(1).upper()
                    opt_text = option_match.group(2).strip()
                    current_q.options.append(f"{opt_label}. {opt_text}")
                else:
                    # 续行，追加到题干
                    current_q.stem += "\n" + line
            else:
                # 第一行不是题号开头，视为题干开始
                q_counter += 1
                current_q = ExamQuestion(
                    id=str(q_counter),
                    type=section_type,
                    stem=line,
                )

        if current_q:
            questions.append(current_q)

        # 清理题干：移除开头的题号
        for q in questions:
            q.stem = self._clean_stem(q.stem)

        return questions

    def _extract_reading_questions(self, lines: list[str]) -> list[ExamQuestion]:
        """阅读理解专项提取：区分文章与题目。"""
        questions: list[ExamQuestion] = []
        passage_lines: list[str] = []
        question_lines: list[str] = []
        in_questions = False
        q_counter = 0

        for line in lines:
            is_start, q_num = self._is_question_start(line)
            if is_start:
                in_questions = True
                # 保存之前的题目
                if question_lines:
                    q_counter += 1
                    questions.append(ExamQuestion(
                        id=str(q_counter),
                        type="reading",
                        stem="\n".join(question_lines),
                        sub_questions=question_lines[:],
                    ))
                    question_lines = []
                question_lines.append(line)
            elif in_questions:
                question_lines.append(line)
            else:
                passage_lines.append(line)

        # 保存最后一道题
        if question_lines:
            q_counter += 1
            questions.append(ExamQuestion(
                id=str(q_counter),
                type="reading",
                stem="\n".join(question_lines),
                sub_questions=question_lines[:],
            ))

        # 如果没有检测到小题，整段作为一个阅读理解题
        if not questions and passage_lines:
            questions.append(ExamQuestion(
                id="1",
                type="reading",
                stem="\n".join(passage_lines),
            ))

        return questions

    def _is_question_start(self, line: str) -> tuple[bool, str | None]:
        """检测一行是否是题目开头，返回 (is_start, question_number)。"""
        # 模式1: 第X题
        m = re.match(r"^第([一二三四五六七八九十百零\d]+)[题道]\s*", line)
        if m:
            return True, m.group(1)

        # 模式2: (1) 1. 1、 1) 等
        m = re.match(r"^[\(（]?(\d{1,3})[\.、\)）]\s*", line)
        if m:
            # 排除选项 A/B/C/D
            return True, m.group(1)

        # 模式3: (一) (1) 等中文数字
        m = re.match(r"^[\(（]([一二三四五六七八九十]+)[\)）]\s*", line)
        if m:
            return True, m.group(1)

        return False, None

    def _clean_stem(self, stem: str) -> str:
        """清理题干，移除开头的题号。"""
        # 移除开头的题号模式
        patterns = [
            r"^第[一二三四五六七八九十百零\d]+[题道]\s*",
            r"^[\(（]?\d{1,3}[\.、\)）]\s*",
            r"^[\(（][一二三四五六七八九十]+[\)）]\s*",
        ]
        cleaned = stem
        for p in patterns:
            cleaned = re.sub(p, "", cleaned, count=1)
        return cleaned.strip()


def parse_exam_text(ocr_text: str, subject: str = "") -> ParsedExam:
    """便捷函数：解析 OCR 文本为结构化试卷。"""
    parser = ExamParser(subject=subject)
    # 先清洗 OCR 文本中的手写噪音
    cleaned = clean_ocr_text(ocr_text)
    return parser.parse(cleaned)


# ---------------------------------------------------------------------------
# OCR 后处理：手写痕迹 / 乱码清洗
# ---------------------------------------------------------------------------

# 常见手写 OCR 乱码模式
_HANDWRITING_NOISE_PATTERNS = [
    # 连续 3+ 个无意义符号 (如 „„„, ∞∞∞, ≈≈≈)
    re.compile(r"([„\u201e\u201c\u201d\u2018\u2019~\u2248\u221e\u2026\u00b7\u2022\u25cf\u25cb\u25a0\u25a1\u25b2\u25b3\u25ba\u25bb\u25bc\u25bd\u25be\u25bf\u25c0\u25c1])\1{2,}"),
    # 连续混杂的中英文乱码（如 “的的是是” “了了了”）
    re.compile(r"(.)\1{4,}"),
    # 孤立的手写标注符号（如单独的 ✓ ✗ √ × ✘）
    re.compile(r"^\s*[\u2713\u2717\u221a\u00d7\u2718\u2605\u2606\u25cb\u25cf\u25b3\u25b2\u25a1\u25a0]{1,2}\s*$", re.MULTILINE),
    # 红笔批注常见：括号内的简短评语
    re.compile(r"\s*[(（][^\n){8,30}[)）]\s*"),
]

# 手写答案常见模式（如 “选 A” “答: B” “= 3”）
_HANDWRITING_ANSWER_PATTERNS = [
    re.compile(r"(?:选|答|answer)\s*[:\uff1a]?\s*[A-D]\s*[\.、]?", re.IGNORECASE),
    re.compile(r"=\s*-?\d+\.?\d*\s*$", re.MULTILINE),
    re.compile(r"(?:解|答案)\s*[:\uff1a]\s*[^\n]{1,20}\s*$", re.MULTILINE),
]


def clean_ocr_text(text: str) -> str:
    """
    清洗 OCR 文本中的手写痕迹、乱码、低质量片段。

    处理流程:
    1. 移除手写 OCR 乱码
    2. 移除孤立批注符号
    3. 移除明显的手写答案片段
    4. 合并连续空行
    5. 清理行首行尾多余空格
    """
    if not text or not text.strip():
        return text

    cleaned = text

    # 1. 移除手写乱码
    for pattern in _HANDWRITING_NOISE_PATTERNS:
        cleaned = pattern.sub("", cleaned)

    # 2. 移除手写答案片段
    for pattern in _HANDWRITING_ANSWER_PATTERNS:
        cleaned = pattern.sub("", cleaned)

    # 3. 合并连续 3+ 空行为 2 个
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    # 4. 清理每行首尾多余空格
    lines = cleaned.split("\n")
    lines = [line.strip() for line in lines]
    cleaned = "\n".join(lines)

    # 5. 移除极短行（单个字符的行，大概率是手写残余）
    lines = cleaned.split("\n")
    filtered_lines = []
    for line in lines:
        stripped = line.strip()
        # 保留空行（段落分隔）和长度 >= 2 的行
        if not stripped or len(stripped) >= 2:
            filtered_lines.append(line)
        else:
            # 保留单个数字或字母（可能是题号）
            if stripped.isalnum():
                filtered_lines.append(line)
            # 其余单字符行丢弃

    result = "\n".join(filtered_lines)
    return result
