"""yaml_manager.py — YAML 读写管理
YAML 文件的读取、写入、合并、校验。
"""

import re
import yaml
import logging

logger = logging.getLogger(__name__)

VALID_INT_EXT = {"INT", "EXT", "INT/EXT"}
VALID_TIME_OF_DAY = {"DAY", "NIGHT", "DAWN", "DUSK", "CONTINUOUS"}
VALID_TRANSITIONS = {"CUT TO", "FADE IN", "FADE OUT", "DISSOLVE TO", "SMASH CUT", "MATCH CUT", ""}
VALID_BEAT_TYPES = {"dialogue", "action", "direction"}
VALID_ROLES = {"protagonist", "antagonist", "supporting", "extra"}

META_REQUIRED = ["title", "author", "version", "genre", "source"]

CHARACTER_FIELDS = ["id", "name", "aliases", "role", "arc"]
SCENE_FIELDS = ["scene_id", "act_ref", "location", "int_ext", "time_of_day", "characters_present", "beats", "transition"]
DIALOGUE_BEAT_FIELDS = ["type", "char_ref", "line", "parenthetical", "emotion"]
ACTION_BEAT_FIELDS = ["type", "content"]
DIRECTION_BEAT_FIELDS = ["type", "content"]


class YAMLManager:
    """YAML 文件的读写、合并与校验"""

    def load(self, file_path: str) -> dict:
        """读取 YAML 文件"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except FileNotFoundError:
            logger.error("YAML 文件不存在: %s", file_path)
            raise FileNotFoundError(f"YAML 文件不存在: {file_path}")
        except yaml.YAMLError as e:
            logger.error("YAML 解析失败: %s — %s", file_path, e)
            raise ValueError(f"YAML 文件格式错误: {file_path}") from e
        except (UnicodeDecodeError, PermissionError, OSError) as e:
            logger.error("读取 YAML 文件失败: %s — %s", file_path, e)
            raise IOError(f"无法读取 YAML 文件: {file_path}") from e
        if data is None:
            data = {}
        logger.info("YAML 已加载: %s", file_path)
        return data

    def save(self, data: dict, file_path: str):
        """写入 YAML 文件，确保 2 空格缩进"""
        try:
            with open(file_path, "w", encoding="utf-8", newline="\n") as f:
                yaml.dump(
                    data,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    indent=2,
                    sort_keys=False,
                )
        except yaml.YAMLError as e:
            logger.error("YAML 序列化失败: %s — %s", file_path, e)
            raise ValueError(f"YAML 序列化失败，数据可能包含不可序列化的对象: {e}") from e
        except (PermissionError, OSError) as e:
            logger.error("写入 YAML 文件失败: %s — %s", file_path, e)
            raise IOError(f"无法写入 YAML 文件: {file_path}") from e
        logger.info("YAML 已保存: %s", file_path)

    def parse_yaml_text(self, text: str) -> dict | None:
        """
        从 AI 返回的文本中提取并解析 YAML。

        处理 AI 可能用 ```yaml 或 ``` 包裹 YAML 内容的情况。
        返回解析后的 dict，解析失败返回 None。
        """
        if not text or not text.strip():
            return None

        cleaned = text.strip()

        if "```yaml" in cleaned:
            start = cleaned.find("```yaml") + len("```yaml")
            end = cleaned.find("```", start)
            if end != -1:
                cleaned = cleaned[start:end].strip()
        elif "```" in cleaned:
            start = cleaned.find("```") + len("```")
            end = cleaned.find("```", start)
            if end != -1:
                cleaned = cleaned[start:end].strip()

        try:
            parsed = yaml.safe_load(cleaned)
            return parsed
        except yaml.YAMLError as e:
            logger.warning("parse_yaml_text 解析失败: %s", e)
            return None

    def merge_acts(self, yaml_pieces: list[str], meta: dict, characters: list[dict]) -> dict:
        """
        合并所有章节的 YAML 片段为完整剧本。

        参数:
            yaml_pieces: 每章生成的 YAML 字符串列表
            meta: 元信息 {"title": "...", "author": "...", "version": "...", "genre": "...", "source": "..."}
            characters: 角色表列表（来自 character_profiles.json）

        返回: 完整的剧本 dict
        """
        acts = []
        for i, piece in enumerate(yaml_pieces):
            if not piece or not piece.strip():
                logger.warning("merge_acts: 第 %d 个 YAML 片段为空，跳过", i + 1)
                continue

            parsed = self.parse_yaml_text(piece)
            if parsed is None:
                logger.warning("merge_acts: 第 %d 个 YAML 片段解析失败，跳过", i + 1)
                continue

            piece_acts = self._extract_acts_from_parsed(parsed)
            acts.extend(piece_acts)

        for idx, act in enumerate(acts):
            act["act_id"] = f"act_{idx + 1:03d}"

        char_list = self._build_character_list(characters)

        screenplay = {
            "meta": meta,
            "characters": char_list,
            "acts": acts,
        }

        logger.info("剧本合并完成: %d 幕, %d 个角色", len(acts), len(char_list))
        return screenplay

    def validate(self, data: dict) -> list[str]:
        """
        校验 YAML 是否符合 Schema，返回错误信息列表。

        返回: 错误信息列表，空列表表示校验通过
        """
        errors = []

        if not isinstance(data, dict):
            return ["根节点必须是 dict 类型"]

        errors.extend(self._validate_meta(data.get("meta")))
        errors.extend(self._validate_characters(data.get("characters")))
        errors.extend(self._validate_acts(data.get("acts")))

        if errors:
            logger.warning("YAML 校验发现 %d 个错误", len(errors))
        else:
            logger.info("YAML 校验通过")
        return errors

    def validate_yaml_text(self, yaml_text: str) -> list[str]:
        """
        解析 YAML 文本并校验，适用于剧本生成后立即校验。

        参数:
            yaml_text: 单章剧本 YAML 字符串

        返回: 错误信息列表
        """
        parsed = self.parse_yaml_text(yaml_text)
        if parsed is None:
            return ["YAML 解析失败: 无法解析为有效的 YAML 格式"]
        return self.validate(parsed)

    def to_display_string(self, data: dict) -> str:
        """将 dict 转为格式化的 YAML 字符串，用于编辑区展示"""
        return yaml.dump(
            data,
            default_flow_style=False,
            allow_unicode=True,
            indent=2,
            sort_keys=False,
        )

    def _extract_acts_from_parsed(self, parsed) -> list[dict]:
        """从解析后的 YAML 数据中提取 acts 列表"""
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            if "acts" in parsed:
                return parsed["acts"]
            if "scenes" in parsed:
                return [parsed]
        return []

    def _build_character_list(self, characters: list[dict]) -> list[dict]:
        """从角色特征数据构建剧本所需的角色列表"""
        char_list = []
        for char in characters:
            entry = {
                "id": char.get("id", ""),
                "name": char.get("name", ""),
                "role": char.get("role", ""),
                "arc": char.get("arc", ""),
            }
            aliases = char.get("aliases")
            if aliases:
                entry["aliases"] = aliases
            char_list.append(entry)
        return char_list

    def _validate_meta(self, meta) -> list[str]:
        errors = []
        if meta is None:
            errors.append("缺少 meta 字段")
            return errors
        if not isinstance(meta, dict):
            errors.append("meta 必须是 dict 类型")
            return errors

        for field in META_REQUIRED:
            if not meta.get(field):
                errors.append(f"meta 缺少必填字段: {field}")

        return errors

    def _validate_characters(self, characters) -> list[str]:
        errors = []
        if characters is None:
            errors.append("缺少 characters 字段")
            return errors
        if not isinstance(characters, list):
            errors.append("characters 必须是 list 类型")
            return errors

        seen_ids = set()
        for i, char in enumerate(characters):
            if not isinstance(char, dict):
                errors.append(f"characters[{i}] 必须是 dict 类型")
                continue
            char_id = char.get("id", "")
            if not char_id:
                errors.append(f"characters[{i}] 缺少 id 字段")
            elif char_id in seen_ids:
                errors.append(f"characters[{i}] id 重复: {char_id}")
            else:
                seen_ids.add(char_id)
            if not char.get("name"):
                errors.append(f"characters[{i}] 缺少 name 字段")
            role = char.get("role", "")
            if role and role not in VALID_ROLES:
                errors.append(f"characters[{i}] role 值无效: {role}，有效值: {VALID_ROLES}")
        return errors

    def _validate_acts(self, acts) -> list[str]:
        errors = []
        if acts is None:
            errors.append("缺少 acts 字段")
            return errors
        if not isinstance(acts, list):
            errors.append("acts 必须是 list 类型")
            return errors

        seen_act_ids = set()
        for act_idx, act in enumerate(acts):
            if not isinstance(act, dict):
                errors.append(f"acts[{act_idx}] 必须是 dict 类型")
                continue

            act_id = act.get("act_id", "")
            if not act_id:
                errors.append(f"acts[{act_idx}] 缺少 act_id 字段")
            elif act_id in seen_act_ids:
                errors.append(f"acts[{act_idx}] act_id 重复: {act_id}")
            else:
                seen_act_ids.add(act_id)

            if not act.get("title"):
                errors.append(f"acts[{act_idx}] 缺少 title 字段")

            errors.extend(self._validate_scenes(act.get("scenes"), act_idx))

        return errors

    def _validate_scenes(self, scenes, act_idx: int) -> list[str]:
        errors = []
        if scenes is None:
            errors.append(f"acts[{act_idx}] 缺少 scenes 字段")
            return errors
        if not isinstance(scenes, list):
            errors.append(f"acts[{act_idx}].scenes 必须是 list 类型")
            return errors

        seen_scene_ids = set()
        for scene_idx, scene in enumerate(scenes):
            prefix = f"acts[{act_idx}].scenes[{scene_idx}]"
            if not isinstance(scene, dict):
                errors.append(f"{prefix} 必须是 dict 类型")
                continue

            scene_id = scene.get("scene_id", "")
            if not scene_id:
                errors.append(f"{prefix} 缺少 scene_id 字段")
            elif scene_id in seen_scene_ids:
                errors.append(f"{prefix} scene_id 重复: {scene_id}")
            else:
                seen_scene_ids.add(scene_id)

            if not scene.get("location"):
                errors.append(f"{prefix} 缺少 location 字段")

            int_ext = scene.get("int_ext", "")
            if int_ext and int_ext not in VALID_INT_EXT:
                errors.append(f"{prefix} int_ext 值无效: {int_ext}，有效值: {VALID_INT_EXT}")

            time_of_day = scene.get("time_of_day", "")
            if time_of_day and time_of_day not in VALID_TIME_OF_DAY:
                errors.append(f"{prefix} time_of_day 值无效: {time_of_day}，有效值: {VALID_TIME_OF_DAY}")

            chars_present = scene.get("characters_present")
            if chars_present is not None and not isinstance(chars_present, list):
                errors.append(f"{prefix} characters_present 必须是 list 类型")

            transition = scene.get("transition", "")
            if transition and transition not in VALID_TRANSITIONS:
                errors.append(f"{prefix} transition 值无效: {transition}，有效值: {VALID_TRANSITIONS}")

            errors.extend(self._validate_beats(scene.get("beats"), act_idx, scene_idx))

        return errors

    def _validate_beats(self, beats, act_idx: int, scene_idx: int) -> list[str]:
        errors = []
        if beats is None:
            errors.append(f"acts[{act_idx}].scenes[{scene_idx}] 缺少 beats 字段")
            return errors
        if not isinstance(beats, list):
            errors.append(f"acts[{act_idx}].scenes[{scene_idx}].beats 必须是 list 类型")
            return errors

        for beat_idx, beat in enumerate(beats):
            prefix = f"acts[{act_idx}].scenes[{scene_idx}].beats[{beat_idx}]"
            if not isinstance(beat, dict):
                errors.append(f"{prefix} 必须是 dict 类型")
                continue

            beat_type = beat.get("type", "")
            if not beat_type:
                errors.append(f"{prefix} 缺少 type 字段")
            elif beat_type not in VALID_BEAT_TYPES:
                errors.append(f"{prefix} type 值无效: {beat_type}，有效值: {VALID_BEAT_TYPES}")
                continue

            if beat_type == "dialogue":
                if not beat.get("char_ref"):
                    errors.append(f"{prefix} 缺少 char_ref 字段")
                if not beat.get("line"):
                    errors.append(f"{prefix} 缺少 line 字段")
            elif beat_type in ("action", "direction"):
                if not beat.get("content"):
                    errors.append(f"{prefix} 缺少 content 字段")

        return errors