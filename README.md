# AI 小说转剧本工具

将小说 `.txt` 文件转换为结构化 YAML 剧本，支持逐章 AI 生成与手动编辑。

## 功能特性

- **章节解析** — 自动识别小说中的章节标题（支持中文数字、阿拉伯数字等多种格式）
- **角色提取** — 调用 AI 全局扫描小说内容，提取角色信息（姓名、性格、说话风格、人际关系等）
- **逐章生成** — 每章独立调用 AI 生成剧本 YAML 片段，保持剧情连贯性
- **手动编辑** — 左侧剧本编辑区支持直接修改 YAML 内容
- **AI 编辑助手** — 右侧对话框支持自然语言指令修改剧本（如"把主角的台词改得更悲伤"）
- **导出下载** — 合并所有章节，导出完整 YAML 剧本文件

## 环境要求

- Python 3.10+
- 阿里云百炼 API Key（[获取地址](https://bailian.console.aliyun.com/)）

## 安装

```bash
git clone <repo-url>
cd novel-to-script
pip install -r requirements.txt
```

## 配置

编辑 `config.py`，修改以下配置项：

```python
BAILIAN_API_KEY = "你的百炼 API Key"
```

其他配置项（模型选择、重试次数、生成参数等）可按需调整。

## 使用方法

### 启动应用

```bash
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`。

### 操作流程

1. **上传小说** — 拖拽 `.txt` 文件到上传区，或输入本地文件夹路径后点击「扫描文件夹」
2. **选择章节** — 勾选需要转换的章节（可多选）
3. **填写信息** — 输入剧本标题、作者、类型
4. **开始转换** — 点击「开始转换」，AI 自动提取角色信息
5. **逐章生成** — 进入生成页面，AI 逐章生成剧本 YAML
   - 左侧：剧本内容，可手动编辑
   - 右侧：AI 编辑助手，输入自然语言指令修改剧本
6. **确认导出** — 逐章确认后，点击「导出完整剧本」下载 YAML 文件

## 项目结构

```
novel-to-script/
├── app.py                  # Streamlit 主应用
├── config.py               # 全局配置（API Key、模型、路径等）
├── bailian_client.py       # 百炼 API 客户端封装
├── chapter_parser.py       # 章节解析模块
├── prompt_templates.py     # AI Prompt 模板
├── character_extractor.py  # 角色提取模块
├── script_generator.py     # 剧本生成模块
├── script_editor.py        # AI 编辑助手模块
├── yaml_manager.py         # YAML 读写与校验
├── requirements.txt        # Python 依赖
├── 小说素材/               # 示例小说文件夹
└── output/                 # 输出目录（自动创建）
```

## 依赖

| 包 | 用途 |
|---|---|
| `streamlit>=1.30.0` | Web 界面 |
| `openai>=1.0.0` | 百炼 API 调用（OpenAI 兼容接口） |
| `pyyaml>=6.0` | YAML 读写 |

## 常见问题

**Q: 角色提取失败怎么办？**

检查 `config.py` 中的 API Key 是否正确，以及网络是否能访问百炼 API。也可以点击「跳过」使用空角色表继续生成剧本。

**Q: 生成的剧本格式不对怎么办？**

系统会自动校验生成的 YAML 格式，如果校验失败会自动重试（最多 2 次）。也可以在左侧编辑区手动修改，或使用 AI 编辑助手修复。

**Q: 上传的文件编码不是 UTF-8？**

系统仅支持 UTF-8 编码的 `.txt` 文件。请将文件另存为 UTF-8 编码后重新上传。