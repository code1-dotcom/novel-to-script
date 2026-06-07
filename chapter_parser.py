"""chapter_parser.py — 章节解析模块
读取 .txt 文件，识别并提取章节标题和对应正文。
支持多种章节标题格式，包括中文数字和阿拉伯数字编号。
"""

import re
import os
import logging

logger = logging.getLogger(__name__)


class ChapterParser:
    """小说章节解析器，从文本中识别章节边界并提取内容"""

    def __init__(self):
        self.patterns = [
            r"^【第[一二三四五六七八九十百千\d]+章[：:\s·.]*(.+)?】?$",
            r"^第[一二三四五六七八九十百千\d]+章[：:\s·.]*(.+)?$",
            r"^Chapter\s+\d+[：:\s]*(.+)?$",
            r"^卷[一二三四五六七八九十百千\d]+[：:\s]*(.+)?$",
            r"^[一二三四五六七八九十百千\d]+[、.]\s*([\u4e00-\u9fff].*)$",
        ]
        self._compiled_patterns = [re.compile(p) for p in self.patterns]

    def _match_chapter_title(self, line: str) -> tuple[str, str] | None:
        stripped = line.strip()
        if not stripped:
            return None
        for pattern in self._compiled_patterns:
            match = pattern.match(stripped)
            if match:
                title = match.group(1) or ""
                title = title.strip().rstrip("】")
                return (stripped, title)
        return None

    def parse(self, text: str) -> list[dict]:
        """
        解析小说文本，返回章节列表。

        返回格式:
        [
            {
                "index": 1,
                "title": "旧日回响",
                "raw_title": "【第1章：旧日回响】",
                "start_line": 1,
                "end_line": 97,
                "content": "完整章节正文..."
            },
            ...
        ]
        """
        lines = text.splitlines(keepends=True)
        if not lines:
            return []

        chapters: list[dict] = []
        chapter_boundaries: list[tuple[int, str, str]] = []

        for i, line in enumerate(lines):
            result = self._match_chapter_title(line)
            if result:
                raw_title, title = result
                chapter_boundaries.append((i, raw_title, title))

        if not chapter_boundaries:
            return [{
                "index": 0,
                "title": "序章",
                "raw_title": "",
                "start_line": 1,
                "end_line": len(lines),
                "content": "".join(lines).strip(),
            }]

        first_boundary_line = chapter_boundaries[0][0]
        if first_boundary_line > 0:
            preamble = "".join(lines[:first_boundary_line]).strip()
            if preamble:
                chapters.append({
                    "index": 0,
                    "title": "序章",
                    "raw_title": "",
                    "start_line": 1,
                    "end_line": first_boundary_line,
                    "content": preamble,
                })

        for idx, (start_line, raw_title, title) in enumerate(chapter_boundaries):
            end_line = (
                chapter_boundaries[idx + 1][0]
                if idx + 1 < len(chapter_boundaries)
                else len(lines)
            )
            content = "".join(lines[start_line:end_line]).strip()

            chapters.append({
                "index": idx + 1,
                "title": title,
                "raw_title": raw_title,
                "start_line": start_line + 1,
                "end_line": end_line,
                "content": content,
            })

        logger.info("解析完成: 共 %d 个章节", len(chapters))
        return chapters

    def parse_file(self, file_path: str) -> list[dict]:
        """从文件路径读取并解析"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except FileNotFoundError:
            logger.error("文件不存在: %s", file_path)
            raise FileNotFoundError(f"文件不存在: {file_path}")
        except UnicodeDecodeError as e:
            logger.error("文件编码不是 UTF-8: %s", file_path)
            raise UnicodeDecodeError(
                e.encoding, e.object, e.start, e.end,
                f"文件编码不是 UTF-8，请将文件转换为 UTF-8 编码后重试: {file_path}",
            ) from e
        except (PermissionError, OSError) as e:
            logger.error("文件读取失败: %s — %s", file_path, e)
            raise IOError(f"文件读取失败: {file_path}") from e
        logger.info("读取文件: %s (%d 字符)", file_path, len(text))
        return self.parse(text)

    def parse_directory(self, dir_path: str) -> list[dict]:
        """
        扫描文件夹，读取所有 .txt 文件并解析。

        返回格式:
        [
            {
                "file_name": "《深渊代码》.txt",
                "chapters": [ ... ]
            },
            ...
        ]
        """
        results = []
        for filename in sorted(os.listdir(dir_path)):
            if filename.lower().endswith(".txt"):
                file_path = os.path.join(dir_path, filename)
                chapters = self.parse_file(file_path)
                results.append({
                    "file_name": filename,
                    "chapters": chapters,
                })
        logger.info("目录扫描完成: %s, 共 %d 个 .txt 文件", dir_path, len(results))
        return results

    def parse_uploaded_files(self, uploaded_files: list) -> list[dict]:
        """
        解析用户通过 st.file_uploader 上传的多个文件。

        返回格式同 parse_directory。
        """
        results = []
        errors = []
        for uploaded_file in uploaded_files:
            filename = getattr(uploaded_file, "name", "unknown")
            try:
                raw_bytes = uploaded_file.read()
                text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError as e:
                logger.warning("文件编码不是 UTF-8，跳过: %s", filename)
                errors.append(f"{filename}: 编码不是 UTF-8，已跳过")
                continue
            except Exception as e:
                logger.warning("文件读取失败，跳过: %s — %s", filename, e)
                errors.append(f"{filename}: 读取失败，已跳过")
                continue
            logger.info("解析上传文件: %s (%d 字符)", filename, len(text))
            chapters = self.parse(text)
            results.append({
                "file_name": filename,
                "chapters": chapters,
            })
        logger.info("上传文件解析完成: 共 %d 个文件, %d 个错误", len(results), len(errors))
        return results, errors