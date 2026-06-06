# 工具架构设计文档 — AI 小说转剧本工具

**日期**：2026-06-06
**版本**：v1.0
**状态**：设计阶段（待实现）

---

## 一、产品概述

### 1.1 核心功能

用户上传小说 `.txt` 文本，工具自动解析章节结构，调用 AI 逐章将小说内容转换为结构化 YAML 剧本。每章生成后，用户可在左右分栏界面中手动编辑或通过 AI 对话进行修改，确认后再生成下一章。

### 1.2 核心交付物

| 交付物 | 说明 |
|--------|------|
| Streamlit Web 应用 | 用户交互界面 |
| YAML Schema 定义文档 | 剧本格式规范（另见 `yaml-schema.md`） |
| `character_profiles.json` | AI 角色特征工作文档 |
| 最终输出 YAML 文件 | 完整的结构化剧本 |

### 1.3 技术选型

| 项目 | 选择 | 理由 |
|------|------|------|
| 前端框架 | **Streamlit** | Python 原生，文本编辑+状态管理方便，左右分栏易实现 |
| Python 版本 | **Python 3.10+** | Streamlit 要求，conda 管理 |
| 环境管理 | **Conda + environment.yml + requirements.txt** | Conda 管理 Python 环境和核心依赖，pip 补充纯 Python 包 |
| LLM 平台 | **阿里云百炼平台** | 免费额度充足 |
| 主力模型 | **qwen-max** | 理解+生成能力强，适合剧本生成 |
| 辅助模型 | **qwen-plus** | 性价比高，适合角色提取、章节解析 |
| 数据格式 | **YAML** | 可读性好，符合行业标准剧本格式 |
| YAML 库 | **PyYAML** | 成熟稳定 |
| Conda | **Miniconda / Anaconda** | Python 环境隔离，依赖管理 |

---

## 二、系统架构

### 2.1 模块总览

```
novel-to-script/
├── environment.yml            # Conda 环境配置文件
├── requirements.txt           # pip 补充依赖
├── app.py                    # Streamlit 主应用入口
├── config.py                 # 配置管理（API Key、模型选择等）
├── chapter_parser.py         # 章节解析模块
├── character_extractor.py    # 角色提取模块
├── script_generator.py       # 剧本生成模块
├── script_editor.py          # AI 编辑辅助模块
├── yaml_manager.py           # YAML 读写与合并管理
├── prompt_templates.py       # Prompt 模板管理
├── bailian_client.py         # 百炼 API 客户端封装
├── README.md
└── docs/
    └── yaml-schema.md        # YAML Schema 定义文档
```

### 2.2 模块职责

```
┌─────────────────────────────────────────────────────┐
│                     app.py (主应用)                   │
│   页面路由 · Session State 管理 · 整体流程编排        │
└──────────┬──────────────────────────────────────────┘
           │
    ┌──────┴──────┬──────────────┬──────────────┐
    ▼             ▼              ▼              ▼
┌────────┐  ┌──────────┐  ┌───────────┐  ┌──────────┐
│章节解析  │  │角色提取   │  │剧本生成    │  │AI编辑辅助  │
│chapter  │  │character │  │script     │  │script    │
│_parser  │  │_extractor│  │_generator │  │_editor   │
└────────┘  └────┬─────┘  └─────┬─────┘  └────┬─────┘
                 │              │              │
            ┌────┴──────────────┴──────────────┘
            ▼
     ┌──────────────┐     ┌──────────────┐
     │百炼 API 客户端 │     │YAML 管理器    │
     │bailian_client │     │yaml_manager   │
     └──────────────┘     └──────────────┘
```

---

## 三、详细模块设计

### 3.1 `bailian_client.py` — 百炼 API 客户端

**职责**：封装百炼平台 OpenAI 兼容 API 的调用逻辑，提供统一调用接口。

```python
class BailianClient:
    def __init__(self, api_key: str, base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"):
        ...

    def chat(self, model: str, messages: list[dict],
             temperature: float = 0.7, max_tokens: int = 4096) -> str:
        """
        统一调用接口
        参数:
          - model: "qwen-max" 或 "qwen-plus"
          - messages: OpenAI 格式的消息列表
          - temperature: 生成温度
          - max_tokens: 最大 token 数
        返回: 模型生成的文本
        """

    def chat_json(self, model: str, messages: list[dict], **kwargs) -> dict:
        """
        调用并尝试解析 JSON 输出，用于需要结构化输出的场景
        """
```

**实现要点**：
- 使用 `openai` SDK，base_url 指向百炼平台
- 超时重试机制（最多 3 次，指数退避）
- 异常处理：API 限流、超时、返回格式错误等

---

### 3.2 `chapter_parser.py` — 章节解析模块

**职责**：读取 `.txt` 文件，识别并提取章节标题和对应正文。

```python
class ChapterParser:
    def __init__(self):
        # 支持的章节标题模式
        self.patterns = [
            r"^第[一二三四五六七八九十百千\d]+章[：:\s·.]*(.+)?$",
            r"^Chapter\s+\d+[：:\s]*(.+)?$",
            r"^卷[一二三四五六七八九十百千\d]+[：:\s]*(.+)?$",
            r"^[一二三四五六七八九十百千\d]+[、.]\s*(.+)$",
        ]

    def parse(self, text: str) -> list[dict]:
        """
        解析小说文本，返回章节列表

        返回格式:
        [
            {
                "index": 1,
                "title": "疯狂年代",
                "raw_title": "第一章 疯狂年代",
                "start_line": 42,
                "end_line": 156,
                "content": "完整章节正文..."
            },
            ...
        ]
        """

    def parse_file(self, file_path: str) -> list[dict]:
        """从文件路径读取并解析"""

    def parse_directory(self, dir_path: str) -> list[dict]:
        """
        扫描文件夹，读取所有 .txt 文件并解析

        返回格式:
        [
            {
                "file_name": "《深渊代码》.txt",
                "chapters": [  // 同 parse() 的返回格式
                    {"index": 1, "title": "...", "content": "..."},
                    ...
                ]
            },
            ...
        ]
        """

    def parse_uploaded_files(self, uploaded_files: list) -> list[dict]:
        """
        解析用户通过 st.file_uploader 上传的多个文件
        返回格式同 parse_directory
        """
```

**实现要点**：
- 逐行扫描，用正则匹配章节标题
- 匹配到的行作为新章节的起始
- 未匹配到标题的文本作为"序章"（index=0）
- 支持多文件输入：每个 txt 文件独立解析，在 UI 中以"文件名 → 章节列表"的树形结构展示
- 用户可勾选跨文件的任意章节进行转换
- 返回章节列表供用户在 UI 上勾选

---

### 3.3 `character_extractor.py` — 角色提取模块

**职责**：全局扫描整本小说（或用户选择的全部章节），提取角色信息并生成 `character_profiles.json`。

```python
class CharacterExtractor:
    def __init__(self, client: BailianClient):
        self.client = client

    def extract_characters(self, chapters_content: list[str]) -> dict:
        """
        从章节正文列表中提取角色信息

        返回格式:
        {
            "characters": [
                {
                    "id": "char_001",
                    "name": "叶文洁",
                    "aliases": ["文洁", "叶老师"],
                    "role": "protagonist",
                    "arc": "从理想主义天体物理学家...",
                    "traits": {
                        "personality": "冷静、理性，内心深处对人类充满矛盾情感",
                        "speaking_style": "说话简练，喜欢用隐喻",
                        "background": "清华大学天体物理学毕业生",
                        "relationships": {
                            "叶哲泰": "父亲，被批斗致死",
                            "杨卫宁": "同事，对其有好感"
                        }
                    }
                },
                ...
            ]
        }
        """

    def save_profiles(self, profiles: dict, output_path: str):
        """保存到 character_profiles.json"""
```

**实现要点**：
- 如果小说很长（超过 token 上限），分批扫描后合并去重
- Prompt 要求 AI 输出严格的 JSON 格式
- 生成的 `character_profiles.json` 供后续剧本生成模块读取

---

### 3.4 `script_generator.py` — 剧本生成模块

**职责**：逐章调用 AI，将小说正文转换为 YAML 剧本片段。

```python
class ScriptGenerator:
    def __init__(self, client: BailianClient):
        self.client = client

    def generate_chapter_script(
        self,
        chapter_content: str,
        chapter_index: int,
        chapter_title: str,
        characters: dict,          # character_profiles.json 中的角色表
        previous_summary: str = ""  # 上一幕的 summary，提供上下文
    ) -> str:
        """
        生成单章对应的剧本 YAML 片段

        返回: 符合 Schema 定义的 YAML 字符串（单幕+场景）
        """
```

**实现要点**：
- 每次调用时，将 `character_profiles.json` 中的角色信息和前一章 summary 作为上下文注入 prompt
- Prompt 明确要求输出符合 Schema 的 YAML 格式
- 对 AI 输出的 YAML 做基本校验（必须包含 `scenes`、`beats` 等必要字段）
- 如果 YAML 解析失败，自动重试（最多 2 次），在 prompt 中追加错误信息

---

### 3.5 `script_editor.py` — AI 编辑辅助模块

**职责**：处理右侧 AI 对话框的交互，根据用户指令修改剧本。

```python
class ScriptEditor:
    def __init__(self, client: BailianClient):
        self.client = client

    def apply_edit(
        self,
        user_instruction: str,
        current_yaml: str,          # 当前编辑区的 YAML 内容
        character_profiles: dict    # 角色特征文档
    ) -> str:
        """
        根据用户的自然语言指令修改剧本

        示例指令:
          - "把第二场戏的转场改成 SMASH CUT"
          - "叶文洁的台词改得更悲伤一些"
          - "在第三场增加一个她看向窗外的动作描写"
          - "删除最后一个 direction"

        返回: 修改后的完整 YAML 字符串
        """
```

**实现要点**：
- 维护对话历史（最近 10 轮），支持多轮修改
- Prompt 中注入当前 YAML 和角色特征，要求 AI 返回修改后的完整 YAML
- 修改前后做 diff，让用户看到具体变化

---

### 3.6 `yaml_manager.py` — YAML 读写管理

**职责**：YAML 文件的读取、写入、合并、校验。

```python
class YAMLManager:
    def load(self, file_path: str) -> dict:
        """读取 YAML 文件"""

    def save(self, data: dict, file_path: str):
        """写入 YAML 文件，确保 2 空格缩进"""

    def merge_acts(self, yaml_pieces: list[str], meta: dict, characters: list[dict]) -> dict:
        """
        合并所有章节的 YAML 片段为完整剧本

        参数:
          - yaml_pieces: 每章生成的 YAML 字符串列表
          - meta: 元信息
          - characters: 角色表

        返回: 完整的剧本 dict
        """

    def validate(self, data: dict) -> list[str]:
        """
        校验 YAML 是否符合 Schema
        返回错误信息列表（空列表表示无错误）
        """

    def to_display_string(self, data: dict) -> str:
        """将 dict 转为格式化的 YAML 字符串，用于编辑区展示"""
```

---

### 3.7 `prompt_templates.py` — Prompt 模板

**职责**：集中管理所有 Prompt 模板。

```python
PROMPTS = {

    "character_extraction": """你是一位专业的影视编剧顾问。请阅读以下小说章节内容，
提取所有重要角色的信息，并以 JSON 格式输出。

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

    "script_generation": """你是一位经验丰富的影视编剧。请将以下小说章节内容改编为剧本，
输出格式为 YAML。

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

    "script_edit": """你是一位专业的剧本编辑。请根据用户的修改指令，
修改以下 YAML 剧本内容。

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
"""
}
```

---

## 四、用户交互流程

### 4.1 完整流程图

```
┌──────────────────────────────────────────────────────────────────┐
│                       页面一：上传与配置                           │
│                                                                  │
│  [上传区域] 选择文件夹 或 上传多个 .txt 文件                       │
│                                                                  │
│  ── 系统自动解析章节 ──                                           │
│                                                                  │
│  ☑ 第一章 疯狂年代                                                │
│  ☑ 第二章 寂静的春天                                              │
│  ☐ 第三章 红岸之上（未勾选则跳过）                                  │
│  ☑ 第四章 ...                                                     │
│                                                                  │
│  [填写元信息]                                                     │
│  标题：__________  类型：__________  作者：__________              │
│                                                                  │
│              [开始转换]                                           │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                    预处理：角色提取（自动，后台执行）                 │
│                                                                  │
│  ████████████████████░░░░ 75%  正在提取角色信息...                 │
│                                                                  │
│  已识别角色：叶文洁、杨卫宁、叶哲泰、...                            │
│                                                                  │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│               页面二：生成与编辑（左右分栏）                        │
│                                                                  │
│  ┌─────────────────────────┬───────────────────┐                │
│  │  左侧：剧本编辑区 (70%)  │ 右侧：AI 对话 (30%) │               │
│  │                          │                    │               │
│  │  当前：第 2/5 章         │ AI: 剧本已生成。   │               │
│  │  "第二章 寂静的春天"      │     您可以告诉我   │               │
│  │                          │     需要修改的地方 │               │
│  │  [可编辑的 YAML 内容]    │                    │               │
│  │                          │ 用户: 把叶文洁的   │               │
│  │  scenes:                 │ 台词改得更悲伤     │               │
│  │    - scene_id: ...       │                    │               │
│  │      beats:              │ AI: 已修改。变化： │               │
│  │        - type: dialogue  │     - 添加了       │               │
│  │          line: ...       │       emotion:    │               │
│  │        - type: action    │       "悲痛"      │               │
│  │          content: ...    │                    │               │
│  │                          │                    │               │
│  │                          │ [输入框] [发送]    │               │
│  │                          │                    │               │
│  ├──────────────────────────┴───────────────────┤                │
│  │                                               │                │
│  │     [撤销修改]  [确认本章 ✓]  [导出完整剧本]    │                │
│  └───────────────────────────────────────────────┘                │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 页面一详细设计

**上传区域**：
- **方式一（文件夹选择）**：`st.text_input` 输入本地文件夹路径（如 `F:\\novel-to-script\\小说素材`）+ `st.button` 扫描，自动读取该目录下所有 `.txt` 文件
- **方式二（多文件上传）**：`st.file_uploader(accept_multiple_files=True)`，支持用户按住 Ctrl 多选 `.txt` 文件
- 两种方式互斥，优先以文件夹方式为准
- 上传/扫描后自动调用 `ChapterParser.parse_file()` 解析每个 `.txt`

**章节选择区域**：
- 如果输入了文件夹/多文件，按文件分组展示：
```
  ☑ 《深渊代码》.txt
    ☑ 第一章 深渊初现
    ☑ 第二章 代码迷宫
  ☑ 《猎场玫瑰》.txt
    ☐ 第一章 玫瑰刺
    ☑ 第二章 猎场
  ```
- 支持文件级全选/取消全选，也支持单章勾选
- 每个章节显示标题和预估字数
- 未选择任何章节时"开始转换"按钮禁用

**元信息填写区域**：
- 标题（自动从文件名提取，可编辑）
- 作者（文本输入）
- 类型（下拉选择 + 自定义输入）
- 这些信息最终写入 YAML 的 `meta`

### 4.3 页面二详细设计

**左侧编辑区（70% 宽度）**：
- 顶部显示当前进度：`当前：第 2/5 章`
- 使用 `st.text_area` 展示 YAML 内容，允许直接编辑
- 编辑区支持语法高亮（可选，用 `st.code` 或自定义组件）
- 用户手动编辑后，AI 对话框不需要感知变化

**右侧 AI 对话区（30% 宽度）**：
- 对话历史展示区（滚动）
- 输入框 + 发送按钮
- AI 修改后，自动更新左侧编辑区的内容
- 修改操作有"撤销"能力（维护编辑历史栈）

**底部操作栏**：
- **撤销修改**：回退到上一版本（支持多级撤销）
- **确认本章**：将当前编辑区内容保存，进入下一章生成
- **导出完整剧本**：合并所有已确认章节为完整 YAML，下载

---

## 五、Session State 管理

Streamlit 的 Session State 是管理多步骤流程的关键：

```python
# app.py 中的 Session State 结构
if "workflow" not in st.session_state:
    st.session_state.workflow = {
        # 阶段控制
        "stage": "upload",              # upload → extracting → generating → done

        # 页面一数据
        "uploaded_file": None,
        "chapters": [],                  # ChapterParser 解析结果
        "selected_chapters": [],         # 用户勾选的章节索引
        "meta": {},                     # 用户填写的元信息

        # 预处理数据
        "character_profiles": {},       # CharacterExtractor 结果
        "profiles_path": "",             # JSON 文件保存路径

        # 页面二数据
        "current_chapter_idx": 0,       # 当前正在处理的章节序号
        "confirmed_yaml_pieces": [],     # 已确认的各章 YAML 字符串列表
        "current_yaml": "",              # 当前编辑区的 YAML
        "edit_history": [],              # 编辑历史栈（用于撤销）
        "ai_chat_history": [],           # AI 对话历史
    }
  ```

---

## 六、数据流

### 6.1 角色特征文档（character_profiles.json）

```
小说全文 → qwen-plus → JSON → character_profiles.json
```

**文件位置**：与最终输出的 YAML 同目录

**结构**：
```json
{
    "characters": [
        {
            "id": "char_001",
            "name": "叶文洁",
            "aliases": ["文洁", "叶老师"],
            "role": "protagonist",
            "arc": "角色弧线...",
            "traits": {
                "personality": "冷静、理性...",
                "speaking_style": "说话简练...",
                "background": "清华大学...",
                "relationships": {"叶哲泰": "父亲"}
            }
        }
    ]
}
```

**使用方式**：
- 剧本生成时：将 `characters` 数组（不含 `traits`）注入 YAML 的 `characters` 字段；将完整 traits 信息作为 prompt 上下文
- AI 编辑时：将完整 traits 信息注入 prompt，确保修改符合角色性格

### 6.2 输出文件

```
output/
├── screenplay.yaml              # 最终完整剧本
├── character_profiles.json       # 角色特征工作文档
└── chapters/                     # 各章中间产物（可选保留）
    ├── chapter_001.yaml
    └── chapter_002.yaml
```

---

## 七、错误处理策略

| 场景 | 处理方式 |
|------|---------|
| 章节解析失败（未识别到任何章节标题） | 提示用户，提供"手动输入章节分割"的备选方案（按固定行数分割） |
| 角色提取 API 失败 | 自动重试 3 次，仍失败则提示用户检查 API Key，并提供"跳过角色提取"选项（使用默认空角色表） |
| 剧本生成 YAML 解析失败 | 自动重试 2 次（在 prompt 中追加错误信息），仍失败则将原始文本展示给用户，标记"需要手动修复" |
| AI 编辑返回非法 YAML | 保留编辑前的内容，提示用户"AI 修改格式有误，请重试或手动编辑" |
| 用户跳过某些章节 | 正常处理，最终剧本中不包含跳过的章节，但 act_id 保持连续编号 |

---

## 八、性能优化

| 优化点 | 方案 |
|--------|------|
| 长文本超过 token 上限 | 分段处理：每段 ≤ 6000 tokens，分段提取后合并 |
| 角色信息注入增加 prompt 长度 | 只注入当前章节涉及的角色（通过 `characters_present` 筛选），不每次都注入全部角色 |
| YAML 编辑区响应速度 | 使用 `st.text_area` 而非自定义富文本编辑器，保证流式编辑体验 |
| API 调用延迟 | 生成时展示进度条（`st.spinner`），编辑时展示"正在思考..." |

---

## 九、实现步骤建议（给 Trae 的分步指引）

建议按以下顺序逐步实现：

| 步骤 | 内容 | 预估复杂度 |
|------|------|-----------|
| **Step 1** | 项目初始化：创建 conda 环境（`environment.yml`）、安装依赖、`config.py` | ⭐ |
| **Step 2** | `bailian_client.py`：封装 API 调用，测试连通性 | ⭐⭐ |
| **Step 3** | `chapter_parser.py`：实现章节解析，准备测试用 .txt 文件 | ⭐⭐ |
| **Step 4** | `prompt_templates.py` + `character_extractor.py`：角色提取 | ⭐⭐⭐ |
| **Step 5** | `yaml_manager.py`：YAML 读写、合并、校验 | ⭐⭐ |
| **Step 6** | `script_generator.py`：单章剧本生成 | ⭐⭐⭐ |
| **Step 7** | `app.py` 页面一：上传 + 章节选择 + 元信息填写 | ⭐⭐ |
| **Step 8** | `app.py` 页面二：左右分栏编辑界面 | ⭐⭐⭐ |
| **Step 9** | `script_editor.py`：AI 编辑辅助（右侧对话） | ⭐⭐⭐ |
| **Step 10** | 整体联调 + 错误处理 + 导出功能 | ⭐⭐ |

---

## 十、API 配置

```python
# config.py
BAILIAN_API_KEY = "sk-daaf5ed4aa784fb78f8567bcb2e39b97"
BAILIAN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL_PRIMARY = "qwen-max"     # 剧本生成
MODEL_SECONDARY = "qwen-plus"  # 角色提取
MAX_RETRIES = 3
TIMEOUT_SECONDS = 60
```

> **安全提示**：正式项目中 API Key 不应硬编码，建议使用环境变量或 `.env` 文件。此处为开发阶段简化处理。

---

## 十一、Conda 环境配置

### 11.1 environment.yml

```yaml
name: novel-to-script
channels:
  - defaults
  - conda-forge
dependencies:
  - python=3.10
  - pip
  - pip:
      - -r requirements.txt
```

### 11.2 requirements.txt

```text
streamlit>=1.30.0
openai>=1.0.0
pyyaml>=6.0
```

### 11.3 环境初始化命令

```bash
# 1. 创建并激活 conda 环境
conda env create -f environment.yml
conda activate novel-to-script

# 2. 安装 pip 依赖
pip install -r requirements.txt

# 3. 运行应用
streamlit run app.py
```

### 11.4 环境导出与复现

```bash
# 导出当前环境（用于分享或部署）
conda env export > environment.yml

# 更新依赖后重建
conda env update -f environment.yml --prune
```
