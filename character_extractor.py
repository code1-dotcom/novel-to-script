"""character_extractor.py — 角色提取模块
全局扫描小说章节内容，调用 AI 提取角色信息并生成 character_profiles.json。
支持长文本分批处理与合并去重。
"""

import json
import logging

from bailian_client import BailianClient, BailianAPIError, BailianFormatError
from prompt_templates import PROMPTS
import config

logger = logging.getLogger(__name__)


class CharacterExtractor:
    """从小说章节中提取角色特征信息"""

    def __init__(self, client: BailianClient):
        self.client = client

    def extract_characters(self, chapters_content: list[str]) -> dict:
        """
        从章节正文列表中提取角色信息。

        参数:
            chapters_content: 各章节的正文内容列表

        返回:
            {
                "characters": [
                    {
                        "id": "char_001",
                        "name": "叶文洁",
                        "aliases": ["文洁", "叶老师"],
                        "role": "protagonist",
                        "arc": "角色弧线描述...",
                        "traits": {
                            "personality": "冷静、理性...",
                            "speaking_style": "说话简练...",
                            "background": "清华大学...",
                            "relationships": {"叶哲泰": "父亲"}
                        }
                    },
                    ...
                ]
            }
        """
        if not chapters_content:
            logger.warning("extract_characters: 章节内容为空")
            return {"characters": []}

        full_text = "\n\n".join(chapters_content)
        chunks = self._split_into_chunks(full_text)

        logger.info("开始角色提取: 共 %d 个分块", len(chunks))

        all_characters = []
        for i, chunk in enumerate(chunks):
            logger.info("提取角色 第 %d/%d 块 (%d 字符)", i + 1, len(chunks), len(chunk))
            try:
                result = self._extract_from_chunk(chunk)
                characters = result.get("characters", [])
                logger.info("第 %d 块提取到 %d 个角色", i + 1, len(characters))
                all_characters.extend(characters)
            except (BailianAPIError, BailianFormatError) as e:
                logger.error("第 %d 块角色提取失败: %s", i + 1, e)
                raise

        if len(chunks) > 1 and all_characters:
            merged = self._merge_characters(all_characters)
            logger.info("角色合并完成: %d → %d 个角色", len(all_characters), len(merged))
            return {"characters": merged}
        else:
            return {"characters": all_characters}

    def save_profiles(self, profiles: dict, output_path: str):
        """
        保存角色特征到 JSON 文件。

        参数:
            profiles: extract_characters 返回的 dict
            output_path: 输出文件路径
        """
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(profiles, f, ensure_ascii=False, indent=2)
        except (PermissionError, OSError) as e:
            logger.error("保存角色特征失败: %s — %s", output_path, e)
            raise IOError(f"无法写入文件: {output_path}") from e
        except TypeError as e:
            logger.error("角色特征数据序列化失败: %s", e)
            raise ValueError(f"角色特征数据格式错误，无法序列化为 JSON: {e}") from e
        logger.info("角色特征已保存到: %s", output_path)

    def load_profiles(self, file_path: str) -> dict:
        """从 JSON 文件读取角色特征"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                profiles = json.load(f)
        except FileNotFoundError:
            logger.error("角色特征文件不存在: %s", file_path)
            raise FileNotFoundError(f"角色特征文件不存在: {file_path}")
        except json.JSONDecodeError as e:
            logger.error("角色特征文件 JSON 格式错误: %s — %s", file_path, e)
            raise ValueError(f"角色特征文件 JSON 格式错误: {file_path}") from e
        except (PermissionError, OSError, UnicodeDecodeError) as e:
            logger.error("读取角色特征文件失败: %s — %s", file_path, e)
            raise IOError(f"无法读取角色特征文件: {file_path}") from e
        logger.info("角色特征已加载: %s (%d 个角色)", file_path, len(profiles.get("characters", [])))
        return profiles

    def _split_into_chunks(self, text: str) -> list[str]:
        max_chars = config.MAX_CHUNK_TOKENS * 2
        if len(text) <= max_chars:
            return [text]

        chunks = []
        for i in range(0, len(text), max_chars):
            chunks.append(text[i:i + max_chars])
        logger.info("文本分块: %d 字符 → %d 块 (每块 ≤ %d 字符)", len(text), len(chunks), max_chars)
        return chunks

    def _extract_from_chunk(self, chunk: str) -> dict:
        prompt = PROMPTS["character_extraction"].format(chapters_content=chunk)
        messages = [{"role": "user", "content": prompt}]
        return self.client.chat_json(
            model=config.MODEL_SECONDARY,
            messages=messages,
            temperature=config.TEMPERATURE_EXTRACT,
            max_tokens=config.MAX_TOKENS_EXTRACT,
        )

    def _merge_characters(self, all_characters: list[dict]) -> list[dict]:
        batch_size = 10
        if len(all_characters) <= batch_size:
            return self._deduplicate_by_name(all_characters)

        merged = self._deduplicate_by_name(all_characters)
        if len(merged) <= batch_size:
            return merged

        return self._ai_merge(merged, batch_size)

    def _deduplicate_by_name(self, characters: list[dict]) -> list[dict]:
        seen_names: dict[str, dict] = {}
        result: list[dict] = []

        for char in characters:
            name = char.get("name", "")
            aliases = char.get("aliases", [])

            matched_key = None
            for key in seen_names:
                if name == key or name in seen_names[key].get("aliases", []):
                    matched_key = key
                    break
                for alias in aliases:
                    if alias == key or alias in seen_names[key].get("aliases", []):
                        matched_key = key
                        break
                if matched_key:
                    break

            if matched_key:
                existing = seen_names[matched_key]
                existing_aliases = set(existing.get("aliases", []))
                existing_aliases.update(aliases)
                if name != matched_key:
                    existing_aliases.add(name)
                existing["aliases"] = sorted(existing_aliases)
                if len(char.get("arc", "")) > len(existing.get("arc", "")):
                    existing["arc"] = char["arc"]
                if char.get("traits"):
                    existing_traits = existing.get("traits", {})
                    for trait_key, trait_val in char["traits"].items():
                        if trait_key == "relationships":
                            existing_rel = existing_traits.get("relationships", {})
                            existing_rel.update(trait_val)
                            existing_traits["relationships"] = existing_rel
                        elif not existing_traits.get(trait_key):
                            existing_traits[trait_key] = trait_val
                    existing["traits"] = existing_traits
            else:
                seen_names[name] = char
                result.append(char)

        for i, char in enumerate(result):
            char["id"] = f"char_{i + 1:03d}"

        return result

    def _ai_merge(self, characters: list[dict], batch_size: int = 10) -> list[dict]:
        current = characters[:batch_size]
        remaining = characters[batch_size:]

        while remaining:
            batch = remaining[:batch_size]
            remaining = remaining[batch_size:]

            existing_json = json.dumps({"characters": current}, ensure_ascii=False, indent=2)
            new_json = json.dumps({"characters": batch}, ensure_ascii=False, indent=2)

            prompt = PROMPTS["character_merge"].format(
                existing_characters=existing_json,
                new_characters=new_json,
            )
            messages = [{"role": "user", "content": prompt}]

            try:
                result = self.client.chat_json(
                    model=config.MODEL_SECONDARY,
                    messages=messages,
                    temperature=config.TEMPERATURE_EXTRACT,
                    max_tokens=config.MAX_TOKENS_EXTRACT,
                )
                current = result.get("characters", [])
                logger.info("AI 合并: 剩余 %d 个角色待合并", len(remaining))
            except (BailianAPIError, BailianFormatError) as e:
                logger.warning("AI 合并失败，回退到名称去重: %s", e)
                current = self._deduplicate_by_name(current + batch)

        for i, char in enumerate(current):
            char["id"] = f"char_{i + 1:03d}"

        return current