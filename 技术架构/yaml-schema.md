# YAML Schema 定义文档 — AI 小说转剧本工具

**日期**：2026-06-06
**版本**：v1.0
**用途**：定义剧本输出格式，供工具代码和用户阅读参考

---

## 一、设计理念

本 Schema 的设计目标是在 **可读性** 与 **机器可解析性** 之间取得平衡：

1. **贴近行业标准剧本格式** — 采用好莱坞/国内影视行业通用的"幕→场景→节拍"三级结构，确保输出的 YAML 剧本对编剧、导演等从业者来说是熟悉的。
2. **强引用约束** — 角色（`char_ref`）、幕（`act_ref`）均通过 ID 引用而非字符串重复，避免角色名不一致、拼写错误等问题。
3. **足够丰富但不臃肿** — 覆盖场景地点、内/外景、时间、转场等专业元素，同时不引入过于冷门的字段。
4. **可扩展** — 使用 `notes` 数组预留自由文本空间，制作团队可以添加特效、改编建议等标注。

---

## 二、Schema 定义

### 2.1 整体结构

```yaml
meta:              # 元信息
  title:           # 剧本标题（string）
  author:          # 原著作者（string）
  adapter:         # 改编/编剧（string，可选）
  version:         # 版本号（string，如 "v1.0"）
  genre:           # 类型（string，如 "悬疑"、"爱情"、"科幻"）
  source:          # 原作来源（string，如 "小说《三体》第一章至第五章"）
  logline:         # 一句话梗概（string，可选）

characters:        # 角色表（array of Character）
acts:              # 幕（array of Act）
notes:             # 全局备注（array of Note，可选）
```

---

### 2.2 Character（角色）

```yaml
- id:              # 唯一标识（string，如 "char_001"）
  name:            # 显示名（string）
  aliases:         # 别名/昵称列表（array of string，可选，如 ["老李", "李工"]）
  role:            # 角色类型（enum: "protagonist" | "antagonist" | "supporting" | "extra"）
  arc:             # 人物弧线描述（string，一段话概括角色的成长/变化轨迹）
```

**设计理由**：
- `id` 是全局唯一标识，场景中的对白通过 `char_ref` 引用此 ID，避免角色名拼写不一致。
- `aliases` 用于处理小说中同一角色的不同称呼（如"老王"、"王师傅"、"他"），帮助 AI 在解析时正确归并。
- `role` 枚举值让下游工具（如自动生成通告单）能快速区分主次角色。
- `arc` 是对角色整个故事线的概括，AI 生成时参考此字段保持角色行为的一致性。

---

### 2.3 Act（幕）

```yaml
- act_id:          # 幕编号（string，如 "act_001"）
  title:           # 幕标题（string，如 "命运的开端"）
  summary:         # 幕摘要（string，概括本幕的核心情节）
  scenes:          # 本幕包含的场景列表（array of Scene）
```

**设计理由**：
- 在本工具的映射规则中，**1 章 = 1 幕**，因此 `act_id` 与章节序号直接对应。
- `summary` 供用户快速浏览剧本结构，也为 AI 生成下一幕时提供上下文。

---

### 2.4 Scene（场景）— 核心结构

```yaml
- scene_id:        # 场景唯一标识（string，如 "scene_001_001"）
  act_ref:         # 所属幕的 ID 引用（string，如 "act_001"）
  location:        # 场景地点（string，如 "北京·胡同巷口"）
  int_ext:         # 内/外景（enum: "INT" | "EXT" | "INT/EXT"）
  time_of_day:     # 时间段（enum: "DAY" | "NIGHT" | "DAWN" | "DUSK" | "CONTINUOUS"）
  characters_present:  # 出场角色 ID 列表（array of string，引用 characters[].id）
  beats:           # 节拍序列（array of Beat）
  transition:      # 转场方式（enum: "CUT TO" | "FADE IN" | "FADE OUT" |
                   #            "DISSOLVE TO" | "SMASH CUT" | "MATCH CUT"）
```

**设计理由**：
- `int_ext` 和 `time_of_day` 是标准剧本格式必备元素，导演和摄影指导依赖这些信息做拍摄准备。
- `INT/EXT` 混合选项覆盖"在室内透过窗户看外面"等场景。
- `CONTINUOUS` 表示时间连续，常用于两个场景之间的无缝衔接。
- `characters_present` 列表让通告单生成、演员调度等下游工具能快速提取所需信息。
- `transition` 覆盖了常见的影视转场术语，`SMASH CUT` 和 `MATCH CUT` 支持更具表现力的剪辑方式。

---

### 2.5 Beat（节拍）— 场景内的最小单元

一个 Beat 代表场景中的一个"节拍"，有三种类型：

#### 2.5.1 对白型 Beat（dialogue）

```yaml
- type: "dialogue"
  char_ref:        # 说话角色 ID（string，引用 characters[].id）
  line:            # 台词文本（string）
  parenthetical:   # 小动作/语气提示（string，可选，如 "（皱眉）"、"（低声）"）
  emotion:         # 情绪标签（string，可选，如 "愤怒"、"悲伤"、"紧张"）
```

#### 2.5.2 动作型 Beat（action）

```yaml
- type: "action"
  content:         # 动作描写文本（string，如 "他猛地站起来，椅子向后倒去"）
```

#### 2.5.3 舞台指示型 Beat（direction）

```yaml
- type: "direction"
  content:         # 舞台指示文本（string，如 "镜头缓缓推向桌面上的信封"）
```

**设计理由**：
- 三种类型覆盖了剧本中所有基本元素：对白、动作、镜头指示。
- `parenthetical` 是专业剧本中的标准元素，用于标注角色说话时的小动作或语气，帮助演员理解表演方式。
- `emotion` 是本工具特有的字段，服务于 AI 生成时的角色一致性，也方便导演快速把握场景情绪。
- `direction` 专门用于镜头/画面指示，与 `action`（角色动作）区分开，符合专业剧本的分工习惯。

---

### 2.6 Note（备注）

```yaml
- tag:             # 分类标签（string，如 "vfx"、"rewrite"、"costume"、"music"）
  comment:         # 备注内容（string）
```

**设计理由**：
- 全局备注用于制作团队添加特效需求、服装建议、音乐方向等标注，不影响剧本正文。
- `tag` 支持按类型筛选，方便不同部门（特效组、服装组、音乐组）快速定位相关备注。

---

## 三、完整示例

```yaml
meta:
  title: "三体·红岸基地"
  author: "刘慈欣"
  adapter: "AI 辅助改编"
  version: "v1.0"
  genre: "科幻"
  source: "小说《三体》第一章至第三章"
  logline: "文革时期，天体物理学家叶文洁在红岸基地向宇宙发出信号，开启了人类与三体文明的首次接触。"

characters:
  - id: "char_001"
    name: "叶文洁"
    aliases: ["文洁"]
    role: "protagonist"
    arc: "从理想主义的天体物理学家，因遭遇背叛和对人类的绝望，逐渐走向向宇宙发出信号的极端决定。"
  - id: "char_002"
    name: "杨卫宁"
    aliases: ["杨主任"]
    role: "supporting"
    arc: "红岸基地主任，为人正直保守，对叶文洁有好感但最终被她利用。"

acts:
  - act_id: "act_001"
    title: "疯狂年代"
    summary: "文革背景下，叶文洁目睹父亲被害，对人类社会产生深刻怀疑。"
    scenes:
      - scene_id: "scene_001_001"
        act_ref: "act_001"
        location: "清华大学·大礼堂"
        int_ext: "INT"
        time_of_day: "DAY"
        characters_present: ["char_001"]
        beats:
          - type: "action"
            content: "大礼堂内挤满了人，台上挂着横幅。叶文洁坐在角落，低着头。"
          - type: "dialogue"
            char_ref: "char_001"
            line: "（画外音）那是我最后一次相信，正义会自然到来。"
            emotion: "悲痛"
          - type: "direction"
            content: "画面切换为慢镜头，叶文洁的泪滴落在膝盖的笔记本上。"
        transition: "CUT TO"

notes:
  - tag: "costume"
    comment: "叶文洁出场服装：1967年典型灰蓝色工装，戴袖章"
```

---

## 四、字符编码与格式规范

| 规范项 | 要求 |
|--------|------|
| 编码 | UTF-8 |
| 缩进 | 2 空格（严禁 Tab） |
| 换行 | LF（Unix 风格） |
| 字符串引号 | 对白和描写内容使用双引号 `"..."` |
| 注释 | 允许使用 `#` 行注释 |
| 文件扩展名 | `.yaml` |

---

## 五、字段完整索引

| 层级 | 字段 | 类型 | 必填 | 枚举值 |
|------|------|------|------|--------|
| meta | title | string | ✅ | — |
| meta | author | string | ✅ | — |
| meta | adapter | string | ❌ | — |
| meta | version | string | ✅ | — |
| meta | genre | string | ✅ | — |
| meta | source | string | ✅ | — |
| meta | logline | string | ❌ | — |
| character | id | string | ✅ | — |
| character | name | string | ✅ | — |
| character | aliases | array[string] | ❌ | — |
| character | role | string | ✅ | protagonist / antagonist / supporting / extra |
| character | arc | string | ✅ | — |
| act | act_id | string | ✅ | — |
| act | title | string | ✅ | — |
| act | summary | string | ✅ | — |
| act | scenes | array[Scene] | ✅ | — |
| scene | scene_id | string | ✅ | — |
| scene | act_ref | string | ✅ | — |
| scene | location | string | ✅ | — |
| scene | int_ext | string | ✅ | INT / EXT / INT/EXT |
| scene | time_of_day | string | ✅ | DAY / NIGHT / DAWN / DUSK / CONTINUOUS |
| scene | characters_present | array[string] | ✅ | — |
| scene | beats | array[Beat] | ✅ | — |
| scene | transition | string | ✅ | CUT TO / FADE IN / FADE OUT / DISSOLVE TO / SMASH CUT / MATCH CUT |
| beat(dialogue) | type | string | ✅ | dialogue |
| beat(dialogue) | char_ref | string | ✅ | — |
| beat(dialogue) | line | string | ✅ | — |
| beat(dialogue) | parenthetical | string | ❌ | — |
| beat(dialogue) | emotion | string | ❌ | — |
| beat(action) | type | string | ✅ | action |
| beat(action) | content | string | ✅ | — |
| beat(direction) | type | string | ✅ | direction |
| beat(direction) | content | string | ✅ | — |
| note | tag | string | ✅ | — |
| note | comment | string | ✅ | — |
