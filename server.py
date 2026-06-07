import uuid
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from chapter_parser import ChapterParser
from character_extractor import CharacterExtractor
from script_generator import ScriptGenerator
from script_editor import ScriptEditor
from bailian_client import BailianClient
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI 小说转剧本工具 v2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@dataclass
class SessionData:
    chapters_data: list = field(default_factory=list)
    selected_keys: set = field(default_factory=set)
    meta: dict = field(default_factory=dict)
    character_profiles: dict = field(default_factory=dict)
    confirmed_yaml_pieces: list = field(default_factory=list)
    current_chapter_idx: int = 0
    previous_summary: str = ""
    conversation_history: list = field(default_factory=list)
    current_yaml: str = ""


sessions: dict[str, SessionData] = {}

chapter_parser = ChapterParser()
bailian_client = BailianClient()
character_extractor = CharacterExtractor(bailian_client)
script_generator = ScriptGenerator(bailian_client)
script_editor = ScriptEditor(bailian_client)


def get_session(session_id: str) -> SessionData:
    if session_id not in sessions:
        sessions[session_id] = SessionData()
    return sessions[session_id]


class DirPathRequest(BaseModel):
    dir_path: str


class ParseFilesResponse(BaseModel):
    session_id: str
    chapters_data: list


class ExtractCharactersRequest(BaseModel):
    selected_chapters: list[dict]
    chapters_data: list
    session_id: str = ""


class UpdateProfilesRequest(BaseModel):
    session_id: str
    profiles: dict


class ConfirmProfilesRequest(BaseModel):
    session_id: str
    profiles: dict


class GenerateScriptRequest(BaseModel):
    session_id: str
    selected_chapters: list[dict]
    chapters_data: list
    meta: dict = {}


class EditScriptRequest(BaseModel):
    session_id: str
    instruction: str
    current_yaml: str = ""


@app.get("/api/session")
async def create_session():
    session_id = str(uuid.uuid4())
    sessions[session_id] = SessionData()
    return {"session_id": session_id}


@app.post("/api/parse/files")
async def parse_files(
    files: list[UploadFile] = File(...),
    session_id: str = None,
):
    if session_id:
        session = get_session(session_id)
    else:
        session_id = str(uuid.uuid4())
        session = SessionData()
        sessions[session_id] = session

    chapters_data = []
    errors = []

    for uploaded_file in files:
        filename = uploaded_file.filename or "unknown"
        if not filename.lower().endswith(".txt"):
            errors.append(f"{filename}: 不是 .txt 文件，已跳过")
            continue

        try:
            raw_bytes = await uploaded_file.read()
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"{filename}: 编码不是 UTF-8，已跳过")
            continue
        except Exception as e:
            errors.append(f"{filename}: 读取失败，已跳过 — {e}")
            continue

        logger.info("解析上传文件: %s (%d 字符)", filename, len(text))
        chapters = chapter_parser.parse(text)

        for ch in chapters:
            ch["char_count"] = len(ch.get("content", ""))

        chapters_data.append({
            "file_name": filename,
            "chapters": chapters,
        })

    session.chapters_data = chapters_data
    logger.info("上传文件解析完成: 共 %d 个文件, %d 个错误", len(chapters_data), len(errors))
    return {
        "session_id": session_id,
        "chapters_data": chapters_data,
        "errors": errors,
    }


@app.post("/api/parse/directory")
async def parse_directory(req: DirPathRequest):
    session_id = str(uuid.uuid4())
    session = SessionData()
    sessions[session_id] = session

    dir_path = req.dir_path.strip()
    if not os.path.isdir(dir_path):
        raise HTTPException(status_code=400, detail=f"目录不存在: {dir_path}")

    chapters_data = chapter_parser.parse_directory(dir_path)

    for file_data in chapters_data:
        for ch in file_data.get("chapters", []):
            if "char_count" not in ch:
                ch["char_count"] = len(ch.get("content", ""))

    session.chapters_data = chapters_data
    logger.info("目录扫描完成: %s, 共 %d 个文件", dir_path, len(chapters_data))
    return {
        "session_id": session_id,
        "chapters_data": chapters_data,
    }


@app.post("/api/extract/characters")
async def extract_characters(req: ExtractCharactersRequest):
    chapters_content = []
    for sel in req.selected_chapters:
        file_idx = sel.get("file_idx", 0)
        ch_idx = sel.get("ch_idx", 0)
        try:
            content = req.chapters_data[file_idx]["chapters"][ch_idx]["content"]
            chapters_content.append(content)
        except (IndexError, KeyError) as e:
            logger.warning("提取章节内容失败: file_idx=%d, ch_idx=%d — %s", file_idx, ch_idx, e)
            continue

    if not chapters_content:
        raise HTTPException(status_code=400, detail="未找到有效的章节内容")

    session = get_session(req.session_id) if req.session_id else None

    async def event_stream():
        try:
            for event in character_extractor.extract_characters_stream(chapters_content):
                event_type = event.get("type", "message")
                if event_type == "complete":
                    if session is not None:
                        session.character_profiles = event.get("profiles", {})
                    yield f"event: {event_type}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                    yield f"event: progress\ndata: {json.dumps({'type': 'progress', 'percent': 100, 'message': '100% 角色提取完成'}, ensure_ascii=False)}\n\n"
                else:
                    yield f"event: {event_type}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error("角色提取失败: %s", e)
            yield f"event: error\ndata: {json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/editor/edit")
async def edit_script(req: EditScriptRequest):
    session = get_session(req.session_id)
    characters = session.character_profiles
    current_yaml = req.current_yaml or session.current_yaml

    if not current_yaml:
        raise HTTPException(status_code=400, detail="没有可编辑的剧本内容")

    try:
        modified_yaml, diff_text, updated_history = script_editor.apply_edit(
            user_instruction=req.instruction,
            current_yaml=current_yaml,
            character_profiles=characters,
            conversation_history=session.conversation_history if session.conversation_history else None,
        )

        session.conversation_history = updated_history
        session.current_yaml = modified_yaml

        logger.info("AI 编辑完成: %s", req.instruction[:50])
        return {
            "modified_yaml": modified_yaml,
            "diff_text": diff_text,
        }
    except Exception as e:
        logger.error("AI 编辑失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/editor/reset")
async def reset_editor(req: EditScriptRequest):
    session = get_session(req.session_id)
    session.conversation_history = []
    session.current_yaml = req.current_yaml or session.current_yaml
    return {"status": "ok"}


@app.get("/api/export/yaml")
async def export_yaml(session_id: str = Query(...)):
    session = get_session(session_id)
    yaml_content = session.current_yaml

    if not yaml_content:
        file_path = os.path.join(config.OUTPUT_DIR, config.SCREENPLAY_FILE)
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                yaml_content = f.read()

    if not yaml_content:
        raise HTTPException(status_code=404, detail="没有可导出的剧本内容")

    title = session.meta.get("title", "screenplay") if session.meta else "screenplay"
    safe_title = "".join(c for c in title if c.isalnum() or c in "._- ").strip() or "screenplay"
    filename = f"{safe_title}.yaml"

    return StreamingResponse(
        iter([yaml_content]),
        media_type="application/x-yaml",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@app.get("/api/export/txt")
async def export_txt(session_id: str = Query(...)):
    session = get_session(session_id)
    yaml_content = session.current_yaml

    if not yaml_content:
        file_path = os.path.join(config.OUTPUT_DIR, config.SCREENPLAY_FILE)
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                yaml_content = f.read()

    if not yaml_content:
        raise HTTPException(status_code=404, detail="没有可导出的剧本内容")

    import re
    txt_lines = []
    for line in yaml_content.splitlines():
        stripped = re.sub(r'^[\s-]+', '', line)
        if stripped.startswith('#') or not stripped:
            continue
        if stripped.startswith(('meta:', 'characters:', 'acts:', 'scenes:', 'beats:', 'type:', 'aliases:', 'id:', 'name:', 'role:', 'arc:', 'act_id:', 'title:', 'scene_id:', 'location:', 'int_ext:', 'time_of_day:', 'characters_present:', 'transition:', 'char_ref:', 'emotion:')):
            txt_lines.append(stripped)
        elif stripped.startswith('line:'):
            dialogue = stripped[5:].strip().strip('"').strip("'")
            if dialogue:
                txt_lines.append('  ' + dialogue)
        elif stripped.startswith('content:'):
            content = stripped[8:].strip()
            if content:
                txt_lines.append('  [' + content + ']')

    txt_content = '\n'.join(txt_lines)

    title = session.meta.get("title", "screenplay") if session.meta else "screenplay"
    safe_title = "".join(c for c in title if c.isalnum() or c in "._- ").strip() or "screenplay"
    filename = f"{safe_title}.txt"

    return StreamingResponse(
        iter([txt_content]),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@app.get("/api/characters/profiles")
async def get_character_profiles(session_id: str = Query(...)):
    session = get_session(session_id)
    return {"profiles": session.character_profiles}


@app.put("/api/characters/profiles")
async def update_character_profiles(req: UpdateProfilesRequest):
    session = get_session(req.session_id)
    session.character_profiles = req.profiles
    logger.info("角色数据已更新: %d 个角色", len(req.profiles.get("characters", [])))
    return {"status": "ok"}


@app.post("/api/characters/confirm")
async def confirm_character_profiles(req: ConfirmProfilesRequest):
    session = get_session(req.session_id)
    session.character_profiles = req.profiles
    output_path = os.path.join(config.OUTPUT_DIR, config.CHARACTER_PROFILES_FILE)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    character_extractor.save_profiles(req.profiles, output_path)
    logger.info("角色数据已确认并保存: %s (%d 个角色)", output_path, len(req.profiles.get("characters", [])))
    return {"status": "ok", "path": output_path}


@app.post("/api/generate/script")
async def generate_script(req: GenerateScriptRequest):
    session = get_session(req.session_id)
    characters = session.character_profiles
    if not characters or not characters.get("characters"):
        raise HTTPException(status_code=400, detail="未找到角色数据，请先完成角色提取")

    chapters_content = []
    for sel in req.selected_chapters:
        file_idx = sel.get("file_idx", 0)
        ch_idx = sel.get("ch_idx", 0)
        try:
            chapter = req.chapters_data[file_idx]["chapters"][ch_idx]
            chapters_content.append({
                "content": chapter["content"],
                "title": chapter.get("title") or chapter.get("raw_title") or f"第{ch_idx + 1}章",
                "index": ch_idx + 1,
            })
        except (IndexError, KeyError) as e:
            logger.warning("提取章节失败: file_idx=%d, ch_idx=%d — %s", file_idx, ch_idx, e)
            continue

    if not chapters_content:
        raise HTTPException(status_code=400, detail="未找到有效的章节内容")

    total = len(chapters_content)
    yaml_pieces = []
    previous_summary = session.previous_summary

    async def event_stream():
        nonlocal previous_summary, yaml_pieces

        try:
            for i, ch in enumerate(chapters_content):
                progress_msg = f"正在生成第 {i + 1}/{total} 章: {ch['title']}"
                yield f"event: progress\ndata: {json.dumps({'type': 'progress', 'percent': int(i / total * 100), 'message': progress_msg}, ensure_ascii=False)}\n\n"

                yield f"event: chapter_start\ndata: {json.dumps({'type': 'chapter_start', 'chapter_index': i + 1, 'chapter_title': ch['title'], 'total': total}, ensure_ascii=False)}\n\n"

                full_yaml = ""
                try:
                    for chunk in script_generator.generate_chapter_script_stream(
                        chapter_content=ch["content"],
                        chapter_index=ch["index"],
                        chapter_title=ch["title"],
                        characters=characters,
                        previous_summary=previous_summary,
                    ):
                        full_yaml += chunk
                        yield f"event: token\ndata: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"

                    errors = script_generator.yaml_manager.validate_yaml_text(full_yaml)
                    summary = script_generator.extract_summary(full_yaml)
                    previous_summary = summary
                    yaml_pieces.append(full_yaml)

                    yield f"event: chapter_complete\ndata: {json.dumps({'type': 'chapter_complete', 'chapter_index': i + 1, 'chapter_title': ch['title'], 'yaml': full_yaml, 'errors': errors}, ensure_ascii=False)}\n\n"

                except Exception as e:
                    logger.error("第 %d 章生成失败: %s", i + 1, e)
                    yield f"event: error\ndata: {json.dumps({'message': f'第{i + 1}章生成失败: {e}'}, ensure_ascii=False)}\n\n"
                    return

            yield f"event: progress\ndata: {json.dumps({'type': 'progress', 'percent': 90, 'message': '正在合并剧本...'}, ensure_ascii=False)}\n\n"

            meta = req.meta or {}
            meta["version"] = "1.0"
            meta["source"] = "AI 小说转剧本工具 v2.0"
            screenplay = script_generator.yaml_manager.merge_acts(
                yaml_pieces, meta, characters.get("characters", [])
            )

            output_path = os.path.join(config.OUTPUT_DIR, config.SCREENPLAY_FILE)
            os.makedirs(config.OUTPUT_DIR, exist_ok=True)
            script_generator.yaml_manager.save(screenplay, output_path)

            session.confirmed_yaml_pieces = yaml_pieces
            session.previous_summary = previous_summary
            session.meta = meta
            session.current_yaml = script_generator.yaml_manager.to_display_string(screenplay)

            yield f"event: progress\ndata: {json.dumps({'type': 'progress', 'percent': 100, 'message': '100% 剧本生成完成'}, ensure_ascii=False)}\n\n"
            yield f"event: complete\ndata: {json.dumps({'type': 'complete', 'screenplay': screenplay, 'path': output_path}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error("剧本生成失败: %s", e)
            yield f"event: error\ndata: {json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    return FileResponse(os.path.join(static_dir, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)