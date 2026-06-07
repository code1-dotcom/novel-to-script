# 工具架构设计文档 v2.0 — AI 小说转剧本工具（前后端分离）

**日期**：2026-06-07
**版本**：v2.0
**状态**：设计阶段（待实现）
**变更**：前端由 Streamlit 替换为纯 HTML+CSS+JS，后端由 FastAPI 提供 REST API

---

## 一、变更理由

| Streamlit v1.0 的问题 | HTML 前端 v2.0 的解决 |
|------------------------|----------------------|
| checkbox 在嵌套布局中状态不同步 | 原生 DOM 事件，无状态延迟 |
| 全选按钮触发 rerun 不可靠 | 原生 JS 批量操作，精准控制 |
| UI 受 Streamlit 组件限制 | 完全自由的 HTML/CSS 布局 |
| 无法自定义交互细节 | JS 自由控制任何交互 |

---

## 二、新架构总览

```
┌──────────────────────────────────────────────────┐
│              浏览器（前端 SPA）                    │
│  index.html + style.css + app.js                 │
│  章节选择 · 三步确认 · 剧本编辑 · AI 对话         │
└────────────────────┬─────────────────────────────┘
                     │ HTTP / fetch
                     ▼
┌──────────────────────────────────────────────────┐
│            FastAPI 后端 (server.py)               │
│  路由层：接收请求、参数校验、返回 JSON             │
└──────────┬───────────────────────────────────────┘
           │
    ┌──────┴──────┬──────────────┬──────────────┐
    ▼             ▼              ▼              ▼
┌────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐
│章节解析  │ │角色提取   │ │剧本生成    │ │AI编辑辅助  │
│(同v1.0) │ │(同v1.0)  │ │(同v1.0)  │ │(同v1.0)  │
└────────┘ └──────────┘ └───────────┘ └──────────┘
```

**核心原则**：后端 6 个模块（`bailian_client.py`、`chapter_parser.py`、`character_extractor.py`、`script_generator.py`、`script_editor.py`、`yaml_manager.py`）**代码完全不变**，只新增 `server.py` 做路由层和 `static/` 目录放前端。

---

## 三、项目结构

```
novel-to-script/
├── environment.yml
├── requirements.txt
├── config.py                 # API 配置（不变）
├── server.py                 # 🆕 FastAPI 应用入口
├── bailian_client.py         # 百炼客户端（不变）
├── chapter_parser.py         # 章节解析（不变）
├── character_extractor.py    # 角色提取（不变）
├── script_generator.py       # 剧本生成（不变）
├── script_editor.py          # AI 编辑（不变）
├── yaml_manager.py           # YAML 管理（不变）
├── prompt_templates.py       # Prompt 模板（不变）
├── static/                   # 🆕 前端文件
│   ├── index.html            # 单页应用主文件
│   ├── style.css             # 样式
│   └── app.js                # 交互逻辑
├── 小说素材/
├── 技术架构/
│   ├── yaml-schema.md
│   └── architecture-design-v2.md
└── README.md
```

---

## 四、API 端点设计

**Base URL**：`http://localhost:8000`

### 4.1 章节解析

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/parse/files` | 上传多个 txt 文件，返回章节列表 |
| POST | `/api/parse/directory` | 扫描文件夹路径，返回章节列表 |

**POST /api/parse/files**
```
Request: multipart/form-data (files: [txt, txt, ...])
Response:
{
  "chapters_data": [
    {
      "file_name": "《深渊代码》.txt",
      "chapters": [
        {"index": 0, "title": "第一章 深渊初现", "content": "...", "char_count": 3200},
        ...
      ]
    }
  ]
}
```

**POST /api/parse/directory**
```
Request: {"dir_path": "F:\\novel-to-script\\小说素材"}
Response: 同上
```

---

### 4.2 角色提取

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/extract/characters` | 从选中章节提取角色，支持流式 SSE |

**POST /api/extract/characters**
```
Request:
{
  "selected_chapters": [
    {"file_idx": 0, "ch_idx": 0},
    {"file_idx": 0, "ch_idx": 1}
  ],
  "chapters_data": [...]   // 前端回传章节数据
}

Response (SSE 流式):
event: progress
data: {"progress": 30, "message": "正在分析角色..."}

event: progress
data: {"progress": 80, "message": "正在保存角色特征..."}

event: complete
data: {
  "characters": [
    {
      "id": "char_001",
      "name": "林锐",
      "aliases": ["林哥"],
      "role": "protagonist",
      "arc": "...",
      "traits": {
        "personality": "...",
        "speaking_style": "...",
        "background": "...",
        "relationships": {}
      }
    }
  ]
}
```

---

### 4.3 角色确认

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/confirm/characters` | 保存用户编辑后的角色信息 |
| POST | `/api/confirm/profiles` | 保存用户编辑后的角色性格 |

**POST /api/confirm/characters**
```
Request: {"characters": [...]}    // 前端编辑后的角色列表（名称、别名、类型）
Response: {"characters": [...], "profiles_path": "output/character_profiles.json"}
```

**POST /api/confirm/profiles**
```
Request: {"characters": [...]}    // 含完整 traits 的角色列表
Response: {"ok": true}
```

---

### 4.4 剧本生成

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/generate/chapter` | 生成单章剧本，SSE 流式输出 |

**POST /api/generate/chapter**
```
Request:
{
  "chapter_content": "小说正文...",
  "chapter_index": 1,
  "chapter_title": "深渊初现",
  "characters": {...},           // 角色 profiles
  "previous_summary": ""         // 上章摘要
}

Response (SSE 流式):
event: token
data: {"text": "scenes:"}

event: token
data: {"text": "\n  - scene_id:"}

...（逐 token 推送）

event: complete
data: {"yaml": "...", "summary": "本幕摘要...", "errors": []}
```

---

### 4.5 AI 编辑

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/edit/script` | AI 对话式编辑剧本 |

**POST /api/edit/script**
```
Request:
{
  "instruction": "把主角台词改得更悲伤",
  "current_yaml": "...",
  "character_profiles": {...},
  "conversation_history": [...]
}

Response:
{
  "modified_yaml": "...",
  "diff": "...",
  "messages": [...]
}
```

---

### 4.6 导出

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/export` | 合并所有章节，导出完整 YAML |

**POST /api/export**
```
Request:
{
  "yaml_pieces": ["...", "..."],
  "meta": {"title": "...", "author": "...", ...},
  "characters": [...]
}

Response:
{
  "yaml": "完整 YAML 文本...",
  "errors": []
}
```

---

## 五、前端页面设计

### 5.1 整体结构（单页 SPA）

```
┌─────────────────────────────────────────────┐
│  🎬 AI 小说转剧本工具                        │
├─────────────────────────────────────────────┤
│                                             │
│  [页面容器 #page-container]                  │
│                                             │
│  ┌─ 步骤一：上传 ──────────────────────────┐ │
│  │  方式1: 文件夹路径输入 + 扫描按钮        │ │
│  │  方式2: 拖拽/点击上传多个 txt           │ │
│  │                                         │ │
│  │  上传后显示章节列表（checkbox + 全选）   │ │
│  │  ☑ 全选 《深渊代码》                     │ │
│  │  ☑ 第一章 深渊初现                       │ │
│  │  ☑ 第二章 代码迷宫                       │ │
│  │                                         │ │
│  │  剧本标题: [______]  作者: [______]      │ │
│  │                                         │ │
│  │  [🚀 开始转换]                          │ │
│  └─────────────────────────────────────────┘ │
│                                             │
│  ┌─ 步骤二：角色确认 ──────────────────────┐ │
│  │  进度条: ████████░░ 80%                  │ │
│  │                                         │ │
│  │  子步骤2.1: 角色识别确认                 │ │
│  │  ┌──────┬──────┬──────┬────┐            │ │
│  │  │ 名称  │ 别名  │ 类型  │删除│            │ │
│  │  ├──────┼──────┼──────┼────┤            │ │
│  │  │ 林锐  │ 林哥  │ 主角  │ ✕  │            │ │
│  │  └──────┴──────┴──────┴────┘            │ │
│  │  [+ 添加角色] [确认并继续 →]             │ │
│  │                                         │ │
│  │  子步骤2.2: 角色性格确认                 │ │
│  │  [林锐] [苏瑶] [老张]  ← Tab            │ │
│  │  性格特征: [______________]              │ │
│  │  说话风格: [______________]              │ │
│  │  背景信息: [______________]              │ │
│  │  [确认并开始生成 →]                      │ │
│  └─────────────────────────────────────────┘ │
│                                             │
│  ┌─ 步骤三：剧本生成与编辑 ────────────────┐ │
│  │  ┌──────────────┬──────────────┐        │ │
│  │  │ 左侧(70%)     │ 右侧(30%)     │        │ │
│  │  │ 剧本编辑      │ AI 对话       │        │ │
│  │  │              │              │        │ │
│  │  │ [可编辑      │ 用户: 改台词  │        │ │
│  │  │  YAML显示    │ AI: 已修改    │        │ │
│  │  │  中英文对照]  │              │        │ │
│  │  │              │ [输入框]      │        │ │
│  │  └──────────────┴──────────────┘        │ │
│  │                                         │ │
│  │  [↩撤销]  [✅确认本章]  [⏹取消] [📥导出] │ │
│  └─────────────────────────────────────────┘ │
│                                             │
└─────────────────────────────────────────────┘
```

### 5.2 页面切换逻辑

单页应用，通过 JS 控制三个步骤 div 的显示/隐藏：

```javascript
// 步骤状态
let currentStep = 1;  // 1, 2, 3

function showStep(step) {
    document.querySelectorAll('.step').forEach(el => el.style.display = 'none');
    document.getElementById(`step-${step}`).style.display = 'block';
    currentStep = step;
}
```

### 5.3 关键交互

**章节选择（checkbox + 全选）**：
```html
<div class="file-group">
    <h4>📄 《深渊代码》.txt（2 章）</h4>
    <label><input type="checkbox" class="select-all" data-file="0"> 全选/取消</label>
    <label><input type="checkbox" name="chapter" value="0:0"> 第一章 深渊初现 (3200字)</label>
    <label><input type="checkbox" name="chapter" value="0:1"> 第二章 代码迷宫 (2800字)</label>
</div>
```

全选逻辑（纯 JS，无状态问题）：
```javascript
document.querySelectorAll('.select-all').forEach(btn => {
    btn.addEventListener('change', function() {
        const fileIdx = this.dataset.file;
        const checked = this.checked;
        document.querySelectorAll(`input[name="chapter"][value^="${fileIdx}:"]`)
            .forEach(cb => cb.checked = checked);
        updateStartButton();
    });
});
```

**流式输出**：使用 EventSource 或 fetch + ReadableStream：
```javascript
async function generateChapter() {
    const response = await fetch('/api/generate/chapter', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({...})
    });
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        // 解析 SSE 格式
        const text = decoder.decode(value);
        // 逐 token 追加到编辑区
        appendToEditor(text);
    }
}
```

**YAML 显示中英文对照**：前端 JS 替换，不传后端：
```javascript
const FIELD_MAP = {
    'scenes': '场景/scenes',
    'scene_id': '场景序号/scene_id',
    'location': '地点/location',
    // ...
};

function translateYaml(yamlText) {
    for (const [en, cn_en] of Object.entries(FIELD_MAP)) {
        const regex = new RegExp(`^(\\s*)${en}:`, 'gm');
        yamlText = yamlText.replace(regex, `$1${cn_en}:`);
    }
    return yamlText;
}
```

---

## 六、数据流

```
用户上传 txt → POST /api/parse/files → 返回章节列表 → 前端渲染 checkbox
                                                              │
用户勾选章节 + 填写元信息 + 点击"开始转换"                        │
                                                              ▼
POST /api/extract/characters (SSE) → 流式返回角色 → 前端渲染角色确认表
                                                              │
用户编辑角色（名称/别名/类型）→ 点击"确认并继续"                   │
                                                              ▼
POST /api/confirm/profiles → 保存 → 前端渲染性格确认 Tab
                                                              │
用户编辑性格 → 点击"确认并开始生成"                               │
                                                              ▼
POST /api/generate/chapter (SSE) → 逐 token 推送 YAML
        │
        ▼
左侧实时显示生成中的 YAML，右侧 AI 对话可用
        │
用户编辑 / AI 修改 → 点击"确认本章" → 循环到下一章
        │
        ▼
全部确认 → POST /api/export → 合并导出完整 YAML
```

---

## 七、Session 管理（后端）

用内存字典管理会话，无需数据库：

```python
# server.py
sessions = {}  # {session_id: SessionData}

class SessionData:
    chapters_data: list
    selected_keys: set
    meta: dict
    character_profiles: dict
    confirmed_yaml_pieces: list
    current_chapter_idx: int
    previous_summary: str
```

前端每次请求携带 `session_id`（首次由后端生成并返回）。

---

## 八、requirements.txt 更新

```
fastapi>=0.110.0
uvicorn>=0.29.0
python-multipart>=0.0.9
openai>=1.0.0
pyyaml>=6.0
```

新增：`fastapi`、`uvicorn`、`python-multipart`

---

## 九、启动方式

```bash
conda activate novel-to-script
pip install -r requirements.txt
python server.py
# 浏览器打开 http://localhost:8000
```

---

## 十、实现步骤（新）

| 步骤 | 内容 | 依赖 |
|------|------|------|
| **Step 1** | `server.py`：FastAPI 骨架 + 静态文件服务 | — |
| **Step 2** | API：`/api/parse/*` 端点（对接 chapter_parser） | Step 1 |
| **Step 3** | `static/index.html`：上传页 + 章节选择 UI | Step 2 |
| **Step 4** | API：`/api/extract/characters` (SSE) | Step 3 |
| **Step 5** | 前端：角色确认步骤（表格编辑 + Tab） | Step 4 |
| **Step 6** | API：`/api/confirm/*`、`/api/generate/chapter` (SSE) | Step 5 |
| **Step 7** | 前端：剧本编辑页（左右分栏 + YAML 中文对照） | Step 6 |
| **Step 8** | API：`/api/edit/script` + 前端 AI 对话 | Step 7 |
| **Step 9** | API：`/api/export` + 下载功能 | Step 8 |
| **Step 10** | 整体联调 + 样式美化 | Step 9 |
