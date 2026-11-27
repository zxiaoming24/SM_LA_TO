"""
知识图谱服务：上传文档 -> 解析内容 -> LLM提取知识点和关系 -> 生成可视化图谱数据

数据存储结构:
  memory/knowledge_graphs/{user_id}/
    index.json           <- 所有图谱的索引列表
    {graph_id}.json      <- 单个图谱数据 (nodes + edges)
"""

import os
import json
import uuid
import hashlib
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# ── 存储根目录 ──
GRAPH_STORAGE_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "memory", "knowledge_graphs"
)

# ── 支持的文档类型 ──
SUPPORTED_EXTENSIONS = {
    ".pdf": "PDF",
    ".md": "Markdown",
    ".docx": "Word",
    ".doc": "Word",
    ".txt": "文本",
    ".xmind": "XMind",
}


# ====================================================================
#  文档解析
# ====================================================================

async def parse_document(file_path: str) -> str:
    """根据文件扩展名解析文档内容"""
    ext = Path(file_path).suffix.lower()

    if ext == ".pdf":
        return await _read_pdf(file_path)
    elif ext == ".md":
        return await _read_markdown(file_path)
    elif ext in (".docx", ".doc"):
        return await _read_word(file_path)
    elif ext == ".txt":
        return await _read_text(file_path)
    elif ext == ".xmind":
        return await _read_xmind(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")


async def _read_pdf(file_path: str) -> str:
    try:
        import fitz
    except ImportError:
        raise ImportError("请安装 PyMuPDF: pip install pymupdf")

    def _read():
        doc = fitz.open(file_path)
        text = "".join(page.get_text() for page in doc)
        doc.close()
        return text

    return await asyncio.to_thread(_read)


async def _read_markdown(file_path: str) -> str:
    return await asyncio.to_thread(
        lambda: Path(file_path).read_text("utf-8")
    )


async def _read_word(file_path: str) -> str:
    try:
        from docx import Document
    except ImportError:
        raise ImportError("请安装 python-docx: pip install python-docx")

    def _read():
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)

    return await asyncio.to_thread(_read)


async def _read_text(file_path: str) -> str:
    return await asyncio.to_thread(
        lambda: Path(file_path).read_text("utf-8", errors="replace")
    )


async def _read_xmind(file_path: str) -> str:
    import zipfile
    import xml.etree.ElementTree as ET

    def _read():
        with zipfile.ZipFile(file_path, "r") as z:
            if "content.xml" not in z.namelist():
                return ""
            with z.open("content.xml") as f:
                tree = ET.parse(f)
                texts = []
                for elem in tree.iter():
                    if elem.text and elem.text.strip():
                        texts.append(elem.text.strip())
                return "\n".join(texts)

    return await asyncio.to_thread(_read)


# ====================================================================
#  LLM 提取知识点与关系
# ====================================================================

def _get_llm():
    """延迟导入 llm_config，避免循环依赖"""
    from utils.llm_config import get_chat_openai
    return get_chat_openai(temperature=0.3, max_tokens=4096)


EXTRACTION_PROMPT = """你是一个专业的课程知识图谱构建专家。
请从以下文档内容中，提取出核心的知识点实体以及它们之间的关系。

要求：
1. 提取 5~30 个知识点，过多过少都不合适
2. 每个知识点包含：id（唯一标识如 kp_1）、name（名称）、description（一句话描述）、category（分类：概念/原理/方法/工具/应用）
3. 知识点之间的关系包含：source（前置知识点id）、target（后置知识点id）、relation（关系类型：前置依赖/包含/关联/举例/对比）
4. 关系数量应该是知识点数量的 0.8~1.5 倍

请严格按照以下 JSON 格式返回，不要包含任何其他文字：

```json
{{
  "title": "文档标题（从内容推断）",
  "nodes": [
    {{"id": "kp_1", "name": "知识点名称", "description": "简短描述", "category": "概念"}},
    ...
  ],
  "edges": [
    {{"source": "kp_1", "target": "kp_2", "relation": "前置依赖"}},
    ...
  ]
}}
```

文档内容：
{content}
"""


async def extract_knowledge_graph(text: str, filename: str) -> Dict[str, Any]:
    """调用 LLM 从文档文本中提取知识图谱"""
    if not text.strip():
        raise ValueError("文档内容为空，无法提取知识图谱")

    # 如果文本太长，截断前端部分（取前 8000 字符保证能覆盖主要知识点）
    content = text[:8000]
    if len(text) > 8000:
        content += "\n\n...(后续内容已截断)..."

    prompt = EXTRACTION_PROMPT.format(content=content)

    llm = _get_llm()
    response = await llm.ainvoke(prompt)
    result_text = response.content

    # 从 markdown 代码块中提取 JSON
    json_str = result_text
    if "```json" in json_str:
        json_str = json_str.split("```json")[1].split("```")[0].strip()
    elif "```" in json_str:
        json_str = json_str.split("```")[1].split("```")[0].strip()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        # 如果解析失败，尝试直接找 {} 包裹的最外层 JSON
        import re
        match = re.search(r"\{[\s\S]*\}", json_str)
        if match:
            data = json.loads(match.group())
        else:
            raise ValueError(f"LLM 返回无法解析的 JSON:\n{result_text[:500]}")

    # 保证必有 title
    if "title" not in data or not data["title"]:
        data["title"] = Path(filename).stem

    # 保证 nodes/edges 不为空
    data.setdefault("nodes", [])
    data.setdefault("edges", [])
    data["_source_file"] = filename
    data["_total_chars"] = len(text)
    data["_node_count"] = len(data["nodes"])
    data["_edge_count"] = len(data["edges"])

    return data


# ====================================================================
#  图谱数据持久化
# ====================================================================

def _ensure_user_dir(user_id: str) -> str:
    """确保用户存储目录存在，返回目录路径"""
    user_dir = os.path.join(GRAPH_STORAGE_ROOT, user_id)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir


def _index_path(user_id: str) -> str:
    return os.path.join(GRAPH_STORAGE_ROOT, user_id, "index.json")


def _read_index(user_id: str) -> list:
    path = _index_path(user_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _write_index(user_id: str, index: list):
    path = _index_path(user_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


async def create_graph(user_id: str, file_path: str) -> Dict[str, Any]:
    """
    完整流程：上传文件路径 -> 解析文档 -> LLM提取 -> 持久化存储
    返回图谱元信息
    """
    filename = Path(file_path).name

    # 1. 解析文档
    text = await parse_document(file_path)
    if not text.strip():
        raise ValueError(f"文件 {filename} 内容为空，无法解析")

    # 2. LLM 提取
    graph_data = await extract_knowledge_graph(text, filename)

    # 3. 构造图谱记录
    graph_id = hashlib.md5(
        f"{user_id}_{filename}_{datetime.now().isoformat()}".encode()
    ).hexdigest()[:12]

    record = {
        "graph_id": graph_id,
        "title": graph_data.get("title", Path(filename).stem),
        "source_file": filename,
        "created_at": datetime.now().isoformat(),
        "node_count": graph_data["_node_count"],
        "edge_count": graph_data["_edge_count"],
        "total_chars": graph_data["_total_chars"],
    }

    # 4. 存储图谱数据
    user_dir = _ensure_user_dir(user_id)
    graph_path = os.path.join(user_dir, f"{graph_id}.json")
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)

    # 5. 更新索引
    index = _read_index(user_id)
    # 如果同文件已经生成过图谱，覆盖
    for i, item in enumerate(index):
        if item["source_file"] == filename:
            # 删除旧数据文件
            old_path = os.path.join(user_dir, f"{item['graph_id']}.json")
            if os.path.exists(old_path):
                os.remove(old_path)
            index[i] = record
            break
    else:
        index.insert(0, record)
    _write_index(user_id, index)

    return record


def get_graphs(user_id: str) -> List[Dict[str, Any]]:
    """获取用户所有知识图谱列表"""
    return _read_index(user_id)


def get_graph_data(user_id: str, graph_id: str) -> Optional[Dict[str, Any]]:
    """获取单个图谱的完整数据（同步，用于同步上下文）"""
    graph_path = os.path.join(GRAPH_STORAGE_ROOT, user_id, f"{graph_id}.json")
    if not os.path.exists(graph_path):
        return None
    with open(graph_path, "r", encoding="utf-8") as f:
        return json.load(f)


async def async_get_graph_data(user_id: str, graph_id: str) -> Optional[Dict[str, Any]]:
    """异步获取单个图谱的完整数据，文件读取在线程池执行"""
    return await asyncio.to_thread(get_graph_data, user_id, graph_id)


def delete_graph(user_id: str, graph_id: str) -> bool:
    """删除图谱"""
    index = _read_index(user_id)
    new_index = [item for item in index if item["graph_id"] != graph_id]
    if len(new_index) == len(index):
        return False  # 没找到

    # 删除数据文件
    graph_path = os.path.join(GRAPH_STORAGE_ROOT, user_id, f"{graph_id}.json")
    if os.path.exists(graph_path):
        os.remove(graph_path)

    _write_index(user_id, new_index)
    return True


async def merge_and_save_graphs(user_id: str, graph_ids: List[str], merged_title: str = "") -> Dict[str, Any]:
    """
    异步合并多个图谱：
    1. 机械去重：同名节点合并，所有边保留
    2. LLM 发现跨文档关系：LLM 分析不同文档之间的知识点关联，补充跨文档边
    3. 不删除/不修改任何原始节点
    """
    if len(graph_ids) < 2:
        raise ValueError("至少选择2个图谱才能合并")

    # ── 1. 异步读取所有图谱数据 ──
    all_sources = []
    for gid in graph_ids:
        data = await async_get_graph_data(user_id, gid)
        if data is not None:
            all_sources.append(data)

    if len(all_sources) < 2:
        raise ValueError("有效的图谱不足2个")

    source_titles = []

    # ── 2. 机械去重合并 ──
    name_to_node = {}       # name -> node (保留第一个)
    all_raw_edges = []
    old_id_to_name = {}

    for src in all_sources:
        title = src.get("title", src.get("_source_file", "未知"))
        source_titles.append(title)

        for n in src.get("nodes", []):
            name = n.get("name", "")
            nid = n.get("id", "")
            if nid and name:
                old_id_to_name[nid] = name
            if not name:
                continue
            if name not in name_to_node:
                name_to_node[name] = {**n, "_source_doc": title}

        for e in src.get("edges", []):
            all_raw_edges.append({**e, "_source_doc": title})

    # 新 ID 映射
    merged_nodes = []
    name_to_new_id = {}
    for i, (name, node) in enumerate(name_to_node.items()):
        new_id = f"kp_{i + 1}"
        name_to_new_id[name] = new_id
        merged_nodes.append({**node, "id": new_id})

    # 合并原始边（按名称映射）
    seen_edge_keys = set()
    base_edges = []
    for e in all_raw_edges:
        src_name = old_id_to_name.get(e.get("source"), "")
        tgt_name = old_id_to_name.get(e.get("target"), "")
        if not src_name or not tgt_name:
            continue
        ns = name_to_new_id.get(src_name)
        nt = name_to_new_id.get(tgt_name)
        if not ns or not nt or ns == nt:
            continue
        key = f"{ns}_{nt}"
        if key not in seen_edge_keys:
            seen_edge_keys.add(key)
            base_edges.append({
                "source": ns, "target": nt,
                "relation": e.get("relation", "关联"),
            })

    title = merged_title or f"融合图谱 ({' + '.join(source_titles)})"

    # ── 3. LLM 发现跨文档关系 ──
    cross_edges = []
    try:
        cross_edges = await _discover_cross_doc_edges(
            merged_nodes, name_to_new_id,
            source_titles, base_edges
        )
    except Exception as e:
        print(f"⚠️ 跨文档关系发现失败（不影响基础合并）: {e}")

    # ── 4. 合并所有边（基础边 + 跨文档边） ──
    all_edges = list(base_edges)
    for ce in cross_edges:
        key = f"{ce['source']}_{ce['target']}"
        if key not in seen_edge_keys:
            seen_edge_keys.add(key)
            all_edges.append(ce)
            print(f"  🔗 补充跨文档边: {ce.get('relation','')}")

    merged = {
        "title": title,
        "nodes": merged_nodes,
        "edges": all_edges,
        "_source_file": f"merged_{'_'.join(graph_ids)}",
        "_merged_from": graph_ids,
        "_node_count": len(merged_nodes),
        "_edge_count": len(all_edges),
        "_is_merged": True,
        "_cross_edges": len(cross_edges),
    }

    # ── 5. 保存 ──
    import time
    graph_id = "merged_" + hashlib.md5(
        f"{user_id}_{time.time()}".encode()
    ).hexdigest()[:8]

    record = {
        "graph_id": graph_id,
        "title": title,
        "source_file": f"merged_{'_'.join(graph_ids)}",
        "created_at": datetime.now().isoformat(),
        "node_count": len(merged_nodes),
        "edge_count": len(all_edges),
        "_is_merged": True,
        "_cross_edges": len(cross_edges),
    }

    await asyncio.to_thread(_save_graph_file, user_id, graph_id, merged, record)
    return record


# ── LLM 跨文档关系发现 ──

CROSS_DOC_PROMPT = """你是一个学习知识图谱分析师。现在有多份不同学习文档中提取的知识点，需要你找出它们之间潜在的跨文档关联。

## 规则（严格遵循）

1. **不要新建、修改或删除任何知识点** — 只能使用下面列表中已有的知识点
2. **只添加跨文档的边** — 来源文档不同、且确实存在知识关联的节点之间
3. **每条边必须有明确的理由** — 不能强行连接不相关的知识点
4. **关系类型** 只能是以下之一：前置依赖、包含、关联、举例、对比

## 各文档知识点列表

以下是每个文档的知识点，按文档分组：

{grouped_nodes}

## 每个文档内部已有的关系

{internal_edges}

## 现有知识点完整名称列表（用于确认 ID）

{name_list}

## 输出格式

请找出跨文档的知识关联，按以下 JSON 格式输出（没有关联就返回空数组）：

```json
[
  {{"source": "kp_X", "target": "kp_Y", "relation": "关联", "reason": "简要说明为什么这两个知识点相关"}},
  ...
]
```

注意：source 和 target 必须是上面列表中的 id 值。最多输出 10 条最可靠的关联。
"""


async def _discover_cross_doc_edges(
    nodes: list, name_to_id: dict,
    source_titles: list, existing_edges: list
) -> list:
    """用 LLM 发现不同文档知识点之间的潜在关联"""
    from utils.llm_config import get_chat_openai

    # 按来源文档分组
    doc_groups = {}
    # 也可能是每个节点有 _source_doc 字段，或者根据边的来源
    for n in nodes:
        doc = n.get("_source_doc", "未知文档")
        doc_groups.setdefault(doc, []).append(n)

    # 格式化分组信息
    group_lines = []
    for doc, ns in doc_groups.items():
        group_lines.append(f"\n📘 {doc}:")
        for n in ns:
            nid = n.get("id", "")
            name = n.get("name", "")
            desc = (n.get("description", "") or "")[:60]
            cat = n.get("category", "")
            group_lines.append(f"  [{nid}] {name} ({cat}) - {desc}")

    # 格式化内部边
    edge_lines = []
    doc_nodes_only = {n.get("name"): n.get("id") for n in nodes}
    name_rev = {v: k for k, v in name_to_id.items()}
    for e in existing_edges:
        src_name = name_rev.get(e.get("source"), e.get("source"))
        tgt_name = name_rev.get(e.get("target"), e.get("target"))
        edge_lines.append(f"  {e.get('source')}({src_name}) --{e.get('relation','关联')}--> {e.get('target')}({tgt_name})")

    # 名字列表
    name_lines = [f"  {n.get('id')} = {n.get('name')}" for n in nodes]

    prompt = CROSS_DOC_PROMPT.format(
        grouped_nodes="\n".join(group_lines),
        internal_edges="\n".join(edge_lines) or "  (无)",
        name_list="\n".join(name_lines),
    )

    llm = get_chat_openai(temperature=0.2, max_tokens=2048)
    response = await llm.ainvoke(prompt)
    result = response.content

    # 提取 JSON
    json_str = result
    if "```json" in json_str:
        json_str = json_str.split("```json")[1].split("```")[0].strip()
    elif "```" in json_str:
        json_str = json_str.split("```")[1].split("```")[0].strip()

    try:
        edges_data = json.loads(json_str)
    except json.JSONDecodeError:
        import re
        match = re.search(r"\[[\s\S]*\]", json_str)
        if match:
            edges_data = json.loads(match.group())
        else:
            print(f"⚠️ LLM 跨文档返回无法解析:\n{result[:300]}")
            return []

    if not isinstance(edges_data, list):
        return []

    # 验证：只保留 id 真实存在的边
    valid_edges = []
    existing_ids = {n.get("id") for n in nodes}
    for e in edges_data:
        src = e.get("source", "")
        tgt = e.get("target", "")
        if src in existing_ids and tgt in existing_ids and src != tgt:
            valid_edges.append({
                "source": src,
                "target": tgt,
                "relation": e.get("relation", "关联"),
            })

    return valid_edges


def _save_graph_file(user_id: str, graph_id: str, merged_data: Dict[str, Any], record: Dict[str, Any]):
    """同步写文件 + 更新索引（在 asyncio.to_thread 中执行）"""
    user_dir = _ensure_user_dir(user_id)
    graph_path = os.path.join(user_dir, f"{graph_id}.json")
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(merged_data, f, ensure_ascii=False, indent=2)

    index = _read_index(user_id)
    index.insert(0, record)
    _write_index(user_id, index)
