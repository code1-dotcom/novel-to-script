"""script_editor.py — AI 编辑辅助模块
处理右侧 AI 对话框的交互，根据用户自然语言指令修改剧本 YAML。
维护对话历史（最近 10 轮），支持多轮修改，修改前后生成 diff 对比。
"""

import difflib
import logging

from bailian_client import BailianClient, BailianAPIError
from prompt_templates import PROMPTS
from yaml_manager import YAMLManager
import config

logger = logging.getLogger(__name__)

MAX_CHAT_ROUNDS = 10


class ScriptEditor:
    """AI 编辑助手，根据用户自然语言指令修改剧本 YAML"""

    def __init__(self, client: BailianClient):
        self.client = client
        self.yaml_manager = YAMLManager()

    def apply_edit(
        self,
        user_instruction: str,
        current_yaml: str,
        character_profiles: dict,
        conversation_history: list[dict] | None = None,
    ) -> tuple[str, str, list[dict]]:
        """
        根据用户指令修改剧本，维护对话历史实现多轮编辑。

        参数:
            user_instruction: 用户的修改指令
            current_yaml: 当前编辑区的 YAML 内容
            character_profiles: 角色特征文档 {"characters": [...]}
            conversation_history: 之前的对话历史（OpenAI 消息格式），
                                 首次调用时传 None

        返回:
            (modified_yaml, diff_text, updated_conversation_history)
            - modified_yaml: 修改后的完整 YAML 字符串
            - diff_text: unified diff 对比文本
            - updated_conversation_history: 更新后的对话历史
        """
        character_profiles_text = self._format_characters_for_prompt(character_profiles)

        messages = list(conversation_history) if conversation_history else []

        if not messages:
            system_prompt = (
                "你是一位专业的剧本编辑。请根据用户的修改指令，修改 YAML 剧本内容。\n\n"
                "## 当前剧本 YAML\n\n"
                f"{current_yaml}\n\n"
                "## 角色特征参考\n\n"
                f"{character_profiles_text}\n\n"
                "## 要求\n\n"
                "1. 只修改指令要求的部分，不要擅自修改其他内容\n"
                "2. 返回修改后的完整 YAML（不要只返回差异部分）\n"
                "3. 保持 YAML 格式正确\n"
                "4. 保持角色 ID 引用一致\n\n"
                "请直接输出修改后的完整 YAML，不要包含其他说明文字。"
            )
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages[0] = {
                "role": "system",
                "content": (
                    "你是一位专业的剧本编辑。请根据用户的修改指令，修改 YAML 剧本内容。\n\n"
                    "## 当前剧本 YAML\n\n"
                    f"{current_yaml}\n\n"
                    "## 角色特征参考\n\n"
                    f"{character_profiles_text}\n\n"
                    "## 要求\n\n"
                    "1. 只修改指令要求的部分，不要擅自修改其他内容\n"
                    "2. 返回修改后的完整 YAML（不要只返回差异部分）\n"
                    "3. 保持 YAML 格式正确\n"
                    "4. 保持角色 ID 引用一致\n\n"
                    "请直接输出修改后的完整 YAML，不要包含其他说明文字。"
                ),
            }

        messages.append({"role": "user", "content": user_instruction})

        self._trim_history(messages, MAX_CHAT_ROUNDS)

        try:
            raw_output = self.client.chat(
                model=config.MODEL_PRIMARY,
                messages=messages,
                temperature=config.TEMPERATURE_SCRIPT,
                max_tokens=config.MAX_TOKENS_EDIT,
            )

            messages.append({"role": "assistant", "content": raw_output})

            parsed = self.yaml_manager.parse_yaml_text(raw_output)
            if parsed is not None:
                modified_yaml = self.yaml_manager.to_display_string(parsed)
            else:
                logger.warning("AI 编辑返回的 YAML 解析失败，返回原始输出")
                modified_yaml = raw_output

            diff_text = self._generate_diff(current_yaml, modified_yaml)

            logger.info("AI 编辑完成，diff 长度: %d 字符", len(diff_text))
            return modified_yaml, diff_text, messages

        except BailianAPIError as e:
            logger.error("AI 编辑失败: %s", e)
            raise

    def _trim_history(self, messages: list[dict], max_rounds: int):
        system_msg = messages[0]
        user_assistant = messages[1:]
        max_user_assistant = max_rounds * 2
        if len(user_assistant) > max_user_assistant:
            messages[:] = [system_msg] + user_assistant[-max_user_assistant:]

    def _format_characters_for_prompt(self, characters: dict) -> str:
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
            traits = char.get("traits", {})

            lines.append(f"- {char_id}: {name}")
            if role:
                role_label = {"protagonist": "主角", "antagonist": "反派", "supporting": "配角", "extra": "龙套"}.get(
                    role, role
                )
                lines.append(f"  角色类型: {role_label}")
            if traits.get("personality"):
                lines.append(f"  性格: {traits['personality']}")
            if traits.get("speaking_style"):
                lines.append(f"  说话风格: {traits['speaking_style']}")
            if traits.get("background"):
                lines.append(f"  背景: {traits['background']}")

        return "\n".join(lines)

    def _generate_diff(self, old_text: str, new_text: str) -> str:
        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)

        diff_lines = list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile="修改前",
                tofile="修改后",
                lineterm="",
            )
        )

        if not diff_lines:
            return "（无变化）"

        if len(diff_lines) > 80:
            diff_lines = diff_lines[:80]
            diff_lines.append("\n... (diff 过长，已截断)")

        return "".join(diff_lines)