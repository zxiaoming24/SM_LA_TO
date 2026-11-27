"""

笔记服务模块
提供学习笔记的 CRUD、AI 结构化整理、导出（Word/PDF）、附件管理等功能
"""

import os
import json
import hashlib
import time
import re
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from utils.llm_config import get_chat_openai


# ==================== 笔记存储目录 ====================

NOTE_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "note_data")

# ★★★ 路径遍历防护：只允许字母、数字、下划线、连字符 ★★★
_SAFE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_\-]+$')

def _sanitize_path_component(name: str) -> str:
    """验证路径组件是否安全，防止目录遍历攻击"""
    if not _SAFE_ID_PATTERN.match(name):
        raise ValueError(f"非法的路径组件: {name!r}")
    return name


def _user_dir(user_id: str) -> str:
    """获取用户笔记目录路径"""
    d = os.path.join(NOTE_BASE_DIR, _sanitize_path_component(user_id))
    os.makedirs(d, exist_ok=True)
    return d


def _note_path(user_id: str, note_id: str) -> str:
    """获取单篇笔记文件路径"""
    return os.path.join(_user_dir(user_id), f"{_sanitize_path_component(note_id)}.json")


def _attachment_dir(user_id: str) -> str:
    """获取用户笔记附件目录路径"""
    d = os.path.join(NOTE_BASE_DIR, _sanitize_path_component(user_id), "attachments")
    os.makedirs(d, exist_ok=True)
    return d


def get_attachment_static_dir() -> str:
    """获取附件静态文件目录（给 FastAPI static mount 用）"""
    return os.path.join(NOTE_BASE_DIR)


ALLOWED_ATTACHMENT_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp",
    ".doc", ".docx", ".pdf", ".txt", ".md",
    ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".rar", ".7z",
}


async def _auto_bind_knowledge_points(content: str) -> List[str]:
    """用 LLM 从笔记内容中自动提取知识点关键词（不依赖预定义列表）"""
    if not content or not content.strip():
        return []
    try:
        llm = get_chat_openai(temperature=0.1, max_tokens=256)
        prompt = f"""你是一位学习笔记分析助手。请从以下笔记内容中提取 1-4 个最核心的知识点关键词。

要求：
1. 提取能概括笔记核心主题的短关键词
2. 输出纯 JSON 数组格式，如 ["知识点1", "知识点2"]
3. 如果内容太少或无法提取，输出空数组 []
4. 不要输出任何其他文字

笔记内容：
{content[:2000]}

JSON 数组："""
        response = await llm.ainvoke(prompt)
        raw = response.content if hasattr(response, "content") else str(response)
        raw = raw.strip()
        m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
        if m:
            raw = m.group(1).strip()
        result = json.loads(raw)
        if isinstance(result, list):
            return result[:4]
        return []
    except Exception:
        return []


def _gen_note_id(user_id: str, title: str) -> str:
    """生成笔记唯一 ID"""
    raw = f"{user_id}_{title}_{time.time()}_{time.time_ns()}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


# ==================== 笔记链接解析（[[笔记标题]] 语法）====================

def _parse_note_links(content: str, user_id: str) -> List[Dict[str, Any]]:
    """
    从笔记内容中解析 [[笔记标题]] 语法，尝试解析为目标笔记 ID
    返回: [{"title": "笔记标题", "note_id": "id或null"}, ...]
    """
    if not content:
        return []
    pattern = re.compile(r'\[\[([^\]]+)\]\]')
    matches = pattern.findall(content)
    if not matches:
        return []

    # 去重但保持顺序
    unique_titles = list(dict.fromkeys(t.strip() for t in matches if t.strip()))

    # 获取用户所有笔记，建立标题→ID 映射
    all_notes = _list_all(user_id)
    title_to_id = {n["title"]: n["note_id"] for n in all_notes}

    links = []
    for title in unique_titles:
        links.append({
            "title": title,
            "note_id": title_to_id.get(title),  # None 表示未找到（未创建或标题已变更）
        })
    return links


def get_graph_data(user_id: str) -> Dict[str, Any]:
    """
    获取用户笔记知识图谱数据
    返回: {"nodes": [...], "edges": [...]}
    """
    all_notes = _list_all(user_id)

    nodes = []
    note_map = {}  # note_id -> full note data (with links)
    for n in all_notes:
        full = get_note(user_id, n["note_id"])
        if full:
            note_map[n["note_id"]] = full
        nodes.append({
            "id": n["note_id"],
            "title": n.get("title", ""),
            "knowledge_points": n.get("knowledge_points", []),
            "has_ai_organized": n.get("has_ai_organized", False),
        })

    edges = []
    edge_keys = set()  # 去重
    for note_id, note in note_map.items():
        links = note.get("links", [])
        for link in links:
            target_id = link.get("note_id")
            if target_id and target_id in note_map:
                # 保证每对笔记只生成一条边（双向链接算一条）
                key = tuple(sorted([note_id, target_id]))
                if key not in edge_keys:
                    edge_keys.add(key)
                    edges.append({
                        "source": note_id,
                        "target": target_id,
                    })

    return {"nodes": nodes, "edges": edges}


def _list_all(user_id: str) -> List[Dict[str, Any]]:
    """列出用户所有笔记摘要"""
    notes = []
    d = _user_dir(user_id)
    if not os.path.exists(d):
        return notes
    for fname in os.listdir(d):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(d, fname), "r", encoding="utf-8") as f:
                    note = json.load(f)
                    notes.append({
                        "note_id": note.get("note_id"),
                        "title": note.get("title", ""),
                        "summary": note.get("content", "")[:100] if note.get("content") else "",
                        "created_at": note.get("created_at", ""),
                        "updated_at": note.get("updated_at", ""),
                        "has_ai_organized": note.get("ai_organized", False),
                        "ai_organized_at": note.get("ai_organized_at", ""),
                        "knowledge_points": note.get("knowledge_points", []),
                    })
            except Exception:
                continue
    # 按更新时间倒序
    notes.sort(key=lambda x: x.get("updated_at") or x.get("created_at") or "", reverse=True)
    return notes


# ==================== 公开 API ====================

def list_notes(user_id: str) -> List[Dict[str, Any]]:
    """获取用户笔记列表"""
    return _list_all(user_id)


def create_note(user_id: str, title: str, content: str) -> Dict[str, Any]:
    """创建新笔记"""
    note_id = _gen_note_id(user_id, title)
    now = datetime.now().isoformat()
    note = {
        "note_id": note_id,
        "title": title.strip() or "未命名笔记",
        "content": content,
        "created_at": now,
        "updated_at": now,
        "ai_organized": False,
        "ai_organized_at": "",
        "ai_organization_result": None,
        "knowledge_points": [],
        "links": _parse_note_links(content, user_id),
    }
    with open(_note_path(user_id, note_id), "w", encoding="utf-8") as f:
        json.dump(note, f, ensure_ascii=False, indent=2)
    return note


def get_note(user_id: str, note_id: str) -> Optional[Dict[str, Any]]:
    """获取单篇笔记详情"""
    path = _note_path(user_id, note_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def update_note(user_id: str, note_id: str, title: str = None, content: str = None,
                knowledge_points: List[str] = None) -> Optional[Dict[str, Any]]:
    """更新笔记（title/content/knowledge_points 传 None 表示不修改）"""
    note = get_note(user_id, note_id)
    if note is None:
        return None
    if title is not None:
        note["title"] = title.strip() or "未命名笔记"
    if content is not None:
        note["content"] = content
        # 内容变动后清除 AI 整理状态
        note["ai_organized"] = False
        note["ai_organized_at"] = ""
        note["ai_organization_result"] = None
        # 重新解析笔记链接
        note["links"] = _parse_note_links(content, user_id)
    if knowledge_points is not None:
        note["knowledge_points"] = knowledge_points
    note["updated_at"] = datetime.now().isoformat()
    with open(_note_path(user_id, note_id), "w", encoding="utf-8") as f:
        json.dump(note, f, ensure_ascii=False, indent=2)
    return note


def delete_note(user_id: str, note_id: str) -> bool:
    """删除笔记"""
    path = _note_path(user_id, note_id)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


# ==================== AI 整理共享逻辑 ====================

async def _call_organize_llm(content: str, title: str):
    """调用 LLM 进行笔记结构化整理，返回原始 AI 结果。不涉及保存操作，供 organize_note_preview 共用。"""
    llm = get_chat_openai(temperature=0.3, max_tokens=4096)

    # 保护图片标记：在发给 LLM 之前替换为占位符，防止 LLM 丢弃
    img_placeholders = {}
    def _protect_img(m):
        idx = len(img_placeholders)
        ph = f"\u200b\u200bIMG_{idx}\u200b\u200b"
        img_placeholders[ph] = m.group(0)
        return ph
    safe_content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', _protect_img, content)

    prompt = f"""你是一位专业的学习笔记整理助手。请对以下学习笔记进行结构化整理，输出 JSON 格式。

整理要求：
1. **术语补充**：对笔记中涉及的专业术语补充简明解释
2. **易错点区分**：识别并标记笔记中容易混淆或出错的知识点
3. **错误纠正**：检查并纠正笔记中的事实性错误或不准确表述
4. **结构化重组**：将笔记按知识点重新组织为清晰的层级结构

注意：笔记中的 ​​IMG_数字​​ 是图片占位符，请原样保留在 structured_content 中，不要删除或修改。

输出格式（严格 JSON，不要 markdown 代码块标记）：
```json
{{
  "original_title": "{title}",
  "organized_title": "整理后的标题（在原标题基础上优化）",
  "structured_content": "整理后的完整笔记内容（markdown 格式，含层级标题、列表等，必须原样保留 ​​IMG_数字​​ 占位符）",
  "knowledge_points": ["知识点1", "知识点2"],
  "terms": [
    {{"term": "术语名", "explanation": "简明解释"}}
  ],
  "error_prone_points": [
    {{"point": "易错点描述", "suggestion": "正确理解/记忆方法"}}
  ],
  "corrections": [
    {{"original": "原文错误表述", "corrected": "纠正后的表述"}}
  ],
  "summary": "一句话总结笔记核心内容"
}}
```

请直接输出纯 JSON，不要包含任何其他文字。

笔记标题：{title}
笔记内容：
{safe_content}
"""
    response = await llm.ainvoke(prompt)
    raw = response.content if hasattr(response, "content") else str(response)

    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
    if json_match:
        raw = json_match.group(1)
    ai_result = json.loads(raw.strip())

    # summary 为空时自动 fallback
    if not ai_result.get("summary", "").strip():
        sc = ai_result.get("structured_content", "") or ""
        first_line = next(
            (l.strip() for l in sc.split("\n")
             if l.strip() and not l.strip().startswith(("#", ">", "!", "-", "```"))),
            None
        )
        kps = ai_result.get("knowledge_points", [])
        ai_result["summary"] = (
            first_line[:80] if first_line
            else (kps[0] if kps else "暂无摘要")
        )

    # 恢复图片占位符
    if "structured_content" in ai_result:
        for ph, img_md in img_placeholders.items():
            if ph in ai_result["structured_content"]:
                ai_result["structured_content"] = ai_result["structured_content"].replace(ph, img_md)
            else:
                import re as re_mod
                tag = ph.replace("\u200b", "")
                ai_result["structured_content"] = re_mod.sub(
                    re.escape(tag), img_md, ai_result["structured_content"]
                )

    return ai_result, content


async def organize_note_preview(user_id: str, note_id: str, title: str, content: str) -> Dict[str, Any]:
    """
    AI 结构化整理预览（不保存），返回原始与整理结果的 diff 数据。
    用户可通过 accept_organize_preview() 确认后保存。
    """
    try:
        ai_result, _ = await _call_organize_llm(content, title)
    except Exception as e:
        ai_result = {
            "error": f"AI 整理失败: {str(e)}",
            "structured_content": content,
            "terms": [],
            "error_prone_points": [],
            "corrections": [],
            "summary": "",
        }

    organized_content = ai_result.get("structured_content", content)

    # 计算 diff（CPU 密集，在线程池中执行）
    loop = asyncio.get_event_loop()
    diff_lines = await loop.run_in_executor(None, _compute_line_diff, content, organized_content)
    added = sum(1 for d in diff_lines if d["type"] == "added")
    removed = sum(1 for d in diff_lines if d["type"] == "removed")

    return {
        "original": content,
        "organized": organized_content,
        "organized_title": ai_result.get("organized_title", title),
        "diff_lines": diff_lines,
        "diff_stats": {
            "added": added,
            "removed": removed,
            "total_original": len(content.split("\n")),
            "total_organized": len(organized_content.split("\n")),
        },
        "ai_result": {
            "terms": ai_result.get("terms", []),
            "error_prone_points": ai_result.get("error_prone_points", []),
            "corrections": ai_result.get("corrections", []),
            "summary": ai_result.get("summary", ""),
            "knowledge_points": ai_result.get("knowledge_points", []),
        },
    }


async def accept_organize_preview(user_id: str, note_id: str, title: str, organized_content: str,
                                  ai_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    接受 AI 整理预览结果，保存到笔记。
    由前端用户在确认 diff 后调用。
    """
    note = get_note(user_id, note_id)
    if note is None:
        return None

    note["title"] = title
    note["content"] = organized_content
    note["links"] = _parse_note_links(organized_content, user_id)
    note["ai_organized"] = True
    note["ai_organized_at"] = datetime.now().isoformat()
    note["ai_organization_result"] = {
        "terms": ai_result.get("terms", []),
        "error_prone_points": ai_result.get("error_prone_points", []),
        "corrections": ai_result.get("corrections", []),
        "summary": ai_result.get("summary", ""),
    }
    ai_kps = ai_result.get("knowledge_points", [])
    if ai_kps and isinstance(ai_kps, list) and len(ai_kps) > 0:
        note["knowledge_points"] = ai_kps[:4]
    else:
        extracted = await _auto_bind_knowledge_points(organized_content)
        if extracted:
            note["knowledge_points"] = extracted
    note["updated_at"] = datetime.now().isoformat()
    with open(_note_path(user_id, note_id), "w", encoding="utf-8") as f:
        json.dump(note, f, ensure_ascii=False, indent=2)

    return note


# ==================== 思维导图生成 ====================

async def generate_note_mindmap(title: str, content: str) -> Dict[str, Any]:
    """
    从笔记内容生成思维导图 JSON 结构。
    每个节点包含 keywords 字段用于前端定位跳转。
    返回: { "name": "...", "children": [...] }
    """
    try:
        llm = get_chat_openai(temperature=0.3, max_tokens=2048)
        prompt = f"""你是一位学习笔记结构化助手。请将以下笔记内容提炼为思维导图 JSON 格式。

要求：
1. 根节点为笔记标题
2. 一级子节点为笔记的核心主题/章节
3. 二级子节点为具体知识点（尽量短，1-10个字）
4. 最多 2 层深度，不要嵌套过深
5. 如果笔记内容较少，可以只有一级子节点
6. 每个节点必须包含 keywords 数组（1-3个该节点对应的原文关键词/短语），用于前端定位跳转——从原始笔记中提取
7. 输出严格 JSON，不要 markdown 代码块标记

输出格式：
{{
  "name": "思维导图标题",
  "children": [
    {{
      "name": "主题1",
      "keywords": ["原文关键词1", "原文关键词2"],
      "children": [
        {{"name": "知识点1", "keywords": ["关键词a", "关键词b"]}},
        {{"name": "知识点2", "keywords": ["关键词c"]}}
      ]
    }}
  ]
}}

请直接输出纯 JSON，不要包含任何其他文字。

笔记标题：{title}
笔记内容：
{content[:3000]}
"""
        response = await llm.ainvoke(prompt)
        raw = response.content if hasattr(response, "content") else str(response)
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
        if json_match:
            raw = json_match.group(1)
        result = json.loads(raw.strip())
        return result
    except Exception as e:
        return {"name": title, "keywords": [], "children": [{"name": f"解析失败: {str(e)[:50]}", "keywords": []}]}


# ==================== 文本 diff 工具 ====================

def _compute_line_diff(original: str, optimized: str) -> List[Dict[str, Any]]:
    """
    计算两段文本的行级 diff，返回差异行列表。
    每行格式: { "type": "same"|"added"|"removed", "line": str }
    
    基于 LCS (最长公共子序列) 算法实现，不依赖外部库。
    """
    orig_lines = original.split("\n")
    opt_lines = optimized.split("\n")
    
    # 构建 LCS 表
    m, n = len(orig_lines), len(opt_lines)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if orig_lines[i - 1] == opt_lines[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    
    # 回溯生成 diff
    result = []
    i, j = m, n
    temp = []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and orig_lines[i - 1] == opt_lines[j - 1]:
            temp.append({"type": "same", "line": orig_lines[i - 1]})
            i -= 1
            j -= 1
        elif j > 0 and (i == 0 or dp[i][j - 1] >= dp[i - 1][j]):
            temp.append({"type": "added", "line": opt_lines[j - 1]})
            j -= 1
        else:
            temp.append({"type": "removed", "line": orig_lines[i - 1]})
            i -= 1
    
    temp.reverse()
    return temp


# ==================== AI 优化笔记（含 diff 对比，不自动保存）====================

async def optimize_note_text(user_id: str, note_id: str, title: str, content: str) -> Dict[str, Any]:
    """
    AI 优化笔记文本（只优化不保存），返回原始内容与优化后内容的 diff 数据。
    
    返回:
    {
        "original": str,         # 原始内容
        "optimized": str,        # 优化后的内容
        "diff_lines": [...],     # 行级 diff
        "diff_stats": {          # 统计信息
            "added": int,        # 新增行数
            "removed": int,      # 删除行数
            "total_original": int,
            "total_optimized": int
        },
        "summary": str           # 优化说明
    }
    """
    try:
        llm = get_chat_openai(temperature=0.3, max_tokens=4096)

        prompt = f"""你是一位专业的学习笔记润色助手。请优化以下学习笔记，使其表达更清晰、逻辑更连贯。

优化要求：
1. **修正语病和错别字**：纠正语法错误和拼写错误
2. **优化表达**：让句子更通顺、简明
3. **保留原意**：不要改变笔记的核心内容和知识点
4. **保留格式**：保持原有的 Markdown 层级结构、列表、代码块等
5. **保留图片**：笔记中的 ![](url) 图片标记必须原样保留
6. **不要过度修改**：只优化有明显问题的地方，不要重写整篇笔记

输出格式（严格 JSON，不要 markdown 代码块标记）：
{{
  "optimized_content": "优化后的完整笔记内容",
  "summary": "简要说明做了哪些优化（1-2句话）"
}}

请直接输出纯 JSON，不要包含任何其他文字。

笔记标题：{title}
笔记内容：
{content}
"""
        response = await llm.ainvoke(prompt)
        raw = response.content if hasattr(response, "content") else str(response)

        # 从 markdown 代码块中提取 JSON
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
        if json_match:
            raw = json_match.group(1)

        result = json.loads(raw.strip())
        optimized = result.get("optimized_content", content)

    except Exception as e:
        optimized = content
        result = {"summary": f"优化失败: {str(e)}", "optimized_content": content}

    # 计算 diff（CPU 密集，在线程池中执行，不阻塞事件循环）
    loop = asyncio.get_event_loop()
    diff_lines = await loop.run_in_executor(None, _compute_line_diff, content, optimized)
    added = sum(1 for d in diff_lines if d["type"] == "added")
    removed = sum(1 for d in diff_lines if d["type"] == "removed")

    return {
        "original": content,
        "optimized": optimized,
        "diff_lines": diff_lines,
        "diff_stats": {
            "added": added,
            "removed": removed,
            "total_original": len(content.split("\n")),
            "total_optimized": len(optimized.split("\n")),
        },
        "summary": result.get("summary", "AI 优化完成"),
    }


# ==================== 导出功能 ====================

def _resolve_note_image_url(url: str) -> Optional[str]:
    """将笔记中的图片 /note-uploads/{user}/attachments/{file} 解析为本地绝对路径"""
    # 去除可能附加的宽度标记（如 =200x）
    url_clean = re.sub(r'\s*=\d+x\s*$', '', url)
    m = re.match(r'/note-uploads/([^/]+)/attachments/(.+)$', url_clean)
    if not m:
        return None
    user_part, filename = m.group(1), m.group(2)
    if '..' in user_part or '..' in filename:
        return None
    local = os.path.join(NOTE_BASE_DIR, user_part, 'attachments', filename)
    return local if os.path.isfile(local) else None


def export_to_docx(user_id: str, note_id: str) -> Optional[bytes]:
    """导出笔记为 Word (.docx) 格式，返回字节流"""
    try:
        from docx import Document
        from docx.shared import Pt, Inches, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError:
        return None

    note = get_note(user_id, note_id)
    if note is None:
        return None

    doc = Document()

    # 设置默认字体
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Microsoft YaHei"
    font.size = Pt(11)

    # 标题
    title = doc.add_heading(note.get("title", "笔记"), level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # 时间信息
    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = info.add_run(f"创建时间: {note.get('created_at', '')}")
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(128, 128, 128)
    if note.get("ai_organized"):
        info.add_run("\n").font.size = Pt(9)
        run2 = info.add_run(f"AI 整理时间: {note.get('ai_organized_at', '')}")
        run2.font.size = Pt(9)
        run2.font.color.rgb = RGBColor(128, 128, 128)

    doc.add_paragraph("─" * 50)

    # 笔记内容
    img_pat = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
    content = note.get("content", "")
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue

        # 检测本行是否包含图片
        imgs = list(img_pat.finditer(line))
        if imgs:
            # 先确定行类型（去掉图片 markdown 后） 
            text_only = img_pat.sub('', line).strip()
            is_heading1 = text_only.startswith("# ") and not text_only.startswith("## ")
            is_heading2 = text_only.startswith("## ") and not text_only.startswith("### ")
            is_heading3 = text_only.startswith("### ")
            is_bullet = text_only.startswith("- ") or text_only.startswith("* ")

            if is_heading1 or is_heading2 or is_heading3:
                level = 1 if is_heading1 else (2 if is_heading2 else 3)
                prefix_len = level + 1  # "# ", "## ", "### "
                doc.add_heading(text_only[prefix_len:], level=level)
            elif is_bullet:
                p = doc.add_paragraph(text_only[2:], style="List Bullet")
            else:
                p = doc.add_paragraph(text_only) if text_only else None

            # 插入图片
            for m in imgs:
                img_path = _resolve_note_image_url(m.group(2))
                if img_path:
                    try:
                        doc.add_picture(img_path, width=Inches(5.5))
                        last_para = doc.paragraphs[-1]
                        last_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    except Exception:
                        doc.add_paragraph(f'[图片: {m.group(1) or "image"}]')
                else:
                    doc.add_paragraph(f'[图片: {m.group(1) or "image"}]')
        elif line.startswith("# "):
            doc.add_heading(line[2:], level=1)
        elif line.startswith("## "):
            doc.add_heading(line[3:], level=2)
        elif line.startswith("### "):
            doc.add_heading(line[4:], level=3)
        elif line.startswith("- ") or line.startswith("* "):
            doc.add_paragraph(line[2:], style="List Bullet")
        else:
            p = doc.add_paragraph(line)

    # AI 整理结果（如果有）
    ai_result = note.get("ai_organization_result")
    if ai_result:
        doc.add_page_break()
        doc.add_heading("AI 结构化整理", level=1)

        # 摘要
        summary = ai_result.get("summary", "")
        if summary:
            p = doc.add_paragraph()
            run = p.add_run("📝 摘要：")
            run.bold = True
            p.add_run(summary)

        # 术语补充
        terms = ai_result.get("terms", [])
        if terms:
            doc.add_heading("📖 术语补充", level=2)
            for t in terms:
                p = doc.add_paragraph(style="List Bullet")
                run = p.add_run(f"{t.get('term', '')}：")
                run.bold = True
                p.add_run(t.get("explanation", ""))

        # 易错点
        errors = ai_result.get("error_prone_points", [])
        if errors:
            doc.add_heading("⚠️ 易错点区分", level=2)
            for e in errors:
                p = doc.add_paragraph(style="List Bullet")
                run = p.add_run(f"{e.get('point', '')}")
                run.bold = True
                p.add_run(f" → {e.get('suggestion', '')}")

        # 错误纠正
        corrections = ai_result.get("corrections", [])
        if corrections:
            doc.add_heading("✅ 错误纠正", level=2)
            for c in corrections:
                p = doc.add_paragraph(style="List Bullet")
                run = p.add_run("原文：")
                run.bold = True
                run.font.color.rgb = RGBColor(200, 50, 50)
                p.add_run(c.get("original", ""))
                p2 = doc.add_paragraph(style="List Bullet")
                run2 = p2.add_run("纠正：")
                run2.bold = True
                run2.font.color.rgb = RGBColor(50, 150, 50)
                p2.add_run(c.get("corrected", ""))

    # 保存到内存字节流
    import io
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


def export_to_pdf(user_id: str, note_id: str) -> Optional[bytes]:
    """导出笔记为 PDF 格式，返回字节流"""
    note = get_note(user_id, note_id)
    if note is None:
        return None

    try:
        from fpdf import FPDF
    except ImportError:
        # 回退方案：先生成 docx 再转换
        return None

    pdf = FPDF()
    pdf.add_page()

    # 尝试添加中文字体（fpdf2 需要指定 .ttf 文件路径）
    font_added = False
    chinese_font_name = "Helvetica"

    # 使用更通用的中文字体路径（Windows + Linux 全平台兼容）
    font_candidates = [
        # Windows 路径
        (r"C:\Windows\Fonts\msyh.ttc", "msyh"),
        (r"C:\Windows\Fonts\msyh.ttf", "msyh"),
        (r"C:\Windows\Fonts\simsun.ttc", "simsun"),
        (r"C:\Windows\Fonts\SimSun.ttf", "simsun"),
        (r"C:\Windows\Fonts\msyhbd.ttc", "msyhbd"),
        # Linux 路径（Debian/Ubuntu: fonts-wqy-zenhei / fonts-wqy-microhei / fonts-noto-cjk）
        ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "wqy-zenhei"),
        ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", "wqy-microhei"),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "noto-cjk"),
        ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", "noto-cjk"),
        # 项目内置字体（可选，放置后无需系统字体）
        (os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "msyh.ttc"), "msyh"),
        (os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "wqy-zenhei.ttc"), "wqy-zenhei"),
    ]
    for font_path, fname in font_candidates:
        if os.path.exists(font_path):
            try:
                pdf.add_font(fname, "", font_path, uni=True)
                chinese_font_name = fname
                font_added = True
                break
            except Exception:
                continue

    # 设置基础字体
    font_name = chinese_font_name

    # 标题
    pdf.set_font(font_name, "", 16)
    pdf.cell(0, 10, note.get("title", "笔记"), new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font(font_name, "", 9)
    pdf.cell(0, 8, f"创建时间: {note.get('created_at', '')}", new_x="LMARGIN", new_y="NEXT", align="C")
    if note.get("ai_organized"):
        pdf.cell(0, 8, f"AI 整理时间: {note.get('ai_organized_at', '')}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)

    # 内容
    pdf.set_font(font_name, "", 11)
    content = note.get("content", "")
    img_pat = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

    for line in content.split("\n"):
        line = line.strip()
        if not line:
            pdf.ln(3)
            continue

        # 检测本行是否包含图片
        imgs = list(img_pat.finditer(line))
        if imgs:
            # 去掉图片 markdown 后渲染文本
            text_only = img_pat.sub('', line).strip()
            if text_only:
                if text_only.startswith("#"):
                    level = len(text_only) - len(text_only.lstrip("#"))
                    pdf.set_font(font_name, "", 14 if level <= 2 else 12)
                    pdf.ln(3)
                    pdf.multi_cell(0, 7, text_only.lstrip("#").strip())
                    pdf.set_font(font_name, "", 11)
                else:
                    try:
                        pdf.multi_cell(0, 6, text_only)
                    except Exception:
                        pass

            # 嵌入图片
            for m in imgs:
                img_path = _resolve_note_image_url(m.group(2))
                if img_path:
                    try:
                        # 检查剩余空间，不足则换页
                        if pdf.get_y() > pdf.h - 60:
                            pdf.add_page()
                        pdf.image(img_path, w=pdf.epw)  # 图片宽度填满有效区域
                        pdf.ln(3)
                    except Exception:
                        try:
                            pdf.cell(0, 8, f'[图片: {m.group(1) or "image"}]', new_x="LMARGIN", new_y="NEXT")
                        except Exception:
                            pass
                else:
                    try:
                        pdf.cell(0, 8, f'[图片: {m.group(1) or "image"}]', new_x="LMARGIN", new_y="NEXT")
                    except Exception:
                        pass
        elif line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            pdf.set_font(font_name, "", 14 if level <= 2 else 12)
            pdf.ln(3)
            pdf.multi_cell(0, 7, line.lstrip("#").strip())
            pdf.set_font(font_name, "", 11)
        else:
            try:
                pdf.multi_cell(0, 6, line)
            except Exception:
                try:
                    pdf.multi_cell(0, 6, line.encode("ascii", errors="ignore").decode())
                except Exception:
                    pdf.ln(6)

    # AI 整理结果
    ai_result = note.get("ai_organization_result")
    if ai_result:
        pdf.add_page()
        pdf.set_font(font_name, "", 16)
        pdf.cell(0, 10, "AI 结构化整理", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(5)

        summary = ai_result.get("summary", "")
        if summary:
            pdf.set_font(font_name, "", 11)
            try:
                pdf.cell(0, 8, f"摘要: {summary}", new_x="LMARGIN", new_y="NEXT")
            except Exception:
                pass
            pdf.ln(3)

        terms = ai_result.get("terms", [])
        if terms:
            pdf.set_font(font_name, "", 13)
            pdf.cell(0, 8, "术语补充", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(font_name, "", 11)
            for t in terms:
                try:
                    pdf.multi_cell(0, 6, f"  {t.get('term', '')}: {t.get('explanation', '')}")
                except Exception:
                    pass

        errors = ai_result.get("error_prone_points", [])
        if errors:
            pdf.set_font(font_name, "", 13)
            pdf.cell(0, 8, "易错点区分", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(font_name, "", 11)
            for e in errors:
                try:
                    pdf.multi_cell(0, 6, f"  {e.get('point', '')} -> {e.get('suggestion', '')}")
                except Exception:
                    pass

        corrections = ai_result.get("corrections", [])
        if corrections:
            pdf.set_font(font_name, "", 13)
            pdf.cell(0, 8, "错误纠正", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(font_name, "", 11)
            for c in corrections:
                try:
                    pdf.multi_cell(0, 6, f"  原文: {c.get('original', '')}")
                    pdf.multi_cell(0, 6, f"  纠正: {c.get('corrected', '')}")
                    pdf.ln(2)
                except Exception:
                    pass

    return bytes(pdf.output())


def explain_selection_stream(selected_text: str):
    """用 AI 流式解释笔记中的选中文本，yield SSE 事件（Generator）"""
    if not selected_text or not selected_text.strip():
        yield f"data: {json.dumps({'type': 'error', 'text': '选中文本不能为空'})}\n\n"
        return

    try:
        llm = get_chat_openai(temperature=0.3, max_tokens=1024)
        prompt = f"""你是一位专业的学习助手，请对用户笔记中选中的内容进行简明易懂的解释。

要求：
1. 用通俗语言解释选中内容的核心知识点
2. 补充必要的背景或上下文
3. 控制在 300 字以内

请直接输出解释文本，不要使用 JSON 格式。
解释结束后，在末尾单独用一行输出：关键词：关键词1、关键词2、关键词3

选中内容：
{selected_text.strip()}
"""
        full_text = ""
        for chunk in llm.stream(prompt):
            if chunk.content:
                full_text += chunk.content
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk.content})}\n\n"

        # 从完整文本中提取关键词行
        import re as re_mod
        kw_match = re_mod.search(r'关键词[：:]\s*(.+)', full_text)
        keywords = []
        if kw_match:
            kw_str = kw_match.group(1)
            keywords = [k.strip() for k in re_mod.split(r'[、,，]', kw_str) if k.strip()]
            # 从原文中去掉关键词行
            full_text_clean = re_mod.sub(r'关键词[：:]\s*.+', '', full_text).strip()
        else:
            full_text_clean = full_text.strip()

        yield f"data: {json.dumps({'type': 'done', 'text': full_text_clean, 'keywords': keywords})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'text': f'解释生成失败: {str(e)}'})}\n\n"


def life_case_stream(selected_text: str):
    """用 AI 流式生成选中文本对应的生活案例，yield SSE 事件（Generator）"""
    if not selected_text or not selected_text.strip():
        yield f"data: {json.dumps({'type': 'error', 'text': '选中文本不能为空'})}\n\n"
        return

    try:
        llm = get_chat_openai(temperature=0.7, max_tokens=1024)
        prompt = f"""你是一位善于联系实际生活的学习助手，请为用户笔记中选中的内容提供一个贴近生活的案例。

要求：
1. 根据选中内容的核心知识点，结合日常生活场景举例说明
2. 案例要真实、通俗、贴近生活，帮助用户理解抽象概念
3. 控制在 300 字以内
4. 如果选中内容不适合或无法生成生活案例，请直接输出：当前选中内容暂时无法提供相关生活案例

请直接输出案例文本，不要使用 JSON 格式。
案例结束后，如果需要提取关键词，在末尾单独用一行输出：关键词：关键词1、关键词2、关键词3

选中内容：
{selected_text.strip()}
"""
        full_text = ""
        for chunk in llm.stream(prompt):
            if chunk.content:
                full_text += chunk.content
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk.content})}\n\n"

        # 从完整文本中提取关键词行
        import re as re_mod
        kw_match = re_mod.search(r'关键词[：:]\s*(.+)', full_text)
        keywords = []
        if kw_match:
            kw_str = kw_match.group(1)
            keywords = [k.strip() for k in re_mod.split(r'[、,，]', kw_str) if k.strip()]
            full_text_clean = re_mod.sub(r'关键词[：:]\s*.+', '', full_text).strip()
        else:
            full_text_clean = full_text.strip()

        yield f"data: {json.dumps({'type': 'done', 'text': full_text_clean, 'keywords': keywords})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'text': f'生活案例生成失败: {str(e)}'})}\n\n"


def get_export_filename(note: Dict[str, Any], fmt: str) -> str:
    """生成导出文件名"""
    title = re.sub(r'[\\/:*?"<>|]', "_", note.get("title", "笔记"))
    ext = ".docx" if fmt == "docx" else ".pdf"
    return f"{title}{ext}"


# ==================== 后台异步更新用户特征（写笔记场景）====================

async def trigger_note_feature_update(user_id: str, title: str, content: str, action: str = "save", use_ai: bool = False):
    """在后台更新用户特征（由调用方自行 create_task 做 fire-and-forget）"""
    try:
        task_content = f"笔记标题: {title[:80]}，操作: {action}，AI整理: {use_ai}，内容长度: {len(content)}字"
        performance_data = {
            "action": action,
            "title_length": len(title),
            "content_length": len(content),
            "ai_organized": use_ai,
            "has_content": bool(content.strip()),
        }
        from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
        updater = DynamicFeatureUpdater()
        await updater.atomic_update_features_async(
            user_id=user_id,
            task_type="note_writing",
            task_content=task_content,
            performance_data=performance_data,
            completion_quality="high" if content.strip() else "low",
            time_spent=f"笔记{action}",
        )
        print(f"✅ [笔记特征更新] 用户 {user_id} 特征更新完成（{action}）")
    except Exception as e:
        print(f"⚠️ [笔记特征更新] 后台更新失败（不影响主流程）: {e}")
