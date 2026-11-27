"""
视频排序器
对搜索结果进行质量评分和相关性排序
"""

from typing import List, Dict, Any
import re


class VideoRanker:
    """视频质量排序器"""

    def __init__(self):
        self.weights = {
            'relevance': 0.2,      # 相关性权重（降低，确保只要沾边就行）
            'quality': 0.6,        # 质量权重（大幅提高，以播放量为核心）
            'recency': 0.1,        # 时效性权重
            'engagement': 0.1      # 互动度权重
        }

    def _tokenize_query(self, query: str) -> List[str]:
        """
        智能分词：将查询字符串拆分成有意义的关键词

        Args:
            query: 原始查询字符串

        Returns:
            分词后的列表（包含原文词 + 中文二元分词）
        """
        words = re.findall(r'[a-zA-Z0-9]+|[\u4e00-\u9fff]+', query.lower())

        tokens = []
        for word in words:
            if re.match(r'^[a-zA-Z0-9]+$', word):
                if word.strip():
                    tokens.append(word)
            else:
                # ★★★ 中文词：保留整体 + 生成相邻二元组（bigram）
                # 例如 "数据结构教程" → ["数据结构教程", "数据", "据结", "结构", "构教", "教程"]
                # 这样 "数据结构教程" 能匹配到 "数据结构与算法" 中的 "数据" 和 "结构" ★★★
                if word.strip():
                    tokens.append(word)
                    if len(word) >= 4:
                        for i in range(len(word) - 1):
                            bigram = word[i:i+2]
                            if bigram.strip():
                                tokens.append(bigram)

        # 去重但保持顺序
        seen = set()
        unique_tokens = []
        for token in tokens:
            if token not in seen and len(token.strip()) > 0:
                seen.add(token)
                unique_tokens.append(token)

        return unique_tokens

    def rank_videos(self, videos: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """
        对视频列表进行排序：基于强相关性过滤，再按播放量排名
        
        Args:
            videos: 原始视频列表
            query: 搜索查询词
            
        Returns:
            排序后的视频列表（已按播放量降序）
        """
        scored_videos = []
        filtered_count = 0
        
        # 打印查询词和分词结果
        query_words = self._tokenize_query(query)
        print(f"   🔍 查询词: '{query}'")
        print(f"   📝 分词结果: {query_words}")
        
        for idx, video in enumerate(videos):
            # 1. 计算相关性分数
            relevance = self._calc_relevance(video, query)
            
            # 2. 强相关性过滤：只有相关性达到阈值才保留
            # ★★★ 词组级匹配阈值从0.25降到0.15，因为不再拆单字后匹配更严格 ★★★
            if relevance >= 0.15:
                video_with_score = video.copy()
                video_with_score['relevance_score'] = round(relevance, 2)
                video_with_score['quality_score'] = round(self._calc_quality(video), 2)
                scored_videos.append(video_with_score)
                print(f"   ✅ 保留视频 {idx+1}: {video.get('title', '')[:40]}... (相关性: {relevance:.2f})")
            else:
                filtered_count += 1
                # 只显示前5个被过滤的，避免日志过多
                if filtered_count <= 5:
                    title = video.get('title', '')[:40]
                    desc = video.get('description', '')[:30]
                    print(f"   ⚠️ 过滤视频 {idx+1}: {title}... (相关性: {relevance:.2f}, 描述: {desc})")
        
        if filtered_count > 5:
            print(f"   ... 还有 {filtered_count - 5} 个视频被过滤")
        
        print(f"   📊 统计: 原始={len(videos)}, 保留={len(scored_videos)}, 过滤={filtered_count}")
        
        # 3. 核心排序：主要按播放量降序排列
        # 如果播放量相同，则相关性更高的排在前面
        scored_videos.sort(key=lambda x: (x.get('play_count', 0), x.get('relevance_score', 0)), reverse=True)
        
        return scored_videos

    def _calculate_score(self, video: Dict[str, Any], query: str) -> float:
        """计算视频综合分数"""
        relevance = self._calc_relevance(video, query)
        quality = self._calc_quality(video)
        recency = self._calc_recency(video)
        engagement = self._calc_engagement(video)
        
        total_score = (
            relevance * self.weights['relevance'] +
            quality * self.weights['quality'] +
            recency * self.weights['recency'] +
            engagement * self.weights['engagement']
        )
        
        return min(total_score, 1.0)

    def _calc_relevance(self, video: Dict, query: str) -> float:
        """
        计算相关性分数
        
        策略：精确匹配 → 分词精确匹配 → 模糊匹配（SequenceMatcher）三级递进。
        模糊匹配用 find_longest_match 找标题中和查询词最长的公共子串，
        解决 "数据结构教程" vs "数据结构与算法" 这类措辞不同但高度相关的情况。
        """
        import difflib

        title = (video.get('title', '') or '').lower()
        description = (video.get('description', '') or '').lower()
        query_lower = query.lower()

        score = 0.0
        debug_info = []
        query_words = self._tokenize_query(query)

        # ── 标题匹配 ──

        # 1. 完全匹配（最强信号）
        if query_lower in title:
            score += 0.5
            debug_info.append(f"标题完全匹配(+0.5)")

        if query_words:
            # 2. 精确分词匹配
            exact_matched = [w for w in query_words if w in title]
            if exact_matched:
                ratio = len(exact_matched) / len(query_words)
                token_score = 0.3 * ratio
                score += token_score
                debug_info.append(f"标题精确{len(exact_matched)}/{len(query_words)}(+{token_score:.2f})")

            # 3. 模糊匹配（对未精确匹配的词，找最长公共子串）
            unmatched = [w for w in query_words if w not in title]
            if unmatched:
                fuzzy_total = 0.0
                for word in unmatched:
                    matcher = difflib.SequenceMatcher(None, word, title)
                    match = matcher.find_longest_match(0, len(word), 0, len(title))
                    if match.size >= max(2, len(word) * 0.4):
                        # 公共子串覆盖了查询词 40% 以上 → 算模糊匹配
                        overlap_ratio = match.size / len(word)
                        fuzzy_total += overlap_ratio
                if fuzzy_total > 0:
                    fuzzy_score = 0.25 * min(fuzzy_total / len(unmatched), 1.0)
                    score += fuzzy_score
                    debug_info.append(f"标题模糊({len(unmatched)}个未精确)(+{fuzzy_score:.2f})")

        # ── 描述匹配 ──

        if query_lower in description:
            score += 0.2
            debug_info.append(f"描述完全匹配(+0.2)")
        elif query_words:
            # 4. 描述精确分词匹配
            desc_matched = [w for w in query_words if w in description]
            if desc_matched:
                desc_ratio = len(desc_matched) / len(query_words)
                desc_score = 0.1 * desc_ratio
                score += desc_score
                debug_info.append(f"描述精确{len(desc_matched)}/{len(query_words)}(+{desc_score:.2f})")

            # 5. 描述模糊匹配
            unmatched_desc = [w for w in query_words if w not in description]
            if unmatched_desc:
                fuzzy_total = 0.0
                for word in unmatched_desc:
                    matcher = difflib.SequenceMatcher(None, word, description)
                    match = matcher.find_longest_match(0, len(word), 0, len(description))
                    if match.size >= max(2, len(word) * 0.4):
                        overlap_ratio = match.size / len(word)
                        fuzzy_total += overlap_ratio
                if fuzzy_total > 0:
                    fuzzy_score = 0.1 * min(fuzzy_total / len(unmatched_desc), 1.0)
                    score += fuzzy_score
                    debug_info.append(f"描述模糊(+{fuzzy_score:.2f})")

        final_score = min(score, 1.0)

        if final_score > 0 and debug_info:
            print(f"      📊 相关性: {', '.join(debug_info)} => {final_score:.2f}")

        return final_score

    def _calc_quality(self, video: Dict) -> float:
        """计算质量分数（基于播放量 - 强化高播放量优势）"""
        play_count = video.get('play_count', 0)
        
        # 采用对数缩放或更激进的阶梯，让百万播放和十万播放拉开差距
        if play_count > 5000000:
            return 1.0
        elif play_count > 1000000:
            return 0.95
        elif play_count > 500000:
            return 0.85
        elif play_count > 100000:
            return 0.7
        elif play_count > 50000:
            return 0.5
        elif play_count > 10000:
            return 0.3
        else:
            return 0.1

    def _calc_recency(self, video: Dict) -> float:
        """计算时效性分数"""
        publish_time = video.get('publish_time', 0)
        
        if not publish_time:
            return 0.5
        
        # 简单判断：最近一年内的视频给高分
        import time
        current_time = int(time.time())
        age_days = (current_time - publish_time) / (24 * 3600)
        
        if age_days < 30:
            return 1.0
        elif age_days < 90:
            return 0.8
        elif age_days < 365:
            return 0.6
        else:
            return 0.4

    def _calc_engagement(self, video: Dict) -> float:
        """计算互动度分数（基于弹幕数）"""
        danmaku_count = video.get('danmaku_count', 0)
        
        if danmaku_count > 10000:
            return 1.0
        elif danmaku_count > 1000:
            return 0.8
        elif danmaku_count > 100:
            return 0.6
        elif danmaku_count > 10:
            return 0.4
        else:
            return 0.2
