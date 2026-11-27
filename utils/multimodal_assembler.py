"""
多模态内容组装器
将视频搜索结果组装为结构化的多模态响应
"""

from typing import List, Dict, Any


class MultimodalAssembler:
    """多模态内容组装器"""

    def assemble_response(
        self, 
        videos: List[Dict[str, Any]], 
        query: str,
        refined_title: str = None,
        summary: str = None
    ) -> Dict[str, Any]:
        """
        组装多模态响应
        
        Args:
            videos: 排序后的视频列表
            query: 原始查询
            refined_title: 提炼后的标题（可选）
            summary: 文字总结（可选）
            
        Returns:
            结构化的多模态响应
        """
        print(f"   📦 组装响应: 收到 {len(videos) if videos else 0} 个视频")
        
        # 检查输入
        if not videos:
            print(f"   ⚠️ 警告: 视频列表为空！")
        
        # 构建视频卡片列表
        video_cards = []
        source_platforms = set()
        for i, video in enumerate(videos[:3], 1):  # 默认返回前3个，不足则返回实际数量
            print(f"   🎬 处理视频 {i}: {video.get('title', '')[:40]}...")
            platform = video.get('platform', '') or video.get('_source', '')
            if platform:
                source_platforms.add(platform)
            card = {
                'rank': i,
                'bvid': video.get('bvid', ''),  # ★★★ 必须保留 BVID，否则后续 ContentStore 按 BVID 独立存储会失败 ★★★
                'title': video.get('title', ''),
                'url': video.get('url', ''),
                'thumbnail': video.get('thumbnail', ''),
                'duration': video.get('duration', ''),
                'author': video.get('author', ''),
                'play_count': self._format_number(video.get('play_count', 0)),
                'quality_score': video.get('quality_score', 0),
                'description': video.get('description', '')[:100],
                'platform': platform,
                # 合集分P字段
                'collection': video.get('collection', False),
                'page': video.get('page', 1),
                'collection_title': video.get('collection_title', ''),
                'total_pages': video.get('total_pages', 0),
                'collapsed': video.get('collapsed', False),
            }
            video_cards.append(card)
        
        print(f"   ✅ 组装完成: {len(video_cards)} 个视频卡片")
        
        # 构建来源标签
        platform_names = {
            'bilibili': 'B站', 'imooc': '慕课网', 'icourse163': '中国大学MOOC',
        }
        source_tag = ''
        if source_platforms:
            names = [platform_names.get(p, p) for p in sorted(source_platforms)]
            source_tag = f"（来源: {'/'.join(names)}）"

        # 构建完整响应
        response = {
            'query': query,
            'refined_title': refined_title or query,
            'total_results': len(videos),
            'videos': video_cards,
            'summary': summary or self._generate_default_summary(query, len(video_cards), source_tag),
            'metadata': {
                'search_keywords': [query],
                'ranking_criteria': ['相关性', '播放量', '时效性', '互动度'],
                'timestamp': self._get_timestamp(),
                'source_platforms': list(source_platforms),
            }
        }
        
        return response

    def _format_number(self, num: int) -> str:
        """格式化数字显示"""
        if num >= 10000:
            return f"{num / 10000:.1f}万"
        elif num >= 1000:
            return f"{num / 1000:.1f}千"
        else:
            return str(num)

    def _generate_default_summary(self, query: str, count: int, source_tag: str = '') -> str:
        """生成默认总结"""
        return f"为您找到关于「{query}」的{count}个相关教学视频{source_tag}，已按相关性和质量排序。"

    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
