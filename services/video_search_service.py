"""
多源视频搜索服务
支持多个国内视频学习平台，按顺序尝试，提高搜索成功率

数据源：
1. Bilibili (api.bilibili.com) — 3个API端点逐级尝试
2. 慕课网 (imooc.com) — 编程课程搜索
3. 中国大学MOOC (icourse163.org) — 大学公开课搜索
"""

import requests
import time
import hashlib
import re
from typing import List, Dict, Any, Optional


class MultiSourceVideoSearch:
    """多源视频搜索服务 - 聚合多个国内视频学习平台"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/html, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })
        # B站Cookie
        uid = hashlib.md5(str(time.time()).encode()).hexdigest()[:16]
        self.session.cookies.set('buvid3', f'{uid}infoc')
        self.session.cookies.set('buvid4', f'{uid}infoc')
        self.session.cookies.set('buvid_fp', f'{uid}infoc')

    def search_videos(self, keyword: str, page: int = 1, page_size: int = 10) -> List[Dict[str, Any]]:
        """
        多源搜索视频 — 所有源都搜索，汇总后按播放量排序取前N个

        Args:
            keyword: 搜索关键词
            page: 页码
            page_size: 每页数量

        Returns:
            视频列表（所有源都失败时返回空列表）
        """
        print(f"\n   🔍 多源搜索: '{keyword}'")
        all_videos = []

        # 源1: B站（3个端点依次尝试，取第一个成功的结果）
        print(f"   📺 [源1/3] B站搜索中...")
        bili_videos = self._try_bilibili(keyword, page, page_size)
        if bili_videos:
            print(f"      ✅ B站贡献 {len(bili_videos)} 个视频")
            all_videos.extend(bili_videos)
        else:
            print(f"      ⚠️ B站无结果")

        # 源2: 慕课网
        print(f"   📺 [源2/3] 慕课网搜索中...")
        imooc_videos = self._try_imooc(keyword, page_size)
        if imooc_videos:
            print(f"      ✅ 慕课网贡献 {len(imooc_videos)} 个课程")
            all_videos.extend(imooc_videos)
        else:
            print(f"      ⚠️ 慕课网无结果")

        # 源3: 中国大学MOOC
        print(f"   📺 [源3/3] 中国大学MOOC搜索中...")
        icourse_videos = self._try_icourse163(keyword, page_size)
        if icourse_videos:
            print(f"      ✅ 中国大学MOOC贡献 {len(icourse_videos)} 个课程")
            all_videos.extend(icourse_videos)
        else:
            print(f"      ⚠️ 中国大学MOOC无结果")

        if not all_videos:
            print(f"   ❌ 所有视频源均不可用，返回空结果")
            return []

        # ★★★ 展开B站合集/多P视频 ★★★
        all_videos = self._expand_bilibili_collections(all_videos)

        # ★★★ 合集展开后，按合集分组，一个合集当作一个条目排序 ★★★
        # 这样 top_k=1 时能保证拿到合集的完整章节，而不是只取到1P
        grouped = []  # [(collection_title, play_count, pages)]
        singles = []  # 非合集单P视频
        for v in all_videos:
            if v.get('collection') and v.get('collection_title'):
                # 属于合集，按合集分组
                key = v['bvid']
                # 找已存在的组
                found = None
                for g in grouped:
                    if g[0] == key:
                        found = g
                        break
                if found:
                    found[2].append(v)  # 向已有组追加分P
                else:
                    grouped.append((key, v.get('play_count', 0), [v]))
            else:
                singles.append(v)

        # 合集的播放量取第一P的播放量作为代表
        grouped.sort(key=lambda g: g[1], reverse=True)
        singles.sort(key=lambda v: v.get('play_count', 0), reverse=True)

        # 交替取：先取合集（展开的全部P），再取单P视频
        result_videos = []
        gi, si = 0, 0
        while len(result_videos) < page_size and (gi < len(grouped) or si < len(singles)):
            if gi < len(grouped):
                # 添加合集的全部P，算作一个结果
                for p in grouped[gi][2]:
                    result_videos.append(p)
                gi += 1
            if len(result_videos) >= page_size:
                break
            if si < len(singles):
                result_videos.append(singles[si])
                si += 1

        top_videos = result_videos[:page_size]

        print(f"   📊 汇总: 共{len(all_videos)}个条目（{len(grouped)}个合集+{len(singles)}个单P），取前{len(top_videos)}个")
        sources_found = set(v.get('platform', '') for v in top_videos)
        print(f"     来源分布: {', '.join(sorted(sources_found))}")

        return top_videos

    # =========================================================================
    # 源1: B站 (3个API端点)
    # =========================================================================

    def _try_bilibili(self, keyword: str, page: int, page_size: int) -> List[Dict]:
        return (self._try_bilibili_v1(keyword, page, page_size)
                or self._try_bilibili_v2(keyword, page, page_size)
                or self._try_bilibili_legacy(keyword, page, page_size))

    def _try_bilibili_v1(self, keyword: str, page: int, page_size: int) -> List[Dict]:
        try:
            url = "https://api.bilibili.com/x/web-interface/search/type"
            params = {'search_type': 'video', 'keyword': keyword, 'page': page, 'pagesize': page_size}
            resp = self.session.get(url, params=params, timeout=8)
            if resp.status_code != 200 or not resp.text.strip().startswith('{'):
                return []
            data = resp.json()
            if data.get('code') != 0:
                return []
            videos = data.get('data', {}).get('result', [])
            if not videos:
                return []
            parsed = [self._parse_bilibili(v) for v in videos if v]
            print(f"      ✅ B站-v1 成功获取 {len(parsed)} 个视频")
            return parsed
        except Exception as e:
            print(f"      ⚠️ B站-v1 失败: {e}")
            return []

    def _try_bilibili_v2(self, keyword: str, page: int, page_size: int) -> List[Dict]:
        try:
            url = "https://api.bilibili.com/x/web-interface/search/all/v2"
            params = {'keyword': keyword, 'page': page, 'pagesize': page_size}
            resp = self.session.get(url, params=params, timeout=8)
            if resp.status_code != 200 or not resp.text.strip().startswith('{'):
                return []
            data = resp.json()
            if data.get('code') != 0:
                return []
            results = data.get('data', {}).get('result', [])
            for section in results:
                if section.get('result_type') == 'video':
                    videos = section.get('data', [])
                    if videos:
                        parsed = [self._parse_bilibili(v) for v in videos[:page_size] if v]
                        print(f"      ✅ B站-v2 成功获取 {len(parsed)} 个视频")
                        return parsed
            return []
        except Exception as e:
            print(f"      ⚠️ B站-v2 失败: {e}")
            return []

    def _try_bilibili_legacy(self, keyword: str, page: int, page_size: int) -> List[Dict]:
        try:
            url = "https://search.bilibili.com/api/search"
            params = {'search_type': 'video', 'keyword': keyword, 'page': page}
            resp = self.session.get(url, params=params, timeout=8)
            if resp.status_code != 200 or not resp.text.strip().startswith('{'):
                return []
            data = resp.json()
            if data.get('code') != 0:
                return []
            videos = data.get('data', {}).get('result', [])
            if not videos:
                return []
            parsed = [self._parse_bilibili(v) for v in videos[:page_size] if v]
            print(f"      ✅ B站-legacy 成功获取 {len(parsed)} 个视频")
            return parsed
        except Exception as e:
            print(f"      ⚠️ B站-legacy 失败: {e}")
            return []

    def _parse_bilibili(self, raw: Dict) -> Dict:
        title = raw.get('title', '').replace('<em class="keyword">', '').replace('</em>', '')
        return {
            'title': title,
            'url': f"https://www.bilibili.com/video/{raw.get('bvid', '')}",
            'bvid': raw.get('bvid', ''),
            'thumbnail': raw.get('pic', ''),
            'duration': self._format_duration(raw.get('duration', '')),
            'author': raw.get('author', ''),
            'play_count': raw.get('play', 0) or raw.get('play_count', 0),
            'publish_time': raw.get('pubdate', ''),
            'description': raw.get('description', '')[:200] if raw.get('description') else '',
            'platform': 'bilibili',
        }

    # =========================================================================
    # B站合集展开（多P视频 → 分P列表）
    # =========================================================================

    def _expand_bilibili_collections(self, videos: List[Dict], max_expand: int = 2) -> List[Dict]:
        """
        将B站合集/多P视频展开为独立的分P条目。

        策略：
          - 只展开前 max_expand 个合集（按播放量最高的）
          - 其余合集保持原样（显示为"XXP合集"）
          - 不限制每个合集的分P数量（有多少展开多少）
        """
        # 先把B站视频按播放量排序
        bili_videos = [v for v in videos if v.get('platform') == 'bilibili' and v.get('bvid')]
        other_videos = [v for v in videos if v.get('platform') != 'bilibili' or not v.get('bvid')]
        bili_videos.sort(key=lambda v: v.get('play_count', 0), reverse=True)

        expanded = list(other_videos)
        expand_count = 0

        for v in bili_videos:
            bvid = v['bvid']
            pages = self._get_bili_video_pages(bvid)
            if not pages or len(pages) <= 1:
                # 单P视频，保持原样
                expanded.append(v)
                continue

            total = len(pages)

            if expand_count < max_expand:
                # 展开该合集
                print(f"      📂 展开合集: {bvid} ({v['title'][:30]}...) -> {total}个分P")
                for p in pages:
                    page_num = p.get('page', 1)
                    part_title = p.get('part', '').strip() or f'第{page_num}讲'
                    expanded.append({
                        'title': f"{v['title']} - {part_title}",
                        'url': f"https://www.bilibili.com/video/{bvid}?p={page_num}",
                        'bvid': bvid,
                        'cid': p.get('cid', 0),
                        'page': page_num,
                        'thumbnail': v.get('thumbnail', ''),
                        'duration': '',
                        'author': v.get('author', ''),
                        'play_count': v.get('play_count', 0),
                        'description': part_title,
                        'platform': 'bilibili',
                        'collection': True,
                        'collection_title': v['title'],
                        'total_pages': total,
                    })
                expand_count += 1
            else:
                # 不展开，标记为合集入口
                print(f"      📁 合集入口: {bvid} ({v['title'][:30]}...) -> {total}P合集")
                expanded.append({
                    'title': v['title'],
                    'url': f"https://www.bilibili.com/video/{bvid}?p=1",
                    'bvid': bvid,
                    'page': 1,
                    'thumbnail': v.get('thumbnail', ''),
                    'duration': v.get('duration', ''),
                    'author': v.get('author', ''),
                    'play_count': v.get('play_count', 0),
                    'description': f'{total}P合集: {v.get("description", "")}',
                    'platform': 'bilibili',
                    'collection': True,
                    'collection_title': v['title'],
                    'total_pages': total,
                    'collapsed': True,  # 标记为未展开的合集
                })

        return expanded

    def _get_bili_video_pages(self, bvid: str) -> Optional[List[Dict]]:
        """获取B站视频的分P列表"""
        try:
            url = f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}'
            resp = self.session.get(url, timeout=8)
            if resp.status_code != 200:
                return None
            data = resp.json()
            if data.get('code') != 0:
                return None
            pages = data.get('data', {}).get('pages', [])
            return [
                {'cid': p.get('cid'), 'page': p.get('page'), 'part': p.get('part', '')}
                for p in pages
            ]
        except Exception as e:
            print(f"      ⚠️ 获取视频分P失败: {bvid} - {e}")
            return None

    # =========================================================================
    # 源2: 慕课网 (imooc.com) — 编程课程
    # =========================================================================

    def _try_imooc(self, keyword: str, page_size: int) -> List[Dict]:
        try:
            url = "https://www.imooc.com/api/search"
            params = {'type': 'course', 'words': keyword, 'page': 1}
            headers = {
                'Referer': 'https://www.imooc.com/',
                'Origin': 'https://www.imooc.com',
            }
            resp = self.session.get(url, params=params, headers=headers, timeout=8)

            if resp.status_code != 200 or not resp.text.strip().startswith('{'):
                print(f"      慕课网返回非JSON，跳过")
                return []

            data = resp.json()
            if data.get('code') != 1000:
                print(f"      慕课网返回错误码: {data.get('code')}")
                return []

            items = data.get('data', {}).get('result', []) or data.get('data', {}).get('list', [])
            if not items:
                print(f"      慕课网结果为空")
                return []

            videos = []
            for item in items[:page_size]:
                title = item.get('name', '') or item.get('title', '')
                if not title:
                    continue
                course_id = item.get('id', '')
                desc = item.get('description', '') or item.get('brief', '') or ''
                # 慕课网的课程通常有多章，标记为课程入口视频
                videos.append({
                    'title': title,
                    'url': f"https://www.imooc.com/learn/{course_id}" if course_id else '',
                    'thumbnail': item.get('pic', '') or item.get('picUrl', '') or '',
                    'duration': self._format_duration(item.get('duration', '')),
                    'author': item.get('lecturer', '') or item.get('teacherName', '') or item.get('company', '') or '慕课网',
                    'play_count': item.get('learnerCount', 0) or item.get('studentCount', 0) or 0,
                    'description': desc[:200],
                    'platform': 'imooc',
                })

            if videos:
                print(f"      ✅ 慕课网 成功获取 {len(videos)} 个课程")
            return videos

        except Exception as e:
            print(f"      ⚠️ 慕课网搜索失败: {e}")
            return []

    # =========================================================================
    # 源3: 中国大学MOOC (icourse163.org) — 大学公开课
    # =========================================================================

    def _try_icourse163(self, keyword: str, page_size: int) -> List[Dict]:
        try:
            url = "https://www.icourse163.org/search.htm"
            params = {'search': keyword}
            headers = {
                'Referer': 'https://www.icourse163.org/',
            }
            resp = self.session.get(url, params=params, headers=headers, timeout=10)

            if resp.status_code != 200:
                print(f"      中国大学MOOC HTTP {resp.status_code}")
                return []

            text = resp.text

            # 从HTML中提取课程卡片数据（u-course-card组件）
            courses = self._parse_icourse163_html(text, page_size)

            if courses:
                print(f"      ✅ 中国大学MOOC 成功获取 {len(courses)} 个课程")
            else:
                print(f"      中国大学MOOC 未找到匹配课程")

            return courses

        except Exception as e:
            print(f"      ⚠️ 中国大学MOOC搜索失败: {e}")
            return []

    def _parse_icourse163_html(self, html: str, limit: int) -> List[Dict]:
        """从中国大学MOOC搜索页HTML中提取课程信息"""
        videos = []

        # 匹配课程卡片JSON数据（嵌入在HTML的data-data属性中）
        card_pattern = re.compile(
    r'<div[^>]*class="[^"]*u-course-card[^"]*"[^>]*data-data=[\'"]([^\'"]+)[\'"]',
    re.DOTALL
)
        matches = card_pattern.findall(html)

        if not matches:
            # 备用：匹配更通用的课程卡片结构
            card_pattern2 = re.compile(
                r'class="[^"]*course-card[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*title="([^"]+)"',
                re.DOTALL
            )
            matches2 = card_pattern2.findall(html)
            for href, title in matches2[:limit]:
                videos.append({
                    'title': title,
                    'url': f"https://www.icourse163.org{href}" if href.startswith('/') else href,
                    'thumbnail': '',
                    'duration': '',
                    'author': '中国大学MOOC',
                    'play_count': 0,
                    'description': '',
                    'platform': 'icourse163',
                })
            return videos

        import json
        for match in matches[:limit]:
            try:
                data = json.loads(match)
                title = data.get('name', '') or data.get('title', '')
                if not title:
                    continue
                course_id = data.get('id', '')
                school = data.get('schoolName', '') or data.get('school', '')
                desc = data.get('summary', '') or data.get('description', '') or ''
                learner_count = data.get('learnerCount', 0) or 0

                videos.append({
                    'title': title,
                    'url': f"https://www.icourse163.org/course/{course_id}" if course_id else '',
                    'thumbnail': data.get('picUrl', '') or data.get('imgUrl', '') or '',
                    'duration': '',
                    'author': school or '中国大学MOOC',
                    'play_count': learner_count,
                    'description': desc[:200],
                    'platform': 'icourse163',
                })
            except Exception:
                continue

        return videos

    # =========================================================================
    # 通用工具
    # =========================================================================

    def _format_duration(self, d: Any) -> str:
        if not d:
            return ''
        try:
            parts = str(d).split(':')
            if len(parts) == 2:
                return f"{parts[0]}分{parts[1]}秒"
            elif len(parts) == 3:
                return f"{parts[0]}小时{parts[1]}分{parts[2]}秒"
            return str(d)
        except:
            return str(d)


# =============================================================================
# 向后兼容：保留 BilibiliSearchService 别名
# =============================================================================

class BilibiliSearchService(MultiSourceVideoSearch):
    """向后兼容 — 实际已经是多源搜索"""
    pass
