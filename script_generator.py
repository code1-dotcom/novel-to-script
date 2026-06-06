"""script_generator.py — 剧本生成模块
逐章调用 AI，将小说正文转换为 YAML 剧本片段。
对 AI 输出的 YAML 做基本校验，解析失败时自动重试（最多 2 次），
在 prompt 中追加错误信息。
"""

import logging

from bailian_client import BailianClient, BailianAPIError
from prompt_templates import PROMPTS
from yaml_manager import YAMLManager
import config

logger = logging.getLogger(__name__)

MAX_GENERATION_RETRIES = 2


class ScriptGenerator:
    """逐章调用 AI 生成剧本 YAML 片段"""

    def __init__(self, client: BailianClient):
        self.client = client
        self.yaml_manager = YAMLManager()

    def generate_chapter_script(
        self,
        chapter_content: str,
        chapter_index: int,
        chapter_title: str,
        characters: dict,
        previous_summary: str = "",
    ) -> str:
        """
        生成单章对应的剧本 YAML 片段。

        每次调用时将角色信息和上一章摘要作为上下文注入 prompt。
        对 AI 输出的 YAML 做基本校验，解析失败时自动重试（最多 2 次）。

        参数:
            chapter_content: 章节正文内容
            chapter_index: 章节序号（从 1 开始）
            chapter_title: 章节标题
            characters: character_profiles.json 中的角色表 dict，
                       包含 "characters" 列表
            previous_summary: 上一章的剧情摘要，用于保持连贯性

        返回:
            符合 Schema 定义的 YAML 字符串
        """
        character_profiles_text = self._format_characters_for_prompt(characters)

        prompt = PROMPTS["script_generation"].format(
            character_profiles=character_profiles_text,
            previous_summary=previous_summary if previous_summary else "（无）",
            chapter_index=chapter_index,
            chapter_title=chapter_title,
            chapter_content=chapter_content,
        )

        messages = [{"role": "user", "content": prompt}]

        last_output = ""
        last_errors: list[str] = []

        for attempt in range(MAX_GENERATION_RETRIES + 1):
            try:
                raw_output = self.client.chat(
                    model=config.MODEL_PRIMARY,
                    messages=messages,
                    temperature=config.TEMPERATURE_SCRIPT,
                    max_tokens=config.MAX_TOKENS_SCRIPT,
                )
                last_output = raw_output

                errors = self.yaml_manager.validate_yaml_text(raw_output)
                if not errors:
                    logger.info(
                        "第 %d 章剧本生成成功 (第 %d/%d 次尝试)",
                        chapter_index, attempt + 1, MAX_GENERATION_RETRIES + 1,
                    )
                    return raw_output

                last_errors = errors
                logger.warning(
                    "第 %d 章剧本校验失败 (第 %d/%d 次尝试): %s",
                    chapter_index, attempt + 1, MAX_GENERATION_RETRIES + 1, errors,
                )

                if attempt < MAX_GENERATION_RETRIES:
                    retry_message = self._build_retry_message(errors, raw_output)
                    messages.append({"role": "assistant", "content": raw_output})
                    messages.append({"role": "user", "content": retry_message})

            except BailianAPIError as e:
                logger.error(
                    "第 %d 章剧本生成 API 异常 (第 %d/%d 次尝试): %s",
                    chapter_index, attempt + 1, MAX_GENERATION_RETRIES + 1, e,
                )
                if attempt >= MAX_GENERATION_RETRIES:
                    raise

        if last_output:
            logger.warning(
                "第 %d 章剧本生成在 %d 次尝试后仍存在校验错误，返回最后一次输出",
                chapter_index, MAX_GENERATION_RETRIES + 1,
            )
            return last_output

        raise BailianAPIError(
            f"第 {chapter_index} 章剧本生成失败，"
            f"{MAX_GENERATION_RETRIES + 1} 次尝试后仍未获得有效输出"
        )

    def generate_chapter_script_with_errors(
        self,
        chapter_content: str,
        chapter_index: int,
        chapter_title: str,
        characters: dict,
        previous_summary: str = "",
    ) -> tuple[str, list[str]]:
        """
        生成剧本并返回校验结果。

        相比 generate_chapter_script，额外返回校验错误列表，
        方便调用方决定是否需要手动修复。

        返回:
            (yaml_string, errors_list)
            errors_list 为空列表时表示校验通过
        """
        yaml_output = self.generate_chapter_script(
            chapter_content=chapter_content,
            chapter_index=chapter_index,
            chapter_title=chapter_title,
            characters=characters,
            previous_summary=previous_summary,
        )
        errors = self.yaml_manager.validate_yaml_text(yaml_output)
        return yaml_output, errors

    def extract_summary(self, yaml_output: str) -> str:
        """
        从生成的剧本 YAML 中提取剧情摘要，供下一章生成时使用。

        遍历所有 scene 和 beat，提取关键对白和动作描述，
        拼接为纯文本摘要。

        参数:
            yaml_output: 单章剧本 YAML 字符串

        返回:
            剧情摘要文本
        """
        parsed = self.yaml_manager.parse_yaml_text(yaml_output)
        if parsed is None:
            return ""

        summary_parts: list[str] = []

        scenes = self._extract_scenes(parsed)
        for scene in scenes:
            if not isinstance(scene, dict):
                continue

            location = scene.get("location", "")
            if location:
                summary_parts.append(f"地点: {location}")

            beats = scene.get("beats", [])
            for beat in beats:
                if not isinstance(beat, dict):
                    continue
                beat_type = beat.get("type", "")
                if beat_type == "dialogue":
                    char_ref = beat.get("char_ref", "")
                    line = beat.get("line", "")
                    if char_ref and line:
                        summary_parts.append(f"{char_ref}: {line}")
                elif beat_type in ("action", "direction"):
                    content = beat.get("content", "")
                    if content:
                        summary_parts.append(content)

        return "\n".join(summary_parts)

    def _format_characters_for_prompt(self, characters: dict) -> str:
        """
        将角色特征 dict 格式化为 prompt 中可读的文本。

        参数:
            characters: {"characters": [...]} 格式的 dict

        返回:
            格式化的角色信息文本
        """
        char_list = characters.get("characters", []) if characters else []
        if not char_list:
            return "（暂无角色信息）"

        lines: list[str] = []
        for char in char_list:
            if not isinstance(char, dict):
                continue

            char_id = char.get("id", "")
            name = char.get("name", "")
            role = char.get("role", "")
            aliases = char.get("aliases", [])
            traits = char.get("traits", {})

            lines.append(f"- {char_id}: {name}")
            if aliases:
                lines.append(f"  别名: {', '.join(aliases)}")
            if role:
                lines.append(f"  角色类型: {role}")
            if traits.get("personality"):
                lines.append(f"  性格: {traits['personality']}")
            if traits.get("speaking_style"):
                lines.append(f"  说话风格: {traits['speaking_style']}")
            if traits.get("background"):
                lines.append(f"  背景: {traits['background']}")
            if traits.get("relationships"):
                rels = traits["relationships"]
                rel_str = ", ".join(f"{k}: {v}" for k, v in rels.items())
                lines.append(f"  人际关系: {rel_str}")

        return "\n".join(lines)

    def _build_retry_message(self, errors: list[str], previous_output: str) -> str:
        """
        构建重试时的提示消息，告知 AI 上次输出的问题。

        参数:
            errors: 上次校验发现的错误信息列表
            previous_output: 上次 AI 输出的原始文本

        返回:
            重试提示消息
        """
        error_text = "\n".join(f"  - {e}" for e in errors)
        return f"""上一次生成的 YAML 存在以下校验错误，请修正后重新输出完整的 YAML：

校验错误：
{error_text}

请确保：
1. scenes 列表非空，每个 scene 包含 scene_id、location、int_ext、time_of_day、beats 等字段
2. 每个 dialogue beat 必须包含 char_ref 和 line 字段
3. 每个 action/direction beat 必须包含 content 字段
4. transition 使用有效值: CUT TO, FADE IN, FADE OUT, DISSOLVE TO, SMASH CUT, MATCH CUT
5. int_ext 使用有效值: INT, EXT, INT/EXT
6. time_of_day 使用有效值: DAY, NIGHT, DAWN, DUSK, CONTINUOUS

请直接输出修正后的完整 YAML，不要包含其他说明文字。"""

    def _extract_scenes(self, parsed: dict) -> list[dict]:
        """从解析后的 YAML 数据中提取 scenes 列表"""
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            if "scenes" in parsed:
                return parsed["scenes"]
            if "acts" in parsed:
                acts = parsed["acts"]
                all_scenes: list[dict] = []
                for act in acts:
                    if isinstance(act, dict) and "scenes" in act:
                        all_scenes.extend(act["scenes"])
                return all_scenes
        return []