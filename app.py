"""app.py — Streamlit 主应用
AI 小说转剧本工具的用户交互界面。
页面一：上传 + 章节选择 + 元信息填写
页面二：左右分栏生成与编辑（含 AI 编辑助手）
"""

import streamlit as st
import os
import logging

from chapter_parser import ChapterParser
from character_extractor import CharacterExtractor
from script_generator import ScriptGenerator
from script_editor import ScriptEditor
from yaml_manager import YAMLManager
from bailian_client import BailianClient
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="AI 小说转剧本工具",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

GENRE_OPTIONS = ["科幻", "悬疑", "爱情", "奇幻", "武侠", "都市", "历史", "其他"]


def init_session_state():
    if "workflow" not in st.session_state:
        st.session_state.workflow = {
            "stage": "upload",
            "chapters": [],
            "selected_chapter_keys": set(),
            "meta": {"title": "", "author": "", "genre": "", "version": "1.0", "source": "AI 小说转剧本工具"},
            "character_profiles": {},
            "profiles_path": "",
            "current_chapter_idx": 0,
            "confirmed_yaml_pieces": [],
            "current_yaml": "",
            "edit_history": [],
            "ai_chat_history": [],
            "editor_messages": [],
        }

    if "folder_path" not in st.session_state:
        st.session_state.folder_path = ""

    if "scanned" not in st.session_state:
        st.session_state.scanned = False


def reset_chapter_selection():
    wf = st.session_state.workflow
    wf["selected_chapter_keys"] = set()
    keys_to_remove = [k for k in st.session_state if k.startswith("ch_select_")]
    for k in keys_to_remove:
        del st.session_state[k]


def auto_extract_title(chapters_data):
    wf = st.session_state.workflow
    if not wf["meta"]["title"] and chapters_data:
        first_file = chapters_data[0]
        file_name = first_file.get("file_name", "")
        if file_name:
            wf["meta"]["title"] = file_name.replace(".txt", "").strip()


def render_page_upload():
    st.title("🎬 AI 小说转剧本工具")
    st.markdown("将小说 `.txt` 文件转换为结构化 YAML 剧本，支持逐章 AI 生成与手动编辑")
    st.markdown("---")

    wf = st.session_state.workflow

    st.header("📁 上传小说")
    st.markdown("选择文件夹扫描或直接上传 `.txt` 文件")

    use_folder = st.checkbox("使用本地文件夹路径", key="use_folder_mode")

    if use_folder:
        col_path, col_btn = st.columns([4, 1])
        with col_path:
            folder_path = st.text_input(
                "文件夹路径（包含 .txt 文件）",
                value=st.session_state.folder_path,
                placeholder="例如: F:\\novel-to-script\\小说素材",
                key="folder_path_input",
                label_visibility="collapsed",
            )
            st.session_state.folder_path = folder_path
        with col_btn:
            scan_clicked = st.button("🔍 扫描文件夹", use_container_width=True)

        if scan_clicked:
            if folder_path and os.path.isdir(folder_path):
                with st.spinner("正在扫描文件夹..."):
                    try:
                        parser = ChapterParser()
                        results = parser.parse_directory(folder_path)
                    except Exception as e:
                        st.error(f"扫描文件夹失败: {e}")
                        return
                wf["chapters"] = results
                reset_chapter_selection()
                auto_extract_title(results)
                st.session_state.scanned = True
                total_chapters = sum(len(f["chapters"]) for f in results)
                st.success(f"已扫描 {len(results)} 个文件，共 {total_chapters} 个章节")
            else:
                st.error("文件夹路径无效，请检查后重试")
    else:
        uploaded_files = st.file_uploader(
            "上传 .txt 文件（可按住 Ctrl 多选）",
            type=["txt"],
            accept_multiple_files=True,
            key="uploaded_files_widget",
        )
        if uploaded_files:
            parser = ChapterParser()
            results, parse_errors = parser.parse_uploaded_files(uploaded_files)
            wf["chapters"] = results
            reset_chapter_selection()
            auto_extract_title(results)
            st.session_state.scanned = True
            total_chapters = sum(len(f["chapters"]) for f in results)
            st.success(f"已上传 {len(results)} 个文件，共 {total_chapters} 个章节")
            if parse_errors:
                for err in parse_errors:
                    st.warning(err)

    chapters_data = wf.get("chapters", [])
    if not chapters_data:
        st.info("👆 请先上传或扫描小说文件")
        return

    st.markdown("---")
    st.header("📑 选择章节")

    selected_keys: set[str] = set()
    total_chapter_count = 0
    # 先收集已存在的选中状态（来自上一次渲染的 session state）
    existing_selections = {
        k: v for k, v in st.session_state.items()
        if k.startswith("ch_select_") and v is True
    }

    for file_idx, file_data in enumerate(chapters_data):
        file_name = file_data["file_name"]
        file_chapters = file_data["chapters"]
        total_chapter_count += len(file_chapters)

        with st.expander(f"📄 {file_name}（{len(file_chapters)} 章）", expanded=True):
            select_all_key = f"select_all_{file_idx}"

            col_all, col_spacer = st.columns([1, 4])
            with col_all:
                all_selected = st.checkbox("全选 / 取消全选", key=select_all_key)

            if all_selected:
                for ch_idx in range(len(file_chapters)):
                    st.session_state[f"ch_select_{file_idx}_{ch_idx}"] = True

            cols = st.columns(2)
            for ch_idx, ch in enumerate(file_chapters):
                ch_key = f"ch_select_{file_idx}_{ch_idx}"
                label = f"{ch['raw_title'] or ch['title']}　({len(ch['content'])} 字)"
                with cols[ch_idx % 2]:
                    st.checkbox(label, key=ch_key)

    # 渲染完成后，从 session_state 统一读取所有选中的章节
    for key, val in st.session_state.items():
        if key.startswith("ch_select_") and val is True:
            parts = key.replace("ch_select_", "").split("_", 1)
            if len(parts) == 2:
                file_idx, ch_idx = parts[0], parts[1]
                selected_keys.add(f"{file_idx}:{ch_idx}")

    wf["selected_chapter_keys"] = selected_keys

    selected_count = len(selected_keys)
    if selected_count > 0:
        st.success(f"✅ 已选择 {selected_count} / {total_chapter_count} 个章节")
    else:
        st.warning("⚠️ 请至少勾选一个章节")

    st.markdown("---")
    st.header("📝 剧本信息")

    meta = wf["meta"]
    col1, col2 = st.columns(2)
    with col1:
        meta["title"] = st.text_input("剧本标题 *", value=meta.get("title", ""), key="meta_title")
    with col2:
        meta["author"] = st.text_input("作者", value=meta.get("author", ""), key="meta_author")

    current_genre = meta.get("genre", "")
    if current_genre in GENRE_OPTIONS:
        genre_idx = GENRE_OPTIONS.index(current_genre)
    else:
        genre_idx = 0

    genre = st.selectbox("类型", GENRE_OPTIONS, index=genre_idx, key="meta_genre_select")
    if genre == "其他":
        meta["genre"] = st.text_input(
            "自定义类型",
            value=current_genre if current_genre not in GENRE_OPTIONS else "",
            key="meta_genre_custom",
        )
    else:
        meta["genre"] = genre

    st.markdown("---")

    has_selected = selected_count > 0
    has_title = bool(meta.get("title", "").strip())

    col_btn, col_status = st.columns([1, 3])
    with col_btn:
        start_disabled = not (has_selected and has_title)
        if st.button("🚀 开始转换", disabled=start_disabled, type="primary", use_container_width=True):
            wf["stage"] = "extracting"
            st.rerun()
    with col_status:
        if not has_selected:
            st.warning("请至少选择一个章节")
        elif not has_title:
            st.warning("请填写剧本标题")
        else:
            st.success("准备就绪，点击按钮开始转换")


def render_page_extracting():
    st.title("🎬 AI 小说转剧本工具")
    st.markdown("---")
    st.header("🔍 正在提取角色信息...")

    wf = st.session_state.workflow
    chapters_data = wf["chapters"]
    selected_keys = wf["selected_chapter_keys"]

    selected_chapters_content = []
    for key in sorted(selected_keys):
        parts = key.split(":")
        file_idx = int(parts[0])
        ch_idx = int(parts[1])
        ch = chapters_data[file_idx]["chapters"][ch_idx]
        selected_chapters_content.append(ch["content"])

    progress_bar = st.progress(0, text="正在初始化...")
    status_text = st.empty()

    try:
        bailian = BailianClient()
        extractor = CharacterExtractor(bailian)

        progress_bar.progress(30, text="正在调用 AI 提取角色...")
        status_text.info("AI 正在分析小说中的角色信息，请稍候...")

        profiles = extractor.extract_characters(selected_chapters_content)

        progress_bar.progress(80, text="正在保存角色特征...")

        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        profiles_path = os.path.join(config.OUTPUT_DIR, config.CHARACTER_PROFILES_FILE)
        extractor.save_profiles(profiles, profiles_path)

        wf["character_profiles"] = profiles
        wf["profiles_path"] = profiles_path

        char_count = len(profiles.get("characters", []))
        progress_bar.progress(100, text=f"完成！已识别 {char_count} 个角色")
        status_text.success(f"✅ 角色提取完成，共识别 {char_count} 个角色")

        st.markdown("### 已识别角色")
        for char in profiles.get("characters", []):
            role_label = {"protagonist": "主角", "antagonist": "反派", "supporting": "配角", "extra": "龙套"}.get(
                char.get("role", ""), char.get("role", "")
            )
            st.markdown(f"- **{char.get('name', '')}**（{role_label}）— {char.get('arc', '')}")

        st.markdown("---")
        if st.button("▶️ 进入剧本生成", type="primary", use_container_width=True):
            wf["stage"] = "generating"
            st.rerun()

    except Exception as e:
        logger.error("角色提取异常: %s", e, exc_info=True)
        progress_bar.progress(100, text="提取失败")
        status_text.error(f"❌ 角色提取失败: {e}")
        st.warning("请检查 API Key 配置或网络连接后重试")

        col_retry, col_skip = st.columns(2)
        with col_retry:
            if st.button("🔄 重试", use_container_width=True):
                st.rerun()
        with col_skip:
            if st.button("⏭️ 跳过（使用空角色表）", use_container_width=True):
                wf["character_profiles"] = {"characters": []}
                wf["profiles_path"] = ""
                wf["stage"] = "generating"
                st.rerun()


def build_chapter_queue(chapters_data, selected_keys):
    queue = []
    sorted_keys = sorted(selected_keys, key=lambda k: tuple(map(int, k.split(":"))))
    for key in sorted_keys:
        parts = key.split(":")
        file_idx = int(parts[0])
        ch_idx = int(parts[1])
        if file_idx < len(chapters_data) and ch_idx < len(chapters_data[file_idx]["chapters"]):
            ch = chapters_data[file_idx]["chapters"][ch_idx]
            queue.append((file_idx, ch_idx, ch))
    return queue


def generate_current_chapter(wf, chapter_queue, current_idx):
    if current_idx >= len(chapter_queue):
        logger.error("章节索引越界: current_idx=%d, queue_len=%d", current_idx, len(chapter_queue))
        st.error("章节索引错误，请返回重新选择")
        return

    file_idx, ch_idx, ch = chapter_queue[current_idx]
    total = len(chapter_queue)

    previous_summary = ""
    if current_idx > 0:
        previous_summary = wf.get("previous_summary", "")

    status_placeholder = st.empty()
    status_placeholder.info(f"正在生成第 {current_idx + 1}/{total} 章：{ch['title']}...")

    try:
        bailian = BailianClient()
        generator = ScriptGenerator(bailian)

        yaml_output, errors = generator.generate_chapter_script_with_errors(
            chapter_content=ch["content"],
            chapter_index=current_idx + 1,
            chapter_title=ch["title"],
            characters=wf["character_profiles"],
            previous_summary=previous_summary,
        )

        wf["current_yaml"] = yaml_output
        wf["current_errors"] = errors

        summary = generator.extract_summary(yaml_output)
        wf["previous_summary"] = summary

        wf["edit_history"] = [yaml_output]

        status_placeholder.success(f"第 {current_idx + 1}/{total} 章生成完成")

    except Exception as e:
        logger.error("章节生成失败: %s", e, exc_info=True)
        status_placeholder.error(f"生成失败: {e}")
        wf["current_yaml"] = ""
        wf["current_errors"] = [str(e)]
        wf["edit_history"] = []


def render_left_panel(wf, chapter_queue, current_idx, total_chapters):
    chapters_data = wf["chapters"]
    file_idx, ch_idx, ch = chapter_queue[current_idx]

    st.subheader(f"第 {current_idx + 1}/{total_chapters} 章：{ch['title']}")
    st.caption(
        f"文件: {chapters_data[file_idx]['file_name']}　|　"
        f"原文字数: {len(ch['content'])}"
    )

    errors = wf.get("current_errors", [])
    if errors:
        with st.expander(f"⚠️ 校验提示（{len(errors)} 条）", expanded=False):
            for e in errors:
                st.markdown(f"- {e}")

    edited_yaml = st.text_area(
        "剧本内容（可直接编辑）",
        value=wf.get("current_yaml", ""),
        height=600,
        key="yaml_editor",
        label_visibility="collapsed",
    )

    if edited_yaml != wf.get("current_yaml", ""):
        wf["current_yaml"] = edited_yaml


def render_right_panel(wf):
    st.subheader("💬 AI 编辑助手")
    st.caption("输入自然语言指令，AI 将自动修改剧本")

    chat_container = st.container(height=400)
    with chat_container:
        chat_history = wf.get("ai_chat_history", [])
        if not chat_history:
            st.info("AI 编辑助手已就绪，您可以输入修改指令")
        for msg in chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    if user_input := st.chat_input("输入修改指令，例如：把主角的台词改得更悲伤"):
        if "ai_chat_history" not in wf:
            wf["ai_chat_history"] = []
        if "editor_messages" not in wf:
            wf["editor_messages"] = []

        wf["ai_chat_history"].append({"role": "user", "content": user_input})

        try:
            bailian = BailianClient()
            editor = ScriptEditor(bailian)

            modified_yaml, diff_text, new_messages = editor.apply_edit(
                user_instruction=user_input,
                current_yaml=wf["current_yaml"],
                character_profiles=wf["character_profiles"],
                conversation_history=wf["editor_messages"],
            )

            wf["edit_history"].append(wf["current_yaml"])
            wf["current_yaml"] = modified_yaml
            wf["editor_messages"] = new_messages

            if diff_text and diff_text != "（无变化）":
                diff_msg = f"已修改剧本。变化如下：\n```diff\n{diff_text}\n```"
            else:
                diff_msg = "已修改剧本（无显著变化）。"

            wf["ai_chat_history"].append({"role": "assistant", "content": diff_msg})

        except Exception as e:
            logger.error("AI 编辑异常: %s", e)
            wf["ai_chat_history"].append({
                "role": "assistant",
                "content": f"❌ 修改失败: {e}",
            })

        st.rerun()


def render_bottom_bar(wf, chapter_queue, current_idx, total_chapters):
    st.markdown("---")

    col_undo, col_confirm, col_export = st.columns([1, 1, 1])

    with col_undo:
        hist = wf.get("edit_history", [])
        can_undo = len(hist) > 1
        if st.button("↩️ 撤销修改", disabled=not can_undo, use_container_width=True):
            hist.pop()
            wf["current_yaml"] = hist[-1]
            wf["edit_history"] = hist
            st.rerun()

    with col_confirm:
        if st.button("✅ 确认本章", type="primary", use_container_width=True):
            wf["confirmed_yaml_pieces"].append(wf["current_yaml"])
            wf["current_yaml"] = ""
            wf["current_errors"] = []
            wf["edit_history"] = []
            wf["ai_chat_history"] = []
            wf["editor_messages"] = []
            wf["current_chapter_idx"] = current_idx + 1
            st.rerun()

    with col_export:
        if st.button("📥 导出完整剧本", use_container_width=True):
            export_screenplay(wf, chapter_queue)


def export_screenplay(wf, chapter_queue):
    yaml_mgr = YAMLManager()

    all_pieces = list(wf["confirmed_yaml_pieces"])
    if wf.get("current_yaml"):
        all_pieces.append(wf["current_yaml"])

    if not all_pieces:
        st.warning("没有可导出的内容")
        return

    try:
        screenplay = yaml_mgr.merge_acts(
            yaml_pieces=all_pieces,
            meta=wf["meta"],
            characters=wf["character_profiles"].get("characters", []),
        )
    except Exception as e:
        logger.error("剧本合并失败: %s", e)
        st.error(f"剧本合并失败: {e}")
        return

    try:
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(config.OUTPUT_DIR, config.SCREENPLAY_FILE)
        yaml_mgr.save(screenplay, output_path)
    except (IOError, ValueError, PermissionError, OSError) as e:
        logger.error("剧本保存失败: %s", e)
        st.error(f"剧本保存失败: {e}")
        return

    try:
        with open(output_path, "r", encoding="utf-8") as f:
            yaml_content = f.read()
    except (FileNotFoundError, PermissionError, OSError) as e:
        logger.error("读取导出的剧本文件失败: %s", e)
        st.error(f"读取导出的剧本文件失败: {e}")
        return

    st.download_button(
        label="💾 下载剧本 YAML 文件",
        data=yaml_content,
        file_name=config.SCREENPLAY_FILE,
        mime="text/yaml",
        use_container_width=True,
    )
    st.success(f"剧本已导出到: {output_path}")


def render_completion_page(wf, chapter_queue):
    st.title("🎉 剧本生成完成！")
    st.success(f"全部 {len(chapter_queue)} 章已确认完毕")

    st.markdown("### 已确认章节")
    for i, (_, _, ch) in enumerate(chapter_queue):
        st.markdown(f"- 第 {i + 1} 章：{ch['title']}")

    export_screenplay(wf, chapter_queue)

    st.markdown("---")
    if st.button("🔄 返回重新开始", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


def render_page_generating():
    wf = st.session_state.workflow
    chapters_data = wf["chapters"]
    selected_keys = wf["selected_chapter_keys"]

    chapter_queue = build_chapter_queue(chapters_data, selected_keys)

    if not chapter_queue:
        st.error("没有选择任何章节，请返回重新选择")
        if st.button("⬅️ 返回"):
            wf["stage"] = "upload"
            st.rerun()
        return

    total_chapters = len(chapter_queue)
    confirmed_count = len(wf["confirmed_yaml_pieces"])

    if confirmed_count >= total_chapters:
        render_completion_page(wf, chapter_queue)
        return

    current_idx = wf["current_chapter_idx"]

    if current_idx >= total_chapters:
        wf["current_chapter_idx"] = confirmed_count
        current_idx = confirmed_count

    if not wf.get("current_yaml") and current_idx < total_chapters:
        generate_current_chapter(wf, chapter_queue, current_idx)

    st.title("🎬 剧本生成与编辑")

    progress = confirmed_count / total_chapters
    st.progress(progress, text=f"进度：{confirmed_count}/{total_chapters} 章已确认")

    left_col, right_col = st.columns([7, 3])

    with left_col:
        render_left_panel(wf, chapter_queue, current_idx, total_chapters)

    with right_col:
        render_right_panel(wf)

    render_bottom_bar(wf, chapter_queue, current_idx, total_chapters)


def main():
    init_session_state()

    stage = st.session_state.workflow["stage"]

    if stage == "upload":
        render_page_upload()
    elif stage == "extracting":
        render_page_extracting()
    elif stage == "generating":
        render_page_generating()
    else:
        st.title("🎬 完成")
        st.success("剧本已生成完毕！")


if __name__ == "__main__":
    main()