"""
PPT生成子Agent
封装PPT生成流水线：大纲→配色→图片描述→背景图→视频搜索→PPTX→Markdown

包含6个子Agent + 附加功能：
  1. PPTOutlineAgent - 生成PPT大纲
  2. StyleAgent - 生成配色方案
  3. ImageDescAgent - 生成每页图片描述
  4. ImageGenAgent - 生成背景图片
  5. VideoSearchAgent - 为每页搜索真实B站视频链接
  6. PPTGenerateAgent - 合成PPTX文件（含可点击视频超链接）
  7. Markdown导出 - 供ChatAgent读取PPT内容用于上下文感知对话

输出目录:
  Agent/children_agent/PPT/ppt_create/outputs/   (PPTX文件)
  Agent/children_agent/PPT/ppt_create/ppt_images/ (背景图片)
  Agent/children_agent/PPT/ppt_create/markdown/   (Markdown文件)
"""

import os
import uuid
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path


class PPTCreationAgent:
    """PPT生成Agent - 生成专业课程讲解PPT（含视频链接与Markdown导出）"""

    def __init__(self):
        base = Path(__file__).parent / "PPT" / "ppt_create"
        self._agents_dir = base / "agents"
        self._output_dir = base / "outputs"
        self._image_dir = base / "ppt_images"
        self._markdown_dir = base / "markdown"

        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._image_dir.mkdir(parents=True, exist_ok=True)
        self._markdown_dir.mkdir(parents=True, exist_ok=True)

        api_key = self._load_api_key(base)
        self._api_key = api_key

        self._outline_agent = None
        self._style_agent = None
        self._image_desc_agent = None
        self._image_gen_agent = None
        self._video_search_agent = None
        self._ppt_gen_agent = None

    def _load_api_key(self, base: Path) -> str:
        key_file = base / "api-key.txt"
        if key_file.exists():
            return key_file.read_text().strip()
        return os.getenv("DASHSCOPE_API_KEY", "")

    async def _update_features_async(self, user_id: str, topic: str, style: str, pages: int):
        try:
            from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
            updater = DynamicFeatureUpdater()
            features = await updater.get_latest_features_async(user_id)
            if features:
                await updater.update_features_async(
                    current_features=features,
                    task_type="ppt_generation",
                    task_content=f"PPT生成: {topic}",
                    performance_data={
                        "ppt_generated": True,
                        "topic": topic,
                        "pages": pages,
                        "style": style,
                    },
                    completion_quality="good",
                    time_spent="3分钟",
                    user_id=user_id
                )
        except Exception as e:
            print(f"  ⚠️ [PPT Agent] 特征更新失败: {e}")

    def _lazy_init(self):
        if self._outline_agent is not None:
            return
        import importlib.util

        def _import_agent(filename, class_name):
            filepath = self._agents_dir / filename
            spec = importlib.util.spec_from_file_location(class_name, str(filepath))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return getattr(module, class_name)

        PPTOutlineAgent = _import_agent("Ppt_text_agent.py", "PPTOutlineAgent")
        StyleAgent = _import_agent("style_test_agent.py", "StyleAgent")
        ImageDescAgent = _import_agent("Ppt_image_agent.py", "ImageDescAgent")
        ImageGenAgent = _import_agent("image_gen_agent.py", "ImageGenAgent")
        PPTGenerateAgent = _import_agent("Ppt_create_agent.py", "PPTGenerateAgent")

        self._outline_agent = PPTOutlineAgent()
        self._style_agent = StyleAgent()
        self._image_desc_agent = ImageDescAgent()
        self._image_gen_agent = ImageGenAgent(api_key=self._api_key)
        self._ppt_gen_agent = PPTGenerateAgent()

        # ★★★ 延迟加载 VideoSearchAgent ★★★
        try:
            from Agent.children_agent.video_search_agent import VideoSearchAgent
            self._video_search_agent = VideoSearchAgent()
        except ImportError:
            print("  ⚠️ [PPT Agent] VideoSearchAgent 导入失败，视频搜索功能不可用")
            self._video_search_agent = None

    def refresh_llms(self):
        """
        刷新所有子Agent的LLM实例，绑定当前SSE callback上下文
        
        由 _wrap_node 在每个节点执行前调用，get_chat_openai() 自动
        从 contextvars 中取出 callback handler 附加到 LLM。
        """
        if self._outline_agent:
            self._outline_agent.llm = self._outline_agent._create_default_llm()
        if self._style_agent:
            self._style_agent.llm = self._style_agent._create_default_llm()
        if self._image_desc_agent:
            self._image_desc_agent.llm = self._image_desc_agent._create_default_llm()
        if self._video_search_agent:
            self._video_search_agent.llm = self._video_search_agent._initialize_llm()

    async def generate_ppt_async(
        self,
        topic: str,
        style: str = "新中式科技风",
        page_count: int = 4,
        user_id: str = "",
    ) -> Dict[str, Any]:
        """
        异步生成PPT（含视频搜索 + Markdown导出）

        流程：
          大纲 → 配色 → 图片描述 → 视频搜索 → 背景图 → PPTX(含视频链接) → Markdown
        """
        try:
            self._lazy_init()
            loop = asyncio.get_running_loop()

            print(f"\n  🚀 [PPT Agent] 开始生成: {topic} | 风格: {style}")

            # ── 1. 生成PPT大纲（异步LLM） ──
            outline_data = await self._outline_agent.generate_async(topic, style)
            if not outline_data or "pages" not in outline_data:
                return {"status": "error", "message": "大纲生成失败"}
            pages = outline_data.get("pages", [])
            print(f"  ✅ [PPT Agent] 1/6 大纲生成完成 ({len(pages)}页)")

            # ── 2. 生成配色（异步LLM） ──
            ai_colors = await self._style_agent.generate_async(topic, style)
            if not ai_colors:
                return {"status": "error", "message": "配色生成失败"}
            print("  ✅ [PPT Agent] 2/6 配色生成完成")

            # ── 3. 生成图片描述（异步LLM） ──
            enhanced_outline = await self._image_desc_agent.generate(
                topic, style, ai_colors, outline_data
            )
            if not enhanced_outline:
                return {"status": "error", "message": "图片描述生成失败"}
            print("  ✅ [PPT Agent] 3/6 图片描述生成完成")

            # 修复关键字段（ImageDescAgent 可能遗漏 type 等字段）
            for orig_page, new_page in zip(outline_data["pages"], enhanced_outline["pages"]):
                for key in ("type", "title"):
                    if key in orig_page and key not in new_page:
                        new_page[key] = orig_page[key]
                new_page["key_points"] = orig_page.get("key_points", [])
                new_page["detail_content"] = orig_page.get("detail_content", [])

            # ── 3.5 根据PPT整体主题搜索一个关联视频 ──
            pages_enhanced = enhanced_outline["pages"]
            # 使用大纲标题代替用户原始输入，搜到关联知识点视频而非"怎么做PPT"
            search_topic = outline_data.get("title", topic)
            video_data = await self._search_video_for_topic(search_topic)
            if video_data:
                enhanced_outline["video"] = video_data
            print(f"  ✅ [PPT Agent] 4/6 视频搜索完成")

            # ── 4. 生成背景图（异步并发生成） ──
            prompts = [p.get("img_desc", "simple abstract gradient background") for p in pages_enhanced]
            image_paths = await self._image_gen_agent.generate_images_async(prompts, str(self._image_dir))
            valid = [p for p in image_paths if p is not None]
            if len(valid) != len(pages_enhanced):
                print(f"  ⚠️ [PPT Agent] 图片生成不完整: {len(valid)}/{len(pages_enhanced)}，降级使用纯色背景")
                for i in range(len(image_paths)):
                    if image_paths[i] is None:
                        image_paths[i] = ""
            print("  ✅ [PPT Agent] 5/6 背景图生成完成")

            # 兜底修复
            for page in pages_enhanced:
                if "title" not in page:
                    page["title"] = "页面标题"
                if page["type"] == "cover":
                    page["subtitle"] = page.get("subtitle", "AI Powered Presentation")
                    page["sections"] = page.get("sections", [
                        {"title": "主题", "content": "核心内容展示"},
                        {"title": "亮点", "content": "关键价值呈现"},
                        {"title": "总结", "content": "整体成果展示"}
                    ])
                if "key_points" not in page:
                    page["key_points"] = []
                if "detail_content" not in page:
                    page["detail_content"] = []

            # ── 5. 合成PPTX（python-pptx 是同步库，仍需 to_thread） ──
            safe_topic = "".join(c for c in topic if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')[:60]
            short_id = uuid.uuid4().hex[:6]
            output_filename = f"{safe_topic}_{short_id}.pptx"
            output_path = str(self._output_dir / output_filename)

            final_path = await asyncio.to_thread(
                self._ppt_gen_agent.generate,
                outline_data=enhanced_outline,
                ai_colors=ai_colors,
                image_paths=image_paths,
                output_path=output_path
            )

            # ★★★ 验证生成的 PPTX 文件是否有效 ★★★
            if not self._validate_pptx(final_path):
                return {"status": "error", "message": f"PPT生成校验失败: 文件无效"}

            print(f"  ✅ [PPT Agent] 6/6 PPT合成完成: {final_path}")

            # ── 6. 导出 Markdown（供 ChatAgent 读取） ──
            markdown_filename = f"{uuid.uuid4().hex}.md"
            markdown_path = str(self._markdown_dir / markdown_filename)
            await loop.run_in_executor(None, self._export_markdown, enhanced_outline, markdown_path)
            print(f"  ✅ [PPT Agent] Markdown导出完成: {markdown_path}")

            # ── 7. 写入 MemoryHub 工作记忆（ChatAgent 自动感知） ──
            if user_id:
                try:
                    from memory import get_shared_memory_hub
                    hub = get_shared_memory_hub()
                    md_content = await loop.run_in_executor(None, lambda: open(markdown_path, encoding="utf-8").read())
                    summary = md_content[:2000] + ("..." if len(md_content) > 2000 else md_content)
                    hub.working.set_last_generated(
                        user_id=user_id,
                        resource_type="ppt",
                        resource_id=output_filename,
                        summary=summary,
                    )
                    print(f"  ✅ [PPT Agent] MemoryHub 工作记忆写入完成")
                except Exception as e:
                    print(f"  ⚠️ [PPT Agent] MemoryHub 写入失败: {e}")

            # 特征更新由上层 Conduct 层负责，不在此处重复触发
            # asyncio.create_task(self._update_features_async(user_id, topic, style, len(pages_enhanced)))

            # ★★★ 将生成的PPT自动入库（供推荐系统使用）★★★
            try:
                from Agent.children_agent.recommendation.resource_db import ResourceDB
                from Agent.children_agent.recommendation.semantic_store import SemanticStore
                import hashlib
                uid = user_id or "unknown"
                ppt_topic = topic
                ppt_title = f"PPT：{ppt_topic}"
                pid = f"ppt_{hashlib.md5(f'{uid}_{ppt_topic}'.encode()).hexdigest()[:12]}"
                md_content = (await loop.run_in_executor(
                    None, lambda: Path(markdown_path).read_text(encoding="utf-8"))
                ) if markdown_path else ""
                summary = md_content[:300] if md_content else f"PPT演示：{ppt_topic}，共{len(pages_enhanced)}页"
                # ★★★ 所有DB操作放在同一个线程中执行，避免跨线程锁冲突 ★★★
                def _do_ppt_import():
                    _rdb = ResourceDB()
                    _sem = SemanticStore()
                    _rdb.upsert_document(
                        did=pid, category="ppt",
                        title=ppt_title, topic=ppt_topic,
                        difficulty=3, knowledge_points=[ppt_topic],
                        content=md_content, summary=summary,
                        metadata={
                            "user_id": uid,
                            "filename": output_filename,
                            "filepath": final_path,
                            "style": style,
                            "pages": len(pages_enhanced),
                        }
                    )
                    _sem.store_document(
                        did=pid, category="ppt",
                        topic=ppt_topic, difficulty=3,
                        title=ppt_title, content=md_content,
                        summary=summary
                    )
                await loop.run_in_executor(None, _do_ppt_import)
                print(f"   ✅ PPT已入库")
            except Exception as e:
                print(f"   ⚠️ PPT入库失败（不影响使用）: {e}")

            return {
                "status": "success",
                "filename": output_filename,
                "filepath": final_path,
                "markdown_filename": markdown_filename,
                "markdown_path": markdown_path,
                "topic": topic,
                "style": style,
                "pages": len(pages_enhanced),
                "message": f"PPT「{topic}」已生成！共{len(pages_enhanced)}页，含视频链接与Markdown",
            }

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": f"PPT生成失败: {str(e)}"}

    # ════════════════════════════════════════════════════════════
    # 视频搜索
    # ════════════════════════════════════════════════════════════

    async def _search_video_for_topic(self, topic: str) -> Optional[Dict]:
        """根据PPT整体主题搜索一个关联B站视频"""
        if not self._video_search_agent or not topic:
            return None
        try:
            result = await asyncio.wait_for(
                self._video_search_agent.search_videos_for_question_async(
                    user_question=topic,
                    top_k=1,
                    raw_query=True,
                ),
                timeout=10.0,
            )
            videos = result.get("videos", [])
            if not videos:
                return None
            v = videos[0]
            video_data = {
                "title": v.get("title", ""),
                "url": v.get("url", ""),
                "author": v.get("author", ""),
                "duration": v.get("duration", ""),
                "bvid": v.get("bvid", ""),
            }
            print(f"    📺 [{topic}] → {video_data['title']}")
            return video_data
        except asyncio.TimeoutError:
            print(f"    ⏰ [{topic}] 视频搜索超时")
            return None
        except Exception as e:
            print(f"    ⚠️ [{topic}] 视频搜索失败: {e}")
            return None

    # ════════════════════════════════════════════════════════════
    # Markdown 导出（供 ChatAgent 读取）
    # ════════════════════════════════════════════════════════════

    @staticmethod
    def _export_markdown(outline_data: Dict, output_path: str):
        """
        将PPT大纲 + 视频链接导出为Markdown格式。
        结构类似微软 PPT → Markdown 导出风格：
          - 文件头含参考视频链接
          - 封面 → 一级标题 + 摘要
          - 内容页 → 二级标题 + 要点 + 详情
        """
        lines = []
        total_pages = len(outline_data.get("pages", []))

        # ── 文件头 ──
        lines.append(f"# {outline_data.get('title', 'PPT 演示文稿')}")
        lines.append("")
        lines.append(f"> 共 {total_pages} 页")
        lines.append("")

        # ── 全局参考视频（基于PPT整体主题） ──
        video = outline_data.get("video")
        if video:
            vtitle = video.get("title", "参考视频")
            vurl = video.get("url", "")
            vauthor = video.get("author", "")
            vdur = video.get("duration", "")
            meta_parts = []
            if vauthor:
                meta_parts.append(f"UP主：{vauthor}")
            if vdur:
                meta_parts.append(f"时长：{vdur}")
            meta = " | ".join(meta_parts)
            lines.append("")
            if vurl:
                lines.append(f"> 📺 关联视频：[{vtitle}]({vurl})")
            else:
                lines.append(f"> 📺 关联视频：{vtitle}")
            if meta:
                lines.append(f"> {meta}")
            lines.append("")

        lines.append("---")
        lines.append("")

        for idx, page in enumerate(outline_data.get("pages", []), 1):
            page_type = page.get("type", "content")
            title = page.get("title", f"第{idx}页")

            # ── 页面标题 ──
            if page_type == "cover":
                lines.append(f"## 封面：{title}")
            elif page_type == "summary":
                lines.append(f"## 总结：{title}")
            else:
                lines.append(f"## 第 {idx} 页：{title}")

            lines.append("")

            # ── 封面副标题 ──
            if page_type == "cover" and page.get("subtitle"):
                lines.append(f"**{page['subtitle']}**")
                lines.append("")

            # ── 封面板块 ──
            if page_type == "cover" and page.get("sections"):
                for sec in page["sections"]:
                    lines.append(f"- **{sec.get('title', '')}**：{sec.get('content', '')}")
                lines.append("")

            # ── 要点与详情 ──
            key_points = page.get("key_points", [])
            details = page.get("detail_content", [])
            for i, kp in enumerate(key_points):
                lines.append(f"- {kp}")
                if i < len(details) and details[i]:
                    lines.append(f"  - {details[i]}")
            if key_points:
                lines.append("")

            lines.append("---")
            lines.append("")

        # 写入文件
        content = "\n".join(lines)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

    # ════════════════════════════════════════════════════════════
    # 校验
    # ════════════════════════════════════════════════════════════

    @staticmethod
    def _validate_pptx(filepath: str) -> bool:
        """验证 PPTX 文件是否为有效的 zip 存档（PPTX 本质是 ZIP）"""
        import zipfile
        try:
            if not filepath or not os.path.exists(filepath):
                return False
            size = os.path.getsize(filepath)
            if size < 1024:
                print(f"  ❌ [PPT Agent] 文件过小: {size} bytes")
                return False
            with zipfile.ZipFile(filepath, 'r') as zf:
                names = zf.namelist()
                if '[Content_Types].xml' not in names:
                    print(f"  ❌ [PPT Agent] 缺少 [Content_Types].xml")
                    return False
            return True
        except Exception as e:
            print(f"  ❌ [PPT Agent] PPTX 校验失败: {e}")
            return False
