"""prompt_templates.py — Prompt 模板管理
集中管理所有 AI 调用的 Prompt 模板。
"""

PROMPTS = {

    "character_extraction": """你是一位专业的影视编剧顾问。请阅读以下小说章节内容，提取所有重要角色的信息，并以 JSON 格式输出。

要求：
1. 提取所有有对白或重要戏份的角色
2. 分析每个角色的性格特征、说话风格、背景、人际关系
3. 按角色重要程度区分 protagonist/antagonist/supporting/extra
4. 注意同一角色的不同称呼（别名）

输出格式：
```json
{{
    "characters": [
        {{
            "id": "char_001",
            "name": "角色名",
            "aliases": ["别名1", "别名2"],
            "role": "protagonist",
            "arc": "角色弧线描述",
            "traits": {{
                "personality": "性格描述",
                "speaking_style": "说话风格",
                "background": "背景信息",
                "relationships": {{"其他角色名": "关系描述"}}
            }}
        }}
    ]
}}
```

以下是小说内容：
{chapters_content}
""",

    "character_merge": """你是一位专业的影视编剧顾问。请将以下多批角色提取结果合并去重，输出一个完整的角色列表 JSON。

要求：
1. 同一角色在不同批次中可能有不同别名，请合并为一个角色
2. 合并时保留最完整的 traits 信息
3. 重新编号角色的 id（从 char_001 开始）
4. 按角色重要程度排序

现有角色批次：
{existing_characters}

新增角色批次：
{new_characters}

请输出合并后的完整 JSON，格式同上。
""",

    "script_generation": """你是一位经验丰富的影视编剧。请将以下小说章节内容改编为剧本，输出格式为 YAML。

## 剧本格式规范

必须严格遵循以下 YAML Schema：

```yaml
scenes:
  - scene_id: "scene_XXX_XXX"
    act_ref: "act_XXX"
    location: "场景地点"
    int_ext: "INT|EXT|INT/EXT"
    time_of_day: "DAY|NIGHT|DAWN|DUSK|CONTINUOUS"
    characters_present: ["char_XXX"]
    beats:
      - type: "dialogue"
        char_ref: "char_XXX"
        line: "台词内容"
        parenthetical: "（小动作提示）"
        emotion: "情绪"
      - type: "action"
        content: "动作描写"
      - type: "direction"
        content: "镜头/舞台指示"
    transition: "CUT TO|FADE IN|FADE OUT|DISSOLVE TO|SMASH CUT|MATCH CUT"
```

## 角色信息（必须使用这些角色 ID）

{character_profiles}

## 上一章摘要（保持剧情连贯性）

{previous_summary}

## 当前章节内容（第{chapter_index}章：{chapter_title}）

{chapter_content}

## 改编要求

1. 将小说的叙述性描写转化为具体的动作描写和镜头指示
2. 对白要口语化、符合角色性格
3. 合理拆分场景，每个场景有明确的地点和时间
4. 注意情绪标签的准确性
5. 确保所有 char_ref 引用已定义的角色 ID

请直接输出 YAML，不要包含其他说明文字。
""",

    "script_edit": """你是一位专业的剧本编辑。请根据用户的修改指令，修改以下 YAML 剧本内容。

## 当前剧本 YAML

{current_yaml}

## 角色特征参考

{character_profiles}

## 修改指令

{user_instruction}

## 要求

1. 只修改指令要求的部分，不要擅自修改其他内容
2. 返回修改后的完整 YAML（不要只返回差异部分）
3. 保持 YAML 格式正确
4. 保持角色 ID 引用一致

请直接输出修改后的完整 YAML，不要包含其他说明文字。
""",
}