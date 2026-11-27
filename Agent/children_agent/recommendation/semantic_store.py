"""
semantic_store.py - ChromaDB 语义存储（支持混合检索）

用途：
1. 题目/文档/视频 的内容向量存储 → 语义相似搜索 + BM25关键词搜索
2. 用户薄弱点模式向量存储 → 挖掘学习弱点

数据库路径: ./recommendation_data/semantic_store/
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import portalocker

# ChromaDB
try:
    import chromadb
    from chromadb.config import Settings
    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False

# BM25检索相关
try:
    from rank_bm25 import BM25Okapi
    import jieba
    _BM25_AVAILABLE = True
except ImportError:
    _BM25_AVAILABLE = False

BASE_PATH = Path("./recommendation_data/semantic_store")


class SemanticStore:
    """
    ChromaDB 向量存储封装，提供资源语义检索和薄弱点挖掘能力。
    支持混合检索（向量检索 + BM25关键词检索 + RRF融合）。
    """

    def __init__(self):
        if not _CHROMA_AVAILABLE:
            raise RuntimeError("ChromaDB 未安装，请 pip install chromadb")
        self._clients: Dict[str, chromadb.PersistentClient] = {}
        self._collections: Dict[str, Any] = {}
        self._bm25_index_cache: Dict[str, Dict] = {}
    
    def _tokenize_text(self, text: str) -> List[str]:
        """中文分词"""
        if not _BM25_AVAILABLE:
            return text.split()
        return [word for word in jieba.lcut(text) if word.strip()]
    
    def _build_bm25_index(self, collection_name: str) -> Dict:
        """构建BM25索引"""
        if not _BM25_AVAILABLE:
            return {}
        
        coll = self._get_collection(collection_name)
        page_size = 500
        offset = 0
        all_documents = []
        all_metadatas = []
        all_ids = []

        while True:
            batch = coll.get(offset=offset, limit=page_size)
            docs = batch.get('documents', [])
            if not docs:
                break

            all_documents.extend(docs)
            metas = batch.get('metadatas', [])
            if metas:
                all_metadatas.extend(metas)
            ids = batch.get('ids', [])
            if ids:
                all_ids.extend(ids)

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
            "metadatas": all_metadatas,
            "ids": all_ids
        }
    
    def _bm25_search(self, collection_name: str, query: str, limit: int = 5) -> List[Dict]:
        """BM25关键词检索"""
        if not _BM25_AVAILABLE:
            return []
        
        if collection_name not in self._bm25_index_cache:
            self._bm25_index_cache[collection_name] = self._build_bm25_index(collection_name)
        
        index = self._bm25_index_cache[collection_name]
        if not index:
            return []
        
        bm25 = index["bm25"]
        documents = index["documents"]
        metadatas = index["metadatas"]
        ids = index["ids"]
        
        query_tokens = self._tokenize_text(query)
        scores = bm25.get_scores(query_tokens)
        
        scored_items = []
        for i, score in enumerate(scores):
            if score > 0:
                scored_items.append({
                    "id": ids[i],
                    "score": round(score, 4),
                    "search_type": "bm25",
                    "metadata": metadatas[i]
                })
        
        scored_items.sort(key=lambda x: x['score'], reverse=True)
        return scored_items[:limit]
    
    def _rrf_merge(self, vector_results: List[Dict], bm25_results: List[Dict]) -> List[Dict]:
        """Reciprocal Rank Fusion 融合算法"""
        RRF_K = 60
        
        result_map = {}
        
        for rank, item in enumerate(vector_results, 1):
            item_id = item["id"]
            if item_id not in result_map:
                result_map[item_id] = {
                    "id": item_id,
                    "rrf_score": 0.0,
                    "vector_distance": item.get("distance"),
                    "bm25_score": None,
                    "search_types": [],
                    **item.get("metadata", {})
                }
            result_map[item_id]["rrf_score"] += 1.0 / (RRF_K + rank)
            result_map[item_id]["search_types"].append("vector")
        
        for rank, item in enumerate(bm25_results, 1):
            item_id = item["id"]
            if item_id not in result_map:
                result_map[item_id] = {
                    "id": item_id,
                    "rrf_score": 0.0,
                    "vector_distance": None,
                    "bm25_score": item.get("score"),
                    "search_types": [],
                    **item.get("metadata", {})
                }
            result_map[item_id]["rrf_score"] += 1.0 / (RRF_K + rank)
            result_map[item_id]["search_types"].append("bm25")
        
        merged = list(result_map.values())
        merged.sort(key=lambda x: x["rrf_score"], reverse=True)
        return merged

    def _get_lock_path(self, name: str) -> Path:
        """ChromaDB 跨进程锁文件路径"""
        lock_dir = BASE_PATH / name / ".locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        return lock_dir / "chroma.lock"

    def _get_collection(self, name: str, metadata: Dict = None):
        lock_path = self._get_lock_path(name)
        with open(lock_path, "a") as lf:
            portalocker.lock(lf, portalocker.LOCK_EX)
            try:
                if name not in self._clients:
                    path = BASE_PATH / name
                    path.mkdir(parents=True, exist_ok=True)
                    client = chromadb.PersistentClient(path=str(path))
                    self._clients[name] = client
                    self._collections[name] = client.get_or_create_collection(
                        name="default",
                        metadata=metadata or {"description": name}
                    )
            finally:
                portalocker.unlock(lf)
        return self._collections[name]

    # -------------------------------------------------------------------------
    # 题目语义搜索
    # -------------------------------------------------------------------------

    def _locked_upsert(self, collection_name: str, ids, documents, metadatas):
        """带跨进程锁的 ChromaDB upsert，防止多 worker 并发写入损坏 hnsw 索引"""
        lock_path = self._get_lock_path(collection_name)
        with open(lock_path, "a") as lf:
            portalocker.lock(lf, portalocker.LOCK_EX)
            try:
                coll = self._get_collection(collection_name)
                coll.upsert(ids=ids, documents=documents, metadatas=metadatas)
            finally:
                portalocker.unlock(lf)

    def store_question(self, qid: str, topic: str, sub_topic: str,
                       difficulty: int, knowledge_points: List[str],
                       content: str, embedding_text: str = None):
        """
        将题目存入 ChromaDB，用于语义相似题检索。
        embedding_text: 用于生成向量的文本（如题目+知识点描述）
        """
        text = embedding_text or (
            f"{topic} {sub_topic} {' '.join(knowledge_points)} {content[:500]}"
        )
        self._locked_upsert(
            "questions",
            ids=[qid],
            documents=[text],
            metadatas=[{
                "topic": topic,
                "sub_topic": sub_topic,
                "difficulty": difficulty,
                "knowledge_points": ",".join(knowledge_points),
                "stored_at": datetime.now().isoformat()
            }]
        )
        self._bm25_index_cache.pop("questions", None)

    def search_similar_questions(self, query: str, topic: str = None,
                                  difficulty: int = None,
                                  limit: int = 5) -> List[Dict]:
        """
        语义搜索相似的题目（仅向量检索，兼容旧接口）。
        """
        return self.search_hybrid_questions(query, topic, difficulty, limit, hybrid=False)
    
    def search_hybrid_questions(self, query: str, topic: str = None,
                                  difficulty: int = None,
                                  limit: int = 5, hybrid: bool = True) -> List[Dict]:
        """
        混合检索相似题目（向量检索 + BM25关键词检索 + RRF融合）。
        
        Args:
            query: 查询文本
            topic: 题目主题（过滤条件）
            difficulty: 难度（过滤条件）
            limit: 返回数量
            hybrid: 是否启用混合检索（默认True）
            
        Returns:
            检索结果列表，按RRF得分降序排列
        """
        coll = self._get_collection("questions")
        
        vector_results = []
        results = coll.query(query_texts=[query], n_results=limit * 2)
        if results and results["ids"]:
            for i, doc_id in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i]
                if topic and meta.get("topic") != topic:
                    continue
                if difficulty and meta.get("difficulty") != difficulty:
                    continue
                vector_results.append({
                    "id": doc_id,
                    "distance": results["distances"][0][i],
                    "metadata": meta
                })
        
        bm25_results = []
        if hybrid:
            raw_bm25 = self._bm25_search("questions", query, limit * 2)
            for item in raw_bm25:
                meta = item.get("metadata", {})
                if topic and meta.get("topic") != topic:
                    continue
                if difficulty and meta.get("difficulty") != difficulty:
                    continue
                bm25_results.append(item)
        
        if hybrid:
            merged = self._rrf_merge(vector_results, bm25_results)
            return merged[:limit]
        return vector_results[:limit]

    # -------------------------------------------------------------------------
    # 文档语义搜索
    # -------------------------------------------------------------------------

    def store_document(self, did: str, category: str, topic: str,
                       difficulty: int, title: str,
                       content: str, summary: str = ""):
        text = f"{title} {topic} {category} {summary[:300]} {content[:500]}"
        self._locked_upsert(
            "documents",
            ids=[did],
            documents=[text],
            metadatas=[{
                "category": category,
                "topic": topic,
                "difficulty": difficulty,
                "title": title,
                "stored_at": datetime.now().isoformat()
            }]
        )
        self._bm25_index_cache.pop("documents", None)

    def search_similar_documents(self, query: str,
                                  category: str = None,
                                  difficulty: int = None,
                                  limit: int = 5) -> List[Dict]:
        """
        语义搜索相似的文档（仅向量检索，兼容旧接口）。
        """
        return self.search_hybrid_documents(query, category, difficulty, limit, hybrid=False)
    
    def search_hybrid_documents(self, query: str,
                                  category: str = None,
                                  difficulty: int = None,
                                  limit: int = 5, hybrid: bool = True) -> List[Dict]:
        """
        混合检索相似文档（向量检索 + BM25关键词检索 + RRF融合）。
        """
        coll = self._get_collection("documents")
        
        vector_results = []
        results = coll.query(query_texts=[query], n_results=limit * 2)
        if results and results["ids"]:
            for i, doc_id in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i]
                if category and meta.get("category") != category:
                    continue
                if difficulty and meta.get("difficulty") != difficulty:
                    continue
                vector_results.append({
                    "id": doc_id,
                    "distance": results["distances"][0][i],
                    "metadata": meta
                })
        
        bm25_results = []
        if hybrid:
            raw_bm25 = self._bm25_search("documents", query, limit * 2)
            for item in raw_bm25:
                meta = item.get("metadata", {})
                if category and meta.get("category") != category:
                    continue
                if difficulty and meta.get("difficulty") != difficulty:
                    continue
                bm25_results.append(item)
        
        if hybrid:
            merged = self._rrf_merge(vector_results, bm25_results)
            return merged[:limit]
        return vector_results[:limit]

    # -------------------------------------------------------------------------
    # 视频语义搜索
    # -------------------------------------------------------------------------

    def store_video(self, vid: str, topic: str, title: str,
                    difficulty: int, knowledge_points: List[str],
                    description: str = ""):
        coll = self._get_collection("videos", {"type": "video"})
        text = f"{title} {topic} {' '.join(knowledge_points)} {description}"
        coll.upsert(
            ids=[vid],
            documents=[text],
            metadatas=[{
                "topic": topic,
                "difficulty": difficulty,
                "title": title,
                "stored_at": datetime.now().isoformat()
            }]
        )
        
        # 清除BM25索引缓存
        self._bm25_index_cache.pop("videos", None)

    def search_similar_videos(self, query: str,
                               topic: str = None,
                               difficulty: int = None,
                               limit: int = 5) -> List[Dict]:
        coll = self._get_collection("videos")
        results = coll.query(query_texts=[query], n_results=limit)
        if not results or not results["ids"]:
            return []

        items = []
        for i, vid in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]
            if topic and meta.get("topic") != topic:
                continue
            if difficulty and meta.get("difficulty") != difficulty:
                continue
            items.append({
                "id": vid,
                "distance": results["distances"][0][i],
                **meta
            })
        return items

    # -------------------------------------------------------------------------
    # 用户薄弱点模式向量
    # -------------------------------------------------------------------------

    def store_user_weakness_pattern(self, user_id: str,
                                      feature_snapshot: Dict[str, Any]):
        """
        存储用户当前薄弱点向量（由8维度特征压缩而成），
        用于后续检索"与该用户画像相似的其他用户的薄弱点"。
        """
        coll = self._get_collection("user_weakness", {"type": "user_weakness"})
        # 提取各维度得分构成文本
        dims = feature_snapshot.get("summary_scores", {}).get("dimension_scores", [])
        dim_names = ["学术背景", "学习行为", "目标动机", "认知能力",
                     "情绪状态", "社交互动", "时间管理", "创新创造"]
        text_parts = []
        for name, score in zip(dim_names, dims):
            if score < 60:
                text_parts.append(f"{name}弱({score}分)")
            elif score > 80:
                text_parts.append(f"{name}强({score}分)")
        text = " ".join(text_parts) if text_parts else "综合能力中等"

        coll.upsert(
            ids=[f"{user_id}_latest"],
            documents=[text],
            metadatas=[{
                "user_id": user_id,
                "dim_scores": ",".join(str(d) for d in dims),
                "stored_at": datetime.now().isoformat()
            }]
        )

    def find_similar_weak_users(self, user_id: str,
                                  current_weak_topics: List[str],
                                  limit: int = 10) -> List[Dict]:
        """
        找与当前用户薄弱点模式相似的其他用户，
        返回他们做过且做对的题（潜在推荐资源）。
        """
        # 从最新存储的用户薄弱点向量查询
        coll = self._get_collection("user_weakness")
        try:
            results = coll.query(
                query_texts=[" ".join(current_weak_topics)],
                where={"user_id": {"$ne": user_id}},
                n_results=limit
            )
        except Exception:
            return []
        if not results or not results["ids"]:
            return []
        return [dict(
            id=rid,
            distance=results["distances"][0][i],
            **results["metadatas"][0][i]
        ) for i, rid in enumerate(results["ids"][0])]
