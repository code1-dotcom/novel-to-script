let sessionId = null;
let currentStep = 1;
let chaptersData = [];
let characterProfiles = null;
let editingCharIndex = -1;
let selectedChapters = [];
let metaInfo = {};
let fullScriptYaml = '';
let scriptYamlText = '';
let screenplayData = null;

const FIELD_LABELS = {
    "meta": "元信息/meta",
    "title": "标题/title",
    "author": "原著作者/author",
    "adapter": "改编编剧/adapter",
    "version": "版本号/version",
    "genre": "类型/genre",
    "source": "原作来源/source",
    "logline": "一句话梗概/logline",
    "characters": "角色表/characters",
    "id": "角色ID/id",
    "name": "姓名/name",
    "aliases": "别名/aliases",
    "role": "角色类型/role",
    "arc": "人物弧线/arc",
    "acts": "幕/acts",
    "act_id": "幕编号/act_id",
    "summary": "摘要/summary",
    "scenes": "场景/scenes",
    "scene_id": "场景序号/scene_id",
    "act_ref": "所属幕/act_ref",
    "location": "地点/location",
    "int_ext": "内外景/int_ext",
    "time_of_day": "时间/time_of_day",
    "characters_present": "出场角色/characters_present",
    "beats": "节拍/beats",
    "type": "类型/type",
    "char_ref": "角色引用/char_ref",
    "line": "台词/line",
    "parenthetical": "动作提示/parenthetical",
    "emotion": "情绪/emotion",
    "content": "内容/content",
    "transition": "转场/transition",
    "notes": "备注/notes",
    "tag": "标签/tag",
    "comment": "说明/comment",
};

async function initSession() {
    const resp = await fetch('/api/session');
    const data = await resp.json();
    sessionId = data.session_id;
    console.log('Session created:', sessionId);
}

function showStep(step) {
    document.querySelectorAll('.step').forEach(el => el.style.display = 'none');
    const stepEl = document.getElementById(`step-${step}`);
    if (stepEl) {
        stepEl.style.display = 'block';
    }
    currentStep = step;
}

function setStatus(elId, message, type) {
    const el = document.getElementById(elId);
    if (!el) return;
    el.textContent = message;
    el.className = 'status-text';
    if (type) {
        el.classList.add(type);
    }
}

function updateStartButton() {
    const btn = document.getElementById('btn-start');
    if (!btn) return;
    const checked = document.querySelectorAll('input[name="chapter"]:checked');
    btn.disabled = checked.length === 0;
}

function renderChapters(data) {
    chaptersData = data;
    const container = document.getElementById('chapters-container');
    container.innerHTML = '';

    let totalChapters = 0;

    data.forEach((fileData, fileIdx) => {
        const chapters = fileData.chapters || [];
        totalChapters += chapters.length;

        const group = document.createElement('div');
        group.className = 'file-group';

        const header = document.createElement('div');
        header.className = 'file-group-header';

        const titleEl = document.createElement('h4');
        titleEl.textContent = '📄 ' + fileData.file_name;

        const countEl = document.createElement('span');
        countEl.className = 'chapter-count';
        countEl.textContent = chapters.length + ' 章';

        const selectAllLabel = document.createElement('label');
        selectAllLabel.className = 'select-all-label';
        const selectAllCb = document.createElement('input');
        selectAllCb.type = 'checkbox';
        selectAllCb.className = 'select-all';
        selectAllCb.dataset.file = fileIdx;
        selectAllCb.addEventListener('change', function () {
            const checked = this.checked;
            document.querySelectorAll(`input[name="chapter"][data-file="${fileIdx}"]`)
                .forEach(cb => { cb.checked = checked; });
            updateStartButton();
        });
        selectAllLabel.appendChild(selectAllCb);
        selectAllLabel.appendChild(document.createTextNode(' 全选'));

        header.appendChild(titleEl);
        header.appendChild(countEl);
        header.appendChild(selectAllLabel);
        group.appendChild(header);

        const body = document.createElement('div');
        body.className = 'file-group-body';

        chapters.forEach((ch, chIdx) => {
            const item = document.createElement('div');
            item.className = 'chapter-item';

            const label = document.createElement('label');
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.name = 'chapter';
            cb.value = `${fileIdx}:${chIdx}`;
            cb.dataset.file = fileIdx;
            cb.addEventListener('change', updateStartButton);

            const titleSpan = document.createElement('span');
            titleSpan.className = 'chapter-title';
            const displayTitle = ch.title || (ch.raw_title || '第' + (ch.index + 1) + '章');
            titleSpan.textContent = displayTitle;

            const charCount = document.createElement('span');
            charCount.className = 'chapter-char-count';
            charCount.textContent = '(' + (ch.char_count || 0) + '字)';

            label.appendChild(cb);
            label.appendChild(titleSpan);
            label.appendChild(charCount);
            item.appendChild(label);
            body.appendChild(item);
        });

        group.appendChild(body);
        container.appendChild(group);
    });

    document.getElementById('chapters-area').style.display = 'block';
    document.getElementById('meta-area').style.display = 'block';
    updateStartButton();
}

async function scanDirectory() {
    const dirPath = document.getElementById('dir-path').value.trim();
    if (!dirPath) {
        setStatus('dir-status', '请输入文件夹路径', 'error');
        return;
    }

    const btn = document.getElementById('btn-scan-dir');
    btn.disabled = true;
    btn.textContent = '扫描中...';
    setStatus('dir-status', '正在扫描目录...', '');

    try {
        const resp = await fetch('/api/parse/directory', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dir_path: dirPath }),
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || '扫描失败');
        }

        const data = await resp.json();
        sessionId = data.session_id;
        renderChapters(data.chapters_data);
        setStatus('dir-status', '扫描完成，共 ' + data.chapters_data.length + ' 个文件', 'success');
    } catch (e) {
        setStatus('dir-status', '扫描失败: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '扫描';
    }
}

async function uploadFiles(fileList) {
    const formData = new FormData();
    if (sessionId) {
        formData.append('session_id', sessionId);
    }

    let txtCount = 0;
    for (const file of fileList) {
        if (file.name.toLowerCase().endsWith('.txt')) {
            formData.append('files', file);
            txtCount++;
        }
    }

    if (txtCount === 0) {
        setStatus('upload-status', '请选择 .txt 文件', 'error');
        return;
    }

    setStatus('upload-status', '正在解析 ' + txtCount + ' 个文件...', '');

    try {
        const resp = await fetch('/api/parse/files', {
            method: 'POST',
            body: formData,
        });

        if (!resp.ok) {
            throw new Error('解析失败');
        }

        const data = await resp.json();
        sessionId = data.session_id;
        renderChapters(data.chapters_data);

        let msg = '解析完成，共 ' + data.chapters_data.length + ' 个文件';
        if (data.errors && data.errors.length > 0) {
            msg += ' (' + data.errors.length + ' 个错误)';
        }
        setStatus('upload-status', msg, 'success');
    } catch (e) {
        setStatus('upload-status', '上传失败: ' + e.message, 'error');
    }
}

function getSelectedChapters() {
    const selected = [];
    const checkboxes = document.querySelectorAll('input[name="chapter"]:checked');
    checkboxes.forEach(cb => {
        const [fileIdx, chIdx] = cb.value.split(':').map(Number);
        selected.push({ file_idx: fileIdx, ch_idx: chIdx });
    });
    return selected;
}

function getMeta() {
    return {
        title: document.getElementById('meta-title').value.trim(),
        author: document.getElementById('meta-author').value.trim(),
        genre: document.getElementById('meta-genre').value.trim(),
    };
}

async function startConversion() {
    const selected = getSelectedChapters();
    if (selected.length === 0) {
        alert('请至少选择一个章节');
        return;
    }

    selectedChapters = selected;
    metaInfo = getMeta();
    showStep(2);

    document.getElementById('character-progress-fill').style.width = '0%';
    document.getElementById('character-progress-text').textContent = '准备中...';
    document.getElementById('character-content').innerHTML = '';

    const resp = await fetch('/api/extract/characters', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            selected_chapters: selected,
            chapters_data: chaptersData,
            session_id: sessionId,
        }),
    });

    if (!resp.ok) {
        const err = await resp.json();
        document.getElementById('character-progress-text').textContent = '请求失败: ' + (err.detail || '未知错误');
        return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop();

        for (const part of parts) {
            if (!part.trim()) continue;

            const lines = part.split('\n');
            let eventType = '';
            let dataStr = '';

            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    eventType = line.slice(7).trim();
                } else if (line.startsWith('data: ')) {
                    dataStr = line.slice(6).trim();
                }
            }

            if (!dataStr) continue;

            try {
                const data = JSON.parse(dataStr);

                if (eventType === 'progress' || data.type === 'progress') {
                    const percent = data.percent || 0;
                    const message = data.message || '';
                    document.getElementById('character-progress-fill').style.width = percent + '%';
                    document.getElementById('character-progress-text').textContent = message;
                } else if (eventType === 'complete' || data.type === 'complete') {
                    document.getElementById('character-progress-fill').style.width = '100%';
                    document.getElementById('character-progress-text').textContent = '提取完成';
                    characterProfiles = data.profiles;
                    renderCharacterProfiles(data.profiles);
                } else if (eventType === 'error' || data.type === 'error') {
                    document.getElementById('character-progress-text').textContent = '错误: ' + (data.message || '未知错误');
                }
            } catch (e) {
                console.warn('SSE 解析失败:', e, dataStr);
            }
        }
    }
}

function renderCharacterProfiles(profiles) {
    const container = document.getElementById('character-content');
    const characters = profiles.characters || [];

    if (characters.length === 0) {
        container.innerHTML = '<p class="no-result">未提取到角色信息</p>';
        return;
    }

    const roleLabels = {
        protagonist: '主角',
        antagonist: '反派',
        supporting: '配角',
        extra: '龙套',
    };

    const roleColors = {
        protagonist: '#e8f5e9',
        antagonist: '#fce4ec',
        supporting: '#e3f2fd',
        extra: '#f5f5f5',
    };

    const roleBadgeColors = {
        protagonist: '#2e7d32',
        antagonist: '#c62828',
        supporting: '#1565c0',
        extra: '#757575',
    };

    let html = '<h3>已提取 ' + characters.length + ' 个角色</h3><div class="character-grid">';

    for (let i = 0; i < characters.length; i++) {
        const char = characters[i];
        const role = char.role || 'extra';
        const bgColor = roleColors[role] || '#f5f5f5';
        const badgeColor = roleBadgeColors[role] || '#757575';
        const roleLabel = roleLabels[role] || role;

        html += '<div class="character-card" style="background:' + bgColor + '">';
        html += '<div class="character-card-header">';
        html += '<span class="character-name">' + escapeHtml(char.name || '未知') + '</span>';
        html += '<div class="character-card-actions">';
        html += '<span class="character-role" style="background:' + badgeColor + '">' + roleLabel + '</span>';
        html += '<button class="btn-edit-char" onclick="openEditModal(' + i + ')">✏️ 编辑</button>';
        html += '</div>';
        html += '</div>';

        if (char.aliases && char.aliases.length > 0) {
            html += '<div class="character-aliases">别名: ' + escapeHtml(char.aliases.join('、')) + '</div>';
        }

        if (char.arc) {
            html += '<div class="character-arc">' + escapeHtml(char.arc) + '</div>';
        }

        if (char.traits) {
            html += '<div class="character-traits">';
            if (char.traits.personality) {
                html += '<div class="trait-item"><span class="trait-label">性格</span>' + escapeHtml(char.traits.personality) + '</div>';
            }
            if (char.traits.speaking_style) {
                html += '<div class="trait-item"><span class="trait-label">说话风格</span>' + escapeHtml(char.traits.speaking_style) + '</div>';
            }
            if (char.traits.background) {
                html += '<div class="trait-item"><span class="trait-label">背景</span>' + escapeHtml(char.traits.background) + '</div>';
            }
            if (char.traits.relationships && Object.keys(char.traits.relationships).length > 0) {
                const rels = Object.entries(char.traits.relationships)
                    .map(([k, v]) => escapeHtml(k) + ': ' + escapeHtml(v))
                    .join('、');
                html += '<div class="trait-item"><span class="trait-label">关系</span>' + rels + '</div>';
            }
            html += '</div>';
        }

        html += '</div>';
    }

    html += '</div>';
    html += '<div class="confirm-area"><button class="btn btn-primary" onclick="confirmCharacters()">✅ 确认角色，开始生成剧本</button></div>';
    container.innerHTML = html;
}

function openEditModal(index) {
    editingCharIndex = index;
    const characters = characterProfiles.characters || [];
    const char = characters[index];

    document.getElementById('edit-name').value = char.name || '';
    document.getElementById('edit-aliases').value = (char.aliases || []).join(', ');
    document.getElementById('edit-role').value = char.role || 'extra';
    document.getElementById('edit-arc').value = char.arc || '';
    document.getElementById('edit-personality').value = (char.traits && char.traits.personality) ? char.traits.personality : '';
    document.getElementById('edit-speaking').value = (char.traits && char.traits.speaking_style) ? char.traits.speaking_style : '';
    document.getElementById('edit-background').value = (char.traits && char.traits.background) ? char.traits.background : '';
    if (char.traits && char.traits.relationships) {
        const rels = Object.entries(char.traits.relationships)
            .map(([k, v]) => k + ': ' + v)
            .join(', ');
        document.getElementById('edit-relationships').value = rels;
    } else {
        document.getElementById('edit-relationships').value = '';
    }

    document.getElementById('character-edit-modal').style.display = 'flex';
}

function closeEditModal() {
    document.getElementById('character-edit-modal').style.display = 'none';
    editingCharIndex = -1;
}

async function saveCharacterEdit() {
    const name = document.getElementById('edit-name').value.trim();
    if (!name) {
        alert('角色名称不能为空');
        return;
    }

    const aliasesStr = document.getElementById('edit-aliases').value.trim();
    const aliases = aliasesStr ? aliasesStr.split(',').map(function (s) { return s.trim(); }).filter(Boolean) : [];

    const relationshipsStr = document.getElementById('edit-relationships').value.trim();
    const relationships = {};
    if (relationshipsStr) {
        relationshipsStr.split(',').forEach(function (item) {
            const parts = item.split(':');
            if (parts.length >= 2) {
                relationships[parts[0].trim()] = parts.slice(1).join(':').trim();
            }
        });
    }

    const updatedChar = {
        id: characterProfiles.characters[editingCharIndex].id || ('char_' + String(editingCharIndex + 1).padStart(3, '0')),
        name: name,
        aliases: aliases,
        role: document.getElementById('edit-role').value,
        arc: document.getElementById('edit-arc').value.trim(),
        traits: {
            personality: document.getElementById('edit-personality').value.trim(),
            speaking_style: document.getElementById('edit-speaking').value.trim(),
            background: document.getElementById('edit-background').value.trim(),
            relationships: relationships,
        },
    };

    characterProfiles.characters[editingCharIndex] = updatedChar;

    try {
        await fetch('/api/characters/profiles', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                profiles: characterProfiles,
            }),
        });
    } catch (e) {
        console.warn('保存角色到后端失败:', e);
    }

    closeEditModal();
    renderCharacterProfiles(characterProfiles);
}

async function confirmCharacters() {
    if (!characterProfiles || !characterProfiles.characters || characterProfiles.characters.length === 0) {
        alert('没有可确认的角色数据');
        return;
    }

    try {
        const resp = await fetch('/api/characters/confirm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                profiles: characterProfiles,
            }),
        });

        if (!resp.ok) {
            const err = await resp.json();
            alert('确认失败: ' + (err.detail || '未知错误'));
            return;
        }

        showStep(3);
        startScriptGeneration();
    } catch (e) {
        alert('确认失败: ' + e.message);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function startScriptGeneration() {
    document.getElementById('script-progress-fill').style.width = '0%';
    document.getElementById('script-progress-text').textContent = '准备中...';
    document.getElementById('chapter-status-list').innerHTML = '';
    document.getElementById('script-split-layout').style.display = 'none';
    fullScriptYaml = '';

    const resp = await fetch('/api/generate/script', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            session_id: sessionId,
            selected_chapters: selectedChapters,
            chapters_data: chaptersData,
            meta: metaInfo,
        }),
    });

    if (!resp.ok) {
        const err = await resp.json();
        document.getElementById('script-progress-text').textContent = '请求失败: ' + (err.detail || '未知错误');
        return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop();

        for (const part of parts) {
            if (!part.trim()) continue;

            const lines = part.split('\n');
            let eventType = '';
            let dataStr = '';

            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    eventType = line.slice(7).trim();
                } else if (line.startsWith('data: ')) {
                    dataStr = line.slice(6).trim();
                }
            }

            if (!dataStr) continue;

            try {
                const data = JSON.parse(dataStr);

                if (eventType === 'progress' || data.type === 'progress') {
                    const percent = data.percent || 0;
                    const message = data.message || '';
                    document.getElementById('script-progress-fill').style.width = percent + '%';
                    document.getElementById('script-progress-text').textContent = message;
                } else if (eventType === 'chapter_start' || data.type === 'chapter_start') {
                    updateChapterStatus(data.chapter_index, data.chapter_title, 'generating');
                } else if (eventType === 'chapter_complete' || data.type === 'chapter_complete') {
                    const errCount = (data.errors || []).length;
                    const status = errCount > 0 ? 'warning' : 'done';
                    updateChapterStatus(data.chapter_index, data.chapter_title, status, errCount);
                } else if (eventType === 'complete' || data.type === 'complete') {
                    document.getElementById('script-progress-fill').style.width = '100%';
                    document.getElementById('script-progress-text').textContent = '生成完成，已保存到 ' + (data.path || 'output/screenplay.yaml');
                    screenplayData = data.screenplay;
                    displayScriptYaml(data.screenplay);
                } else if (eventType === 'error' || data.type === 'error') {
                    document.getElementById('script-progress-text').textContent = '错误: ' + (data.message || '未知错误');
                }
            } catch (e) {
                console.warn('SSE 解析失败:', e, dataStr);
            }
        }
    }
}

function updateChapterStatus(index, title, status, errCount) {
    const container = document.getElementById('chapter-status-list');
    let item = document.getElementById('chapter-status-' + index);

    if (!item) {
        item = document.createElement('div');
        item.id = 'chapter-status-' + index;
        item.className = 'chapter-status-item';
        container.appendChild(item);
    }

    const statusIcons = {
        generating: '⏳',
        done: '✅',
        warning: '⚠️',
    };

    const icon = statusIcons[status] || '⏳';
    let text = '第' + index + '章: ' + escapeHtml(title) + ' ' + icon;

    if (status === 'warning' && errCount) {
        text += ' (' + errCount + ' 个校验警告)';
    }

    item.textContent = text;
    item.className = 'chapter-status-item status-' + status;
}

function translateYamlKeys(yamlText) {
    var lines = yamlText.split('\n');
    return lines.map(function (line) {
        var match = line.match(/^(\s*)(\w+):(.*)$/);
        if (match) {
            var indent = match[1];
            var key = match[2];
            var rest = match[3];
            if (FIELD_LABELS[key]) {
                return indent + FIELD_LABELS[key] + ':' + rest;
            }
        }
        return line;
    }).join('\n');
}

function displayScriptYaml(screenplay) {
    document.getElementById('script-split-layout').style.display = 'flex';
    document.getElementById('editor-diff-area').style.display = 'none';
    document.getElementById('editor-status').textContent = '';
    document.getElementById('editor-instruction').value = '';

    if (!screenplay) {
        document.getElementById('script-yaml-display').textContent = '（无数据）';
        scriptYamlText = '';
        return;
    }

    let yamlLines = [];
    if (screenplay.meta) {
        yamlLines.push('meta:');
        for (const [key, value] of Object.entries(screenplay.meta)) {
            yamlLines.push('  ' + key + ': ' + value);
        }
        yamlLines.push('');
    }

    if (screenplay.characters) {
        yamlLines.push('characters:');
        for (const char of screenplay.characters) {
            yamlLines.push('  - id: ' + (char.id || ''));
            yamlLines.push('    name: ' + (char.name || ''));
            yamlLines.push('    role: ' + (char.role || ''));
            if (char.arc) {
                yamlLines.push('    arc: ' + char.arc);
            }
            if (char.aliases && char.aliases.length > 0) {
                yamlLines.push('    aliases: [' + char.aliases.join(', ') + ']');
            }
        }
        yamlLines.push('');
    }

    if (screenplay.acts) {
        yamlLines.push('acts:');
        for (const act of screenplay.acts) {
            yamlLines.push('  - act_id: ' + (act.act_id || ''));
            if (act.title) {
                yamlLines.push('    title: ' + act.title);
            }
            if (act.scenes) {
                yamlLines.push('    scenes:');
                for (const scene of act.scenes) {
                    yamlLines.push('      - scene_id: ' + (scene.scene_id || ''));
                    yamlLines.push('        location: ' + (scene.location || ''));
                    yamlLines.push('        int_ext: ' + (scene.int_ext || ''));
                    yamlLines.push('        time_of_day: ' + (scene.time_of_day || ''));
                    if (scene.characters_present) {
                        yamlLines.push('        characters_present: [' + scene.characters_present.join(', ') + ']');
                    }
                    if (scene.beats) {
                        yamlLines.push('        beats:');
                        for (const beat of scene.beats) {
                            if (beat.type === 'dialogue') {
                                yamlLines.push('          - type: dialogue');
                                yamlLines.push('            char_ref: ' + (beat.char_ref || ''));
                                yamlLines.push('            line: "' + (beat.line || '') + '"');
                                if (beat.emotion) {
                                    yamlLines.push('            emotion: ' + beat.emotion);
                                }
                            } else {
                                yamlLines.push('          - type: ' + (beat.type || ''));
                                yamlLines.push('            content: ' + (beat.content || ''));
                            }
                        }
                    }
                    if (scene.transition) {
                        yamlLines.push('        transition: ' + scene.transition);
                    }
                }
            }
        }
    }

    fullScriptYaml = yamlLines.join('\n');
    scriptYamlText = fullScriptYaml;
    document.getElementById('script-yaml-display').textContent = translateYamlKeys(scriptYamlText);
}

function copyScriptYaml() {
    if (!fullScriptYaml) {
        alert('没有可复制的剧本内容');
        return;
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(fullScriptYaml).then(function () {
            var btn = document.getElementById('btn-copy-yaml');
            var original = btn.textContent;
            btn.textContent = '✅ 已复制';
            setTimeout(function () { btn.textContent = original; }, 2000);
        }).catch(function () {
            fallbackCopy(fullScriptYaml);
        });
    } else {
        fallbackCopy(fullScriptYaml);
    }
}

function fallbackCopy(text) {
    var textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    alert('已复制到剪贴板');
}

function downloadScriptYaml() {
    var link = document.createElement('a');
    link.href = '/api/export/yaml?session_id=' + encodeURIComponent(sessionId);
    link.download = '';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function downloadScriptTxt() {
    var link = document.createElement('a');
    link.href = '/api/export/txt?session_id=' + encodeURIComponent(sessionId);
    link.download = '';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

async function applyEdit() {
    const instruction = document.getElementById('editor-instruction').value.trim();
    if (!instruction) {
        alert('请输入修改指令');
        return;
    }

    const btn = document.getElementById('btn-apply-edit');
    const statusEl = document.getElementById('editor-status');
    btn.disabled = true;
    btn.textContent = '⏳ 处理中...';
    statusEl.textContent = '正在处理修改指令...';
    statusEl.className = 'status-text status-loading';

    try {
        const resp = await fetch('/api/editor/edit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                instruction: instruction,
                current_yaml: scriptYamlText,
            }),
        });

        if (!resp.ok) {
            const err = await resp.json();
            statusEl.textContent = '编辑失败: ' + (err.detail || '未知错误');
            statusEl.className = 'status-text status-error';
            return;
        }

        const data = await resp.json();

        scriptYamlText = data.modified_yaml;
        document.getElementById('script-yaml-display').textContent = translateYamlKeys(data.modified_yaml);
        fullScriptYaml = data.modified_yaml;

        if (data.diff_text) {
            document.getElementById('editor-diff-area').style.display = 'block';
            document.getElementById('editor-diff-display').textContent = data.diff_text;
        }

        document.getElementById('editor-instruction').value = '';
        statusEl.textContent = '✅ 编辑已应用';
        statusEl.className = 'status-text status-success';
    } catch (e) {
        statusEl.textContent = '编辑失败: ' + e.message;
        statusEl.className = 'status-text status-error';
    } finally {
        btn.disabled = false;
        btn.textContent = '✨ 应用编辑';
    }
}

async function resetEditor() {
    try {
        await fetch('/api/editor/reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                current_yaml: scriptYamlText,
            }),
        });
    } catch (e) {
        console.warn('重置编辑器失败:', e);
    }

    document.getElementById('editor-instruction').value = '';
    document.getElementById('editor-diff-area').style.display = 'none';
    document.getElementById('editor-status').textContent = '🔄 对话历史已重置';
    document.getElementById('editor-status').className = 'status-text';
}

document.addEventListener('DOMContentLoaded', function () {
    initSession();

    document.getElementById('btn-scan-dir').addEventListener('click', scanDirectory);

    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    dropZone.addEventListener('click', function () {
        fileInput.click();
    });

    dropZone.addEventListener('dragover', function (e) {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', function () {
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', function (e) {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        if (e.dataTransfer.files.length > 0) {
            uploadFiles(e.dataTransfer.files);
        }
    });

    fileInput.addEventListener('change', function () {
        if (fileInput.files.length > 0) {
            uploadFiles(fileInput.files);
        }
    });

    document.getElementById('btn-start').addEventListener('click', startConversion);

    document.getElementById('editor-instruction').addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && e.ctrlKey) {
            e.preventDefault();
            applyEdit();
        }
    });
});