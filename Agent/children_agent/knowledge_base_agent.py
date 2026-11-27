"""
知识库Agent - RAG检索增强生成系统

功能：
1. 导入学习资料（PDF、Markdown、Word等）
2. 文本分块和向量化
3. 存储到ChromaDB向量数据库
4. 检索相关文档片段
5. 基于检索结果生成答案

使用示例：
    import asyncio
    from Agent.children_agent.knowledge_base_agent import KnowledgeBaseAgent
    
    async def main():
        kb = KnowledgeBaseAgent()
        
        # 导入文档（异步）
        await kb.import_documents(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "数据结构"),
            user_id="user_001"
        )
        
        # 问答（异步）
        result = await kb.query_knowledge(
            question="什么是线性表？",
            user_id="user_001"
        )
        print(result["answer"])
    
    asyncio.run(main())
"""

import os
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from utils.async_llm_caller import call_llm_with_retry

# TTS辅助函数
try:
    from utils.tts_helper import generate_tts_audio
except ImportError:
    from utils.tts_helper import generate_tts_audio

try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    raise ImportError("请安装 chromadb: pip install chromadb")

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
    except ImportError:
        raise ImportError("请安装 langchain: pip install langchain langchain-text-splitters")

# BM25检索相关
try:
    from rank_bm25 import BM25Okapi
    import jieba
    _BM25_AVAILABLE = True
except ImportError:
    _BM25_AVAILABLE = False
    print("⚠️ BM25检索依赖未安装，请执行: pip install rank-bm25 jieba")


class KnowledgeBaseAgent:
    """知识库Agent - RAG系统核心"""
    
    def __init__(self, 
                 storage_path: str = "./memory/knowledge_base_db",
                 chunk_size: int = 500,
                 chunk_overlap: int = 50,
                 top_k: int = 5):
        """
        初始化知识库Agent
        
        Args:
            storage_path: ChromaDB存储路径
            chunk_size: 文本分块大小
            chunk_overlap: 分块重叠大小
            top_k: 检索返回的Top-K文档数量
        """
        self.storage_path = storage_path
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.top_k = top_k
        
        # 创建存储目录
        Path(storage_path).mkdir(parents=True, exist_ok=True)
        
        # 初始化ChromaDB客户端
        self.client = chromadb.PersistentClient(path=storage_path)
        
        # 文本分割器
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
        )
        
        # BM25索引缓存（按user_id存储）
        self._bm25_index_cache: Dict[str, Dict] = {}
        
        # 初始化LLM客户端
        self._initialize_llm()
        
        print(f"✅ KnowledgeBaseAgent 初始化完成")
        print(f"   存储路径: {storage_path}")
        print(f"   分块大小: {chunk_size}")
        print(f"   检索Top-K: {top_k}")
        print(f"   BM25检索: {'✅ 可用' if _BM25_AVAILABLE else '⚠️ 不可用'}")
    
    def _initialize_llm(self):
        """初始化LLM客户端"""
        try:
            from utils.llm_config import get_chat_openai, MODEL

            self.llm = get_chat_openai(temperature=0.3, max_tokens=2000)
            self.model = MODEL
            
            print(f"✅ LLM客户端初始化完成: {self.model}")
            
        except Exception as e:
            print(f"❌ LLM客户端初始化失败: {e}")
            raise
    
    async def _get_user_collection(self, user_id: str):
        """
        获取或创建用户专属的知识库collection（异步，线程池）
        
        Args:
            user_id: 用户ID
            
        Returns:
            ChromaDB Collection
        """
        collection_name = f"kb_{user_id}"

        def _get_or_create():
            try:
                return self.client.get_collection(name=collection_name), True
            except Exception:
                return self.client.create_collection(
                    name=collection_name,
                    metadata={
                        "description": f"用户 {user_id} 的知识库",
                        "user_id": user_id
                    }
                ), False

        collection, existed = await asyncio.to_thread(_get_or_create)
        if existed:
            print(f"✅ 加载用户 {user_id} 的知识库")
        else:
            print(f"✅ 为用户 {user_id} 创建新知识库")
        return collection
    
    async def _read_pdf(self, file_path: str) -> str:
        """读取PDF文件（异步，线程池）"""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            print("⚠️ 未安装 PyMuPDF，请使用: pip install pymupdf")
            return ""

        try:
            def _read():
                doc = fitz.open(file_path)
                text = ""
                for page in doc:
                    text += page.get_text()
                doc.close()
                return text

            text = await asyncio.to_thread(_read)
            print(f"✅ 读取PDF: {Path(file_path).name} ({len(text)} 字符)")
            return text

        except Exception as e:
            print(f"❌ 读取PDF失败: {e}")
            return ""
    
    async def _read_markdown(self, file_path: str) -> str:
        """读取Markdown文件（异步，线程池）"""
        try:
            def _read():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()

            text = await asyncio.to_thread(_read)
            print(f"✅ 读取Markdown: {Path(file_path).name} ({len(text)} 字符)")
            return text

        except Exception as e:
            print(f"❌ 读取Markdown失败: {e}")
            return ""
    
    async def _read_word(self, file_path: str) -> str:
        """读取Word文件（异步，线程池）"""
        try:
            from docx import Document
        except ImportError:
            print("⚠️ 未安装 python-docx，请使用: pip install python-docx")
            return ""

        try:
            def _read():
                doc = Document(file_path)
                return "\n".join([para.text for para in doc.paragraphs])

            text = await asyncio.to_thread(_read)
            print(f"✅ 读取Word: {Path(file_path).name} ({len(text)} 字符)")
            return text

        except Exception as e:
            print(f"❌ 读取Word失败: {e}")
            return ""
    
    async def _read_xmind(self, file_path: str) -> str:
        """读取XMind思维导图文件（异步，线程池）"""
        try:
            import zipfile
            import xml.etree.ElementTree as ET
        except ImportError:
            return ""

        try:
            def _read():
                # XMind文件本质是ZIP压缩包
                with zipfile.ZipFile(file_path, 'r') as z:
                    if 'content.xml' in z.namelist():
                        with z.open('content.xml') as f:
                            tree = ET.parse(f)
                            root = tree.getroot()
                            texts = []
                            for elem in root.iter():
                                if elem.text and elem.text.strip():
                                    texts.append(elem.text.strip())
                            return "\n".join(texts)
                return ""

            text = await asyncio.to_thread(_read)
            if text:
                print(f"✅ 读取XMind: {Path(file_path).name} ({len(text)} 字符)")
            return text

        except Exception as e:
            print(f"❌ 读取XMind失败: {e}")
            return ""
    
    async def _split_and_chunk(self, text: str, source: str) -> List[Dict[str, Any]]:
        """
        将文本分块（异步，线程池 - CPU密集型分块操作）
        
        Args:
            text: 原始文本
            source: 来源文件名
            
        Returns:
            分块列表，每个元素包含 {text, metadata}
        """
        def _split():
            chunks = self.text_splitter.split_text(text)
            chunk_docs = []
            for i, chunk in enumerate(chunks):
                chunk_docs.append({
                    "text": chunk,
                    "metadata": {
                        "source": source,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "timestamp": datetime.now().isoformat()
                    }
                })
            return chunk_docs

        chunk_docs = await asyncio.to_thread(_split)
        print(f"✅ 文本分块完成: {len(chunk_docs)} 个片段")
        return chunk_docs
    
    async def import_documents(self, directory: str, user_id: str) -> Dict[str, Any]:
        """
        导入目录下的所有文档到知识库（异步，线程池）
        
        Args:
            directory: 文档目录路径
            user_id: 用户ID
            
        Returns:
            导入结果
        """
        print(f"\n📚 开始导入文档到知识库...")
        print(f"   目录: {directory}")
        print(f"   用户: {user_id}")
        
        dir_path = Path(directory)
        if not dir_path.exists():
            return {
                "status": "error",
                "message": f"目录不存在: {directory}"
            }
        
        # 获取用户专属collection（异步）
        collection = await self._get_user_collection(user_id)
        
        # 统计信息
        total_files = 0
        success_files = 0
        total_chunks = 0
        
        # 遍历目录下的所有文件
        for file_path in dir_path.iterdir():
            if not file_path.is_file():
                continue
            
            total_files += 1
            file_ext = file_path.suffix.lower()
            
            # 根据文件类型读取（异步）
            text = ""
            if file_ext == '.pdf':
                text = await self._read_pdf(str(file_path))
            elif file_ext in ['.md', '.markdown']:
                text = await self._read_markdown(str(file_path))
            elif file_ext in ['.docx', '.doc']:
                text = await self._read_word(str(file_path))
            elif file_ext == '.xmind':
                text = await self._read_xmind(str(file_path))
            else:
                print(f"⚠️ 跳过不支持的文件格式: {file_path.name}")
                continue
            
            if not text:
                continue
            
            # 分块（异步，CPU密集型）
            chunks = await self._split_and_chunk(text, file_path.name)
            
            # 存储到ChromaDB（异步，线程池）
            if chunks:
                ids = [f"{user_id}_{file_path.stem}_{i}" for i in range(len(chunks))]
                documents = [chunk["text"] for chunk in chunks]
                metadatas = [chunk["metadata"] for chunk in chunks]
                
                def _upsert():
                    collection.upsert(
                        ids=ids,
                        documents=documents,
                        metadatas=metadatas
                    )
                await asyncio.to_thread(_upsert)
                
                success_files += 1
                total_chunks += len(chunks)
                print(f"✅ 已导入: {file_path.name} ({len(chunks)} 个片段)")
        
        result = {
            "status": "success",
            "total_files": total_files,
            "success_files": success_files,
            "total_chunks": total_chunks,
            "message": f"成功导入 {success_files}/{total_files} 个文件，共 {total_chunks} 个片段"
        }
        
        # 清除BM25索引缓存（新文档导入后需重新构建索引）
        collection_name = f"kb_{user_id}"
        self._bm25_index_cache.pop(collection_name, None)
        print(f"   📦 已清除用户 {user_id} 的BM25索引缓存")
        
        print(f"\n✅ 文档导入完成: {result['message']}")
        return result
    
    async def query_knowledge(self, question: str, user_id: str, enable_tts: bool = False, 
                             context_truncate_length: int = 500) -> Dict[str, Any]:
        """
        基于知识库回答问题（RAG）- ★★★ 混合检索版本 ★★★
        
        Args:
            question: 用户问题
            user_id: 用户ID
            enable_tts: 是否启用TTS语音合成
            context_truncate_length: 上下文片段截断长度，默认500字符
            
        Returns:
            回答结果，包含答案和引用的文档片段
        """
        print(f"\n🔍 开始混合检索知识库...")
        print(f"   问题: {question}")
        print(f"   用户: {user_id}")
        print(f"   上下文截断长度: {context_truncate_length}")
        
        # 获取用户专属collection（异步）
        collection = await self._get_user_collection(user_id)
        
        # ★★★ 第一步：BM25关键词检索 ★★★
        print(f"   📝 执行BM25关键词检索...")
        keyword_docs = await self._keyword_based_search(collection, question)
        print(f"   ✅ BM25检索得到 {len(keyword_docs)} 个相关片段")
        
        # ★★★ 第二步：向量检索 ★★★
        print(f"   📝 执行向量检索...")
        vector_docs = await self._vector_based_search(collection, question)
        print(f"   ✅ 向量检索得到 {len(vector_docs)} 个相关片段")
        
        # ★★★ 第三步：RRF融合合并 ★★★
        all_docs = self._merge_and_deduplicate(keyword_docs, vector_docs)
        print(f"   ✅ RRF融合后共 {len(all_docs)} 个唯一片段")
        
        if not all_docs:
            return {
                "status": "no_result",
                "message": "知识库中没有找到相关内容",
                "answer": "抱歉，我在知识库中没有找到与您的问题相关的内容。您可以尝试上传更多学习资料，或者换一种问法。"
            }
        
        # ★★★ 第四步：构建上下文 ★★★
        context_parts = []
        for i, doc in enumerate(all_docs[:self.top_k], 1):
            content = doc['content']
            if len(content) > context_truncate_length:
                preview = content[:context_truncate_length] + "..."
            else:
                preview = content
            context_parts.append(f"[参考资料{i} - 来源: {doc['source']}]\n{preview}")
            print(f"   [片段{i}] 来源: {doc['source']} | RRF得分: {doc.get('rrf_score', 0):.4f}")
        
        context = "\n\n".join(context_parts)
        
        # ★★★ 第五步：生成答案 ★★★
        answer = await self._generate_answer(question, context)
        
        result = {
            "status": "success",
            "question": question,
            "answer": answer,
            "retrieved_docs": all_docs[:self.top_k],
            "doc_count": len(all_docs[:self.top_k]),
            "method": "hybrid_search"
        }
        
        # TTS语音合成（可选）- 将答案转为语音
        if enable_tts and answer:
            tts_path = await generate_tts_audio(
                text=answer,
                agent_name="knowledge_base",
                user_id=user_id
            )
            if tts_path:
                result["tts_audio_path"] = tts_path
        
        print(f"✅ 答案生成完成")
        return result
    
    def _tokenize_text(self, text: str) -> List[str]:
        """中文分词（使用jieba）"""
        if not _BM25_AVAILABLE:
            return text.split()
        return [word for word in jieba.lcut(text) if word.strip()]
    
    async def _build_bm25_index(self, collection) -> Dict:
        """构建BM25索引（异步，线程池 - CPU密集型+IO）"""
        if not _BM25_AVAILABLE:
            return {}

        def _build():
            page_size = 500
            offset = 0
            all_documents = []
            all_metadatas = []

            while True:
                batch = collection.get(offset=offset, limit=page_size)
                docs = batch.get('documents', [])
                if not docs:
                    break

                all_documents.extend(docs)
                metas = batch.get('metadatas', [])
                if metas:
                    all_metadatas.extend(metas)

                if len(docs) < page_size:
                    break
                offset += page_size

            if not all_documents:
                return {}

            tokenized_docs = [self._tokenize_text(doc) for doc in all_documents]
            bm25 = BM25Okapi(tokenized_docs)

            return {
                "bm25": bm25,
                "documents": all_documents,
                "metadatas": all_metadatas
            }

        return await asyncio.to_thread(_build)
    
    async def _keyword_based_search(self, collection, question: str) -> List[Dict]:
        """
        ★★★ BM25关键词检索：使用rank_bm25+jieba实现真正的关键词匹配 ★★★
        """
        try:
            if not _BM25_AVAILABLE:
                print("   ⚠️ BM25不可用，回退到简单关键词匹配")
                return await self._fallback_keyword_search(collection, question)
            
            collection_name = collection.name if hasattr(collection, 'name') else 'default'
            
            if collection_name not in self._bm25_index_cache:
                print(f"   📦 首次检索，构建BM25索引...")
                self._bm25_index_cache[collection_name] = await self._build_bm25_index(collection)
            
            index = self._bm25_index_cache[collection_name]
            if not index:
                return []
            
            bm25 = index["bm25"]
            documents = index["documents"]
            metadatas = index["metadatas"]
            
            query_tokens = self._tokenize_text(question)
            scores = bm25.get_scores(query_tokens)
            
            scored_docs = []
            for i, score in enumerate(scores):
                if score > 0:
                    scored_docs.append({
                        "content": documents[i],
                        "source": metadatas[i].get('source', 'unknown'),
                        "chunk_index": metadatas[i].get('chunk_index', 0),
                        "keyword_score": round(score, 4),
                        "search_type": "keyword"
                    })
            
            scored_docs.sort(key=lambda x: x['keyword_score'], reverse=True)
            
            print(f"      BM25检索完成，最高得分: {scored_docs[0]['keyword_score'] if scored_docs else 0}")
            
            return scored_docs[:self.top_k * 2]
            
        except Exception as e:
            print(f"   ⚠️ BM25检索失败: {e}，回退到简单匹配")
            return await self._fallback_keyword_search(collection, question)
    
    async def _fallback_keyword_search(self, collection, question: str) -> List[Dict]:
        """
        回退关键词检索：当BM25不可用时使用简单子串匹配（异步，线程池）
        """
        try:
            def _get():
                return collection.get(limit=500)
            all_docs = await asyncio.to_thread(_get)
            
            matched_docs = []
            for doc_content, metadata in zip(all_docs['documents'], all_docs['metadatas']):
                score = sum(1 for kw in question.split() if kw in doc_content)
                if score > 0:
                    matched_docs.append({
                        "content": doc_content,
                        "source": metadata.get('source', 'unknown'),
                        "chunk_index": metadata.get('chunk_index', 0),
                        "keyword_score": score,
                        "search_type": "keyword"
                    })
            
            matched_docs.sort(key=lambda x: x['keyword_score'], reverse=True)
            return matched_docs[:self.top_k * 2]
            
        except Exception as e:
            print(f"   ⚠️ 回退关键词检索失败: {e}")
            return []
    
    async def _vector_based_search(self, collection, question: str,
                                      distance_threshold: float = 1.0) -> List[Dict]:
        """
        ★★★ 向量检索：作为补充，带相关性阈值过滤 ★★★
                     （异步，线程池 - ChromaDB远程调用）

        Args:
            collection: ChromaDB collection
            question: 查询问题
            distance_threshold: 距离阈值，大于此值的结果视为不相关并丢弃
                                （距离越小越相关，默认 1.0）
        """
        try:
            def _query():
                return collection.query(
                    query_texts=[question],
                    n_results=min(self.top_k * 2, 10),
                    include=["documents", "metadatas", "distances"]
                )

            results = await asyncio.to_thread(_query)

            vector_docs = []
            if results['documents'] and results['documents'][0]:
                distances = results.get('distances', [[]])[0] if results.get('distances') else []
                for i, doc in enumerate(results['documents'][0]):
                    dist = distances[i] if i < len(distances) else 999
                    # ★★★ 过滤掉距离过大的噪音结果 ★★★
                    if dist > distance_threshold:
                        continue
                    vector_docs.append({
                        "content": doc,
                        "source": results['metadatas'][0][i].get('source', 'unknown'),
                        "chunk_index": results['metadatas'][0][i].get('chunk_index', 0),
                        "search_type": "vector",
                        "distance": round(dist, 4)
                    })

            filtered = min(self.top_k * 2, 10) - len(vector_docs)
            if filtered > 0:
                print(f"   🚫 向量检索过滤掉 {filtered} 个低相关结果（distance > {distance_threshold}）")

            return vector_docs

        except Exception as e:
            print(f"   ⚠️ 向量检索失败: {e}")
            return []
    
    def _merge_and_deduplicate(self, keyword_docs: List[Dict], vector_docs: List[Dict]) -> List[Dict]:
        """
        ★★★ Reciprocal Rank Fusion (RRF) 合并算法 ★★★
        
        将关键词检索（BM25）和向量检索的结果融合，利用排名信息计算最终得分。
        
        RRF公式: score(d) = Σ(1 / (k + rank(d_i)))
        其中 k 是平滑常数，通常取 60；rank(d_i) 是文档在第i个检索系统中的排名
        
        Args:
            keyword_docs: BM25检索结果（已按得分降序排列）
            vector_docs: 向量检索结果（已按距离升序排列）
            
        Returns:
            融合后的文档列表，按RRF得分降序排列
        """
        RRF_K = 60
        
        doc_map = {}
        
        for rank, doc in enumerate(keyword_docs, 1):
            doc_id = f"{doc['source']}_{doc['chunk_index']}"
            if doc_id not in doc_map:
                doc_map[doc_id] = {
                    "content": doc["content"],
                    "source": doc["source"],
                    "chunk_index": doc["chunk_index"],
                    "search_type": doc.get("search_type", "mixed"),
                    "keyword_score": doc.get("keyword_score", 0),
                    "distance": doc.get("distance", None),
                    "rrf_score": 0.0
                }
            doc_map[doc_id]["rrf_score"] += 1.0 / (RRF_K + rank)
        
        for rank, doc in enumerate(vector_docs, 1):
            doc_id = f"{doc['source']}_{doc['chunk_index']}"
            if doc_id not in doc_map:
                doc_map[doc_id] = {
                    "content": doc["content"],
                    "source": doc["source"],
                    "chunk_index": doc["chunk_index"],
                    "search_type": doc.get("search_type", "mixed"),
                    "keyword_score": doc.get("keyword_score", None),
                    "distance": doc.get("distance", 0),
                    "rrf_score": 0.0
                }
            doc_map[doc_id]["rrf_score"] += 1.0 / (RRF_K + rank)
        
        merged_docs = list(doc_map.values())
        merged_docs.sort(key=lambda x: x["rrf_score"], reverse=True)
        
        print(f"   ✅ RRF融合完成，最高得分: {merged_docs[0]['rrf_score'] if merged_docs else 0}")
        
        return merged_docs
    
    async def _generate_answer(self, question: str, context: str) -> str:
        """
        基于检索结果生成答案（含防幻觉校验）
        
        Args:
            question: 用户问题
            context: 检索到的文档上下文
            
        Returns:
            生成的答案
        """
        prompt = f"""你是一个专业的教学助手，请**严格基于以下检索到的知识库内容**来回答学生的问题。

【检索到的相关知识】
{context}

【学生问题】
{question}

【重要要求 - 必须遵守】
1. **必须使用上述检索到的知识**来回答问题，不要说"知识库中没有相关信息"
2. 如果检索内容与问题相关，就基于这些内容组织答案
3. 回答要清晰、准确、易懂，适合学生学习
4. 可以引用具体的文档来源（如"根据数据结构.md中的内容..."）
5. 如果知识点复杂，可以用例子或类比帮助理解
6. **禁止编造信息**，只能使用检索到的内容
7. 如果检索内容确实与问题完全无关，才说明"这个问题在知识库中没有找到相关内容"

请直接给出你的回答：
"""
        
        try:
            response = await call_llm_with_retry(self.llm, prompt, error_msg="知识库Agent答案生成LLM调用")
            answer = response.content if hasattr(response, 'content') else str(response)
            
            answer = await self._check_hallucination(answer, context)
            
            return answer
            
        except Exception as e:
            print(f"❌ 答案生成失败: {e}")
            return f"抱歉，生成答案时出现错误: {str(e)}"
    
    async def _check_hallucination(self, answer: str, context: str) -> str:
        """
        防幻觉校验 - 验证答案与知识库内容的一致性
        
        Args:
            answer: LLM生成的答案
            context: 检索到的知识库上下文
            
        Returns:
            校验后的答案（可能被修正）
        """
        try:
            from utils.hallucination_guard import get_hallucination_guard
            
            guard = get_hallucination_guard(strict_mode=False, llm_client=self.llm)
            result, check_result = await guard.validate_and_correct(answer, context)
            
            if check_result.warnings:
                print(f"⚠️ [防幻觉] 检测到警告: {check_result.warnings}")
                print(f"   事实准确率: {check_result.fact_accuracy * 100:.1f}%")
                
            if check_result.confidence.value == "low":
                print(f"⚠️ [防幻觉] 置信度低，建议重新生成")
                
            return result
            
        except ImportError:
            print("⚠️ 防幻觉模块未安装，跳过校验")
            return answer
        except Exception as e:
            print(f"⚠️ 防幻觉校验失败: {e}")
            return answer
    
    async def get_knowledge_stats(self, user_id: str) -> Dict[str, Any]:
        """
        获取知识库统计信息（异步，线程池）
        
        Args:
            user_id: 用户ID
            
        Returns:
            统计信息
        """
        collection = await self._get_user_collection(user_id)
        
        def _count():
            return collection.count()
        count = await asyncio.to_thread(_count)
        
        return {
            "status": "success",
            "user_id": user_id,
            "total_chunks": count,
            "message": f"知识库中共有 {count} 个文档片段"
        }
