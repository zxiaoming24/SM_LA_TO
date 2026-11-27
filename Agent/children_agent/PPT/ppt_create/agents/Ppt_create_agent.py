from typing import Dict, List, Any
from pptx import Presentation
from pptx.util import Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.xmlchemy import OxmlElement
import os
import yaml
from pathlib import Path


class PPTGenerateAgent:
    THEME_ROOT = Path(__file__).parent.parent / "ppt_theme"

    def __init__(self, theme_name: str = "business_blue"):
        self.prs = None
        self.theme_cfg = self._load_theme_config(theme_name)

    def _load_theme_config(self, theme: str) -> dict:
        cfg_path = self.THEME_ROOT / f"{theme}.yaml"
        with open(cfg_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        tokens = {**raw["layout"], "sizes": raw["font_size"], "colors": raw["color"]}
        return tokens

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> RGBColor:
        hex_color = hex_color.lstrip('#')
        return RGBColor(int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))

    @staticmethod
    def _add_shadow(element, blur_rad, dist, alpha):
        try:
            effect = element.get_or_add_effectLst()
            outer_shdw = OxmlElement('a:outerShdw')
            outer_shdw.set('blurRad', blur_rad)
            outer_shdw.set('dist', dist)
            outer_shdw.set('dir', '2700000')
            outer_shdw.set('algn', 'tl')
            outer_shdw.set('rotWithShape', '0')
            srgb = OxmlElement('a:srgbClr')
            srgb.set('val', '000000')
            srgb.set('alpha', alpha)
            outer_shdw.append(srgb)
            effect.append(outer_shdw)
        except Exception:
            pass

    # ======================== 基础绘制辅助 ========================

    def _draw_solid_bg(self, slide, color_hex="#FFFFFF"):
        """绘制纯色背景"""
        sw, sh = self.prs.slide_width, self.prs.slide_height
        bg_shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, sw, sh)
        bg_shape.fill.solid()
        bg_shape.fill.fore_color.rgb = self._hex_to_rgb(color_hex)
        bg_shape.line.fill.background()
        sp = bg_shape._element
        sp.getparent().remove(sp)
        slide.shapes._spTree.insert(2, sp)

    def _draw_accent_bar(self, slide, left, top, width, height, color_hex):
        """绘制装饰色条"""
        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(left), Emu(top), Emu(width), Emu(height))
        bar.fill.solid()
        bar.fill.fore_color.rgb = self._hex_to_rgb(color_hex)
        bar.line.fill.background()
        return bar

    def _draw_card(self, slide, left, top, width, height, bg_color="#FFFFFF", tokens=None):
        """绘制圆角卡片"""
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Emu(left), Emu(top), Emu(width), Emu(height))
        card.fill.solid()
        card.fill.fore_color.rgb = self._hex_to_rgb(bg_color)
        card.line.color.rgb = self._hex_to_rgb("#E8E8E8")
        card.line.width = Pt(0.5)
        if tokens:
            self._add_shadow(card._element, tokens["content_shadow_blur"], tokens["content_shadow_dist"], tokens["content_shadow_alpha"])
        return card

    def _draw_number_circle(self, slide, left, top, size, number, color_hex):
        """绘制编号圆圈"""
        circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, Emu(left), Emu(top), Emu(size), Emu(size))
        circle.fill.solid()
        circle.fill.fore_color.rgb = self._hex_to_rgb(color_hex)
        circle.line.fill.background()
        p = circle.text_frame.paragraphs[0]
        p.text = str(number)
        p.font.size = Pt(16)
        p.font.bold = True
        p.font.color.rgb = RGBColor(255, 255, 255)
        p.alignment = PP_ALIGN.CENTER
        circle.text_frame.word_wrap = False
        return circle

    def _draw_textbox(self, slide, left, top, width, height, text, font_size, color_hex, bold=False, align=PP_ALIGN.LEFT):
        """绘制文本框"""
        box = slide.shapes.add_textbox(Emu(left), Emu(top), Emu(width), Emu(height))
        p = box.text_frame.paragraphs[0]
        p.text = text
        p.font.size = Pt(font_size)
        p.font.bold = bold
        p.font.color.rgb = self._hex_to_rgb(color_hex)
        p.alignment = align
        box.text_frame.word_wrap = True
        return box

    def _estimate_text_height(self, text, font_pt, width_emu):
        """根据文本长度、字号和文本框宽度，估算实际需要的文本框高度"""
        if not text or width_emu <= 0:
            return int(font_pt * 12700 * 1.5)
        # 中文每字符宽度约等于字号，英文/数字约一半
        cn_count = sum(1 for c in text if ord(c) > 127)
        en_count = len(text) - cn_count
        char_width = font_pt * 12700  # 1pt = 12700 EMU
        en_char_width = char_width * 0.55
        text_width = cn_count * char_width + en_count * en_char_width
        chars_per_line = max(1, int(width_emu / (cn_count / max(len(text), 1) * char_width + en_count / max(len(text), 1) * en_char_width)))
        # 简化：用平均字符宽度
        avg_char_w = text_width / max(len(text), 1)
        chars_per_line = max(1, int(width_emu / avg_char_w))
        lines = max(1, (len(text) + chars_per_line - 1) // chars_per_line)
        # 行高 = 字号 × 1.6
        line_h = int(font_pt * 12700 * 1.6)
        return lines * line_h

    def _calc_item_sizes(self, available_h, n, kps=None, dets=None, width=None, tokens=None):
        """根据实际文本内容和可用空间，精确计算每个要点/详情文本框高度和间距"""
        if n <= 0:
            return 0, 0, 0
        per_item = available_h // n

        # 基于实际文本估算高度
        if kps and width and tokens:
            d_indent = tokens["detail_indent_emu"]
            point_font = tokens["sizes"]["point_pt"]
            detail_font = tokens["sizes"]["detail_pt"]
            detail_width = max(1, width - d_indent)

            avg_point_text = sum(len(k) + 2 for k in kps) / len(kps)  # +2 for bullet
            p_box_h = self._estimate_text_height("●" + "测试" * int(avg_point_text / 2), point_font, width)
            avg_det_text = sum(len(d) for d in dets if d) / max(1, len([d for d in dets if d])) if dets else 0
            d_box_h = self._estimate_text_height("测试" * max(1, int(avg_det_text / 2)), detail_font, detail_width) if avg_det_text > 0 else 0
        else:
            # 回退：按比例
            p_box_h = int(per_item * 0.28)
            d_box_h = int(per_item * 0.52)

        # 确保不超过可用空间
        total_content = p_box_h + d_box_h
        gap = per_item - total_content
        if gap < 60000:
            # 空间不够，按比例缩减内容
            scale = (per_item - 60000) / max(total_content, 1)
            p_box_h = int(p_box_h * scale)
            d_box_h = int(d_box_h * scale)
            gap = per_item - p_box_h - d_box_h

        # 绝对最小值
        p_box_h = max(p_box_h, int(tokens["sizes"]["point_pt"] * 12700 * 1.6 * 1.2) if tokens else 300000)
        d_box_h = max(d_box_h, 100000)
        gap = max(gap, 60000)

        # 绝对最大值（不超过 per_item 的 40%）
        p_box_h = min(p_box_h, int(per_item * 0.40))
        d_box_h = min(d_box_h, int(per_item * 0.60))

        return p_box_h, d_box_h, gap

    def _render_points(self, slide, left, start_y, width, kps, dets, available_h, tokens, indent=None):
        """通用要点渲染：动态计算高度，确保不超出 available_h"""
        n = len(kps)
        if n == 0:
            return
        p_box_h, d_box_h, gap = self._calc_item_sizes(available_h, n, kps, dets, width, tokens)
        d_indent = indent or tokens["detail_indent_emu"]
        bullet = tokens["point_bullet"]
        cur_y = start_y
        for i, kp in enumerate(kps):
            self._draw_textbox(slide, left, cur_y, width, p_box_h,
                                f"{bullet} {kp}", tokens["sizes"]["point_pt"],
                                tokens["colors"]["accent"], bold=True)
            if i < len(dets) and dets[i]:
                detail_y = cur_y + p_box_h
                self._draw_textbox(slide, left + d_indent, detail_y, width - d_indent, d_box_h,
                                    dets[i], tokens["sizes"]["detail_pt"], tokens["colors"]["text_body"])
                cur_y = detail_y + d_box_h + gap
            else:
                cur_y = cur_y + p_box_h + gap

    # ======================== 封面页 ========================

    def _render_cover_page(self, slide, page, tokens, bg_path):
        """封面页：使用生成的背景图"""
        sw, sh = self.prs.slide_width, self.prs.slide_height
        if bg_path and os.path.exists(bg_path):
            slide.shapes.add_picture(bg_path, 0, 0, sw, sh)
        else:
            self._draw_solid_bg(slide, "#F0F4FA")
            self._draw_accent_bar(slide, 0, 0, 50000, sh, tokens["colors"]["cover_main_title_color"])

        title_box = self._draw_textbox(slide, 800000, tokens["cover_main_title_top_emu"],
                                        sw - 1600000, 1500000, page["title"],
                                        tokens["sizes"]["cover_main_title_pt"],
                                        tokens["colors"]["cover_main_title_color"], bold=True, align=PP_ALIGN.CENTER)
        self._add_shadow(title_box._element, tokens["floating_shadow_blur"], tokens["floating_shadow_dist"], tokens["floating_shadow_alpha"])

        if page.get("subtitle"):
            self._draw_textbox(slide, 800000, tokens["cover_subtitle_top_emu"],
                                sw - 1600000, 600000, page["subtitle"],
                                tokens["sizes"]["cover_subtitle_pt"],
                                tokens["colors"]["cover_subtitle_color"], align=PP_ALIGN.CENTER)

        sections = page.get("sections", [])
        if not sections:
            return
        sec_count = len(sections)
        y = tokens["cover_section_start_top_emu"]
        sec_h = tokens["section_title_box_height_emu"] + tokens["section_title_to_content_gap_emu"] + tokens["section_content_box_height_emu"]
        gap = tokens["cover_section_gap_emu"]
        # 动态计算卡片宽度，确保不超出
        total_needed = sec_count * 2800000 + (sec_count - 1) * 150000
        if total_needed > sw - 800000:
            sec_w = (sw - 800000 - (sec_count - 1) * 150000) // sec_count
        else:
            sec_w = 2800000
        start_x = (sw - sec_w * sec_count - 150000 * (sec_count - 1)) // 2

        for idx, sec in enumerate(sections):
            sx = start_x + idx * (sec_w + 150000)
            self._draw_card(slide, sx, y, sec_w, sec_h + 200000, "#FFFFFF", tokens)
            inner_m = 250000
            self._draw_textbox(slide, sx + inner_m, y + inner_m,
                                sec_w - inner_m * 2, tokens["section_title_box_height_emu"],
                                sec["title"], tokens["sizes"]["section_title_pt"],
                                tokens["colors"]["section_title_color"], bold=True)
            self._draw_textbox(slide, sx + inner_m, y + inner_m + tokens["section_title_to_content_gap_emu"],
                                sec_w - inner_m * 2, tokens["section_content_box_height_emu"],
                                sec["content"], tokens["sizes"]["section_content_pt"],
                                tokens["colors"]["section_content_color"])

    # ======================== 尾页/总结页 ========================

    def _render_summary_page(self, slide, page, tokens, bg_path):
        """总结页：使用生成的背景图"""
        sw, sh = self.prs.slide_width, self.prs.slide_height
        if bg_path and os.path.exists(bg_path):
            slide.shapes.add_picture(bg_path, 0, 0, sw, sh)
        else:
            self._draw_solid_bg(slide, "#F0F4FA")

        self._draw_textbox(slide, 800000, tokens["content_margin_top_emu"],
                            sw - 1600000, tokens["content_title_box_height_emu"],
                            page["title"], tokens["sizes"]["content_title_pt"],
                            tokens["colors"]["content_title_color"], bold=True, align=PP_ALIGN.CENTER)

        kps = page.get("key_points", [])
        dets = page.get("detail_content", [])
        if not kps:
            return
        card_count = len(kps)
        margin = 600000
        gap = 200000
        total_w = sw - margin * 2
        card_w = (total_w - gap * (card_count - 1)) // card_count
        card_top = tokens["content_margin_top_emu"] + tokens["content_title_box_height_emu"] + 400000
        card_h = sh - card_top - margin

        for idx, kp in enumerate(kps):
            cx = margin + idx * (card_w + gap)
            self._draw_card(slide, cx, card_top, card_w, card_h, "#FFFFFF", tokens)
            inner_m = 280000
            circle_size = 400000
            self._draw_number_circle(slide, cx + inner_m, card_top + inner_m,
                                      circle_size, idx + 1, tokens["colors"]["accent"])
            # 动态计算卡片内各元素高度
            inner_available = card_h - inner_m * 2 - circle_size - 200000  # 圆圈+间距
            text_w = card_w - inner_m * 2
            point_h = self._estimate_text_height(kp, tokens["sizes"]["point_pt"], text_w)
            point_h = min(point_h, int(inner_available * 0.35))
            detail_h = inner_available - point_h
            if idx < len(dets) and dets[idx]:
                needed = self._estimate_text_height(dets[idx], tokens["sizes"]["detail_pt"], text_w)
                if needed > detail_h:
                    # 按比例缩减
                    scale = detail_h / max(needed, 1)
                    point_h = int(point_h * scale)
                    detail_h = inner_available - point_h
            self._draw_textbox(slide, cx + inner_m, card_top + inner_m + circle_size + 100000,
                                card_w - inner_m * 2, int(point_h), kp,
                                tokens["sizes"]["point_pt"], tokens["colors"]["accent"], bold=True)
            if idx < len(dets) and dets[idx]:
                self._draw_textbox(slide, cx + inner_m, card_top + inner_m + circle_size + 100000 + int(point_h),
                                    card_w - inner_m * 2, int(detail_h), dets[idx],
                                    tokens["sizes"]["detail_pt"], tokens["colors"]["text_body"])

    # ======================== 布局A：左侧色条 + 右侧内容 ========================

    def _render_right_content(self, slide, page, tokens):
        """左侧色条(40%) + 右侧要点内容(60%)"""
        sw, sh = self.prs.slide_width, self.prs.slide_height
        self._draw_solid_bg(slide, "#F8F9FC")

        sidebar_w = int(sw * 0.38)
        self._draw_accent_bar(slide, 0, 0, sidebar_w, sh, tokens["colors"]["cover_main_title_color"])

        self._draw_textbox(slide, 300000, tokens["content_margin_top_emu"] + 200000,
                            sidebar_w - 500000, tokens["content_title_box_height_emu"],
                            page["title"], tokens["sizes"]["content_title_pt"],
                            "#FFFFFF", bold=True)
        self._draw_accent_bar(slide, 300000, tokens["content_margin_top_emu"] + tokens["content_title_box_height_emu"] + 300000,
                              sidebar_w - 600000, 30000, "#FFFFFF")

        left = sidebar_w + 400000
        content_w = sw - left - 400000
        start_y = tokens["content_margin_top_emu"] + 200000
        available_h = sh - start_y - 300000  # 底部留白

        kps = page.get("key_points", [])
        dets = page.get("detail_content", [])
        self._render_points(slide, left, start_y, content_w, kps, dets, available_h, tokens)

    # ======================== 布局B：顶部色栏 + 下方全宽内容 ========================

    def _render_top_banner(self, slide, page, tokens):
        """顶部色栏标题 + 下方全宽要点"""
        sw, sh = self.prs.slide_width, self.prs.slide_height
        self._draw_solid_bg(slide, "#FFFFFF")

        bar_h = 1100000
        self._draw_accent_bar(slide, 0, 0, sw, bar_h, tokens["colors"]["cover_main_title_color"])
        self._draw_textbox(slide, 600000, 180000, sw - 1200000, bar_h - 360000,
                            page["title"], tokens["sizes"]["content_title_pt"],
                            "#FFFFFF", bold=True, align=PP_ALIGN.CENTER)
        self._draw_accent_bar(slide, 0, bar_h, sw, 40000, tokens["colors"]["accent"])

        margin = 600000
        content_w = sw - margin * 2
        start_y = bar_h + 500000
        available_h = sh - start_y - 300000

        kps = page.get("key_points", [])
        dets = page.get("detail_content", [])
        self._render_points(slide, margin, start_y, content_w, kps, dets, available_h, tokens)

    # ======================== 布局C：居中卡片 ========================

    def _render_center_focus(self, slide, page, tokens):
        """居中白色大卡片 + 标题 + 要点"""
        sw, sh = self.prs.slide_width, self.prs.slide_height
        self._draw_solid_bg(slide, "#F0F2F8")

        self._draw_accent_bar(slide, 0, 0, sw, 60000, tokens["colors"]["cover_main_title_color"])
        self._draw_textbox(slide, 600000, 250000, sw - 1200000, tokens["content_title_box_height_emu"],
                            page["title"], tokens["sizes"]["content_title_pt"],
                            tokens["colors"]["content_title_color"], bold=True, align=PP_ALIGN.CENTER)

        card_w = int(sw * 0.85)
        card_x = (sw - card_w) // 2
        card_y = 250000 + tokens["content_title_box_height_emu"] + 300000
        card_h = sh - card_y - 300000  # 底部留白
        self._draw_card(slide, card_x, card_y, card_w, card_h, "#FFFFFF", tokens)

        inner_m = 500000
        start_y = card_y + inner_m
        available_h = card_h - inner_m * 2

        kps = page.get("key_points", [])
        dets = page.get("detail_content", [])
        self._render_points(slide, card_x + inner_m, start_y, card_w - inner_m * 2, kps, dets, available_h, tokens)

    # ======================== 布局D：多列卡片网格 ========================

    def _render_grid_cards(self, slide, page, tokens):
        """2~3列白色卡片，每个要点一张"""
        sw, sh = self.prs.slide_width, self.prs.slide_height
        self._draw_solid_bg(slide, "#F5F6FA")

        self._draw_accent_bar(slide, 0, 0, sw, 60000, tokens["colors"]["cover_main_title_color"])
        self._draw_textbox(slide, 600000, 200000, sw - 1200000, tokens["content_title_box_height_emu"],
                            page["title"], tokens["sizes"]["content_title_pt"],
                            tokens["colors"]["content_title_color"], bold=True, align=PP_ALIGN.CENTER)

        kps = page.get("key_points", [])
        dets = page.get("detail_content", [])
        count = max(len(kps), 1)
        cols = 2 if count <= 2 else 3
        rows = (count + cols - 1) // cols

        margin = 500000
        gap = 200000
        total_w = sw - margin * 2
        card_w = (total_w - gap * (cols - 1)) // cols
        card_top = 200000 + tokens["content_title_box_height_emu"] + 350000
        total_h = sh - card_top - margin
        card_h = (total_h - gap * (rows - 1)) // rows

        for idx, kp in enumerate(kps):
            row = idx // cols
            col = idx % cols
            cx = margin + col * (card_w + gap)
            cy = card_top + row * (card_h + gap)

            self._draw_card(slide, cx, cy, card_w, card_h, "#FFFFFF", tokens)
            inner_m = 300000
            circle_size = 350000

            self._draw_number_circle(slide, cx + inner_m, cy + inner_m,
                                      circle_size, idx + 1, tokens["colors"]["cover_main_title_color"])
            # 卡片内动态分配高度
            inner_available = card_h - inner_m * 2 - circle_size - 200000
            point_w = card_w - inner_m * 2 - circle_size - 100000
            detail_w = card_w - inner_m * 2
            point_h = self._estimate_text_height(kp, tokens["sizes"]["point_pt"], point_w)
            point_h = min(point_h, int(inner_available * 0.35))
            detail_h = inner_available - point_h
            if idx < len(dets) and dets[idx]:
                needed = self._estimate_text_height(dets[idx], tokens["sizes"]["detail_pt"], detail_w)
                if needed > detail_h:
                    scale = detail_h / max(needed, 1)
                    point_h = int(point_h * scale)
                    detail_h = inner_available - point_h

            self._draw_textbox(slide, cx + inner_m + circle_size + 100000, cy + inner_m,
                                card_w - inner_m * 2 - circle_size - 100000, point_h,
                                kp, tokens["sizes"]["point_pt"],
                                tokens["colors"]["accent"], bold=True)
            if idx < len(dets) and dets[idx]:
                self._draw_textbox(slide, cx + inner_m, cy + inner_m + circle_size + 100000,
                                    card_w - inner_m * 2, int(detail_h),
                                    dets[idx], tokens["sizes"]["detail_pt"],
                                    tokens["colors"]["text_body"])

    # ======================== 布局E：时间线/步骤 ========================

    def _render_timeline(self, slide, page, tokens):
        """纵向编号步骤，带连接线"""
        sw, sh = self.prs.slide_width, self.prs.slide_height
        self._draw_solid_bg(slide, "#FFFFFF")

        self._draw_accent_bar(slide, 0, 0, sw, 60000, tokens["colors"]["accent"])
        self._draw_textbox(slide, 600000, 200000, sw - 1200000, tokens["content_title_box_height_emu"],
                            page["title"], tokens["sizes"]["content_title_pt"],
                            tokens["colors"]["content_title_color"], bold=True, align=PP_ALIGN.CENTER)

        kps = page.get("key_points", [])
        dets = page.get("detail_content", [])
        count = max(len(kps), 1)

        margin_x = 800000
        content_w = sw - margin_x * 2
        start_y = 200000 + tokens["content_title_box_height_emu"] + 400000
        total_h = sh - start_y - 400000
        step_h = total_h // count

        # 纵向连接线
        line_x = margin_x + 200000
        self._draw_accent_bar(slide, line_x, start_y + 200000, 30000,
                              total_h - 400000, "#E0E0E0")

        # 动态计算每个步骤内各元素高度
        circle_size = min(400000, int(step_h * 0.35))
        for idx, kp in enumerate(kps):
            cy = start_y + idx * step_h
            self._draw_number_circle(slide, margin_x, cy,
                                      circle_size, idx + 1, tokens["colors"]["accent"])

            # 步骤内可用空间
            inner_available = step_h - 100000  # 上下各留50000
            text_w = content_w - circle_size - 150000
            point_h = self._estimate_text_height(kp, tokens["sizes"]["point_pt"], text_w)
            point_h = min(point_h, int(inner_available * 0.35))
            detail_h = inner_available - point_h
            if idx < len(dets) and dets[idx]:
                needed = self._estimate_text_height(dets[idx], tokens["sizes"]["detail_pt"], text_w)
                if needed > detail_h:
                    scale = detail_h / max(needed, 1)
                    point_h = int(point_h * scale)
                    detail_h = inner_available - point_h

            self._draw_textbox(slide, margin_x + circle_size + 150000, cy,
                                text_w, point_h,
                                kp, tokens["sizes"]["point_pt"],
                                tokens["colors"]["accent"], bold=True)
            if idx < len(dets) and dets[idx]:
                self._draw_textbox(slide, margin_x + circle_size + 150000, cy + point_h,
                                    text_w, detail_h,
                                    dets[idx], tokens["sizes"]["detail_pt"],
                                    tokens["colors"]["text_body"])

    # ======================== 布局F：对比分栏 ========================

    def _render_comparison(self, slide, page, tokens):
        """左右分栏对比"""
        sw, sh = self.prs.slide_width, self.prs.slide_height
        self._draw_solid_bg(slide, "#F8F9FC")

        self._draw_accent_bar(slide, 0, 0, sw, 60000, tokens["colors"]["cover_main_title_color"])
        self._draw_textbox(slide, 600000, 200000, sw - 1200000, tokens["content_title_box_height_emu"],
                            page["title"], tokens["sizes"]["content_title_pt"],
                            tokens["colors"]["content_title_color"], bold=True, align=PP_ALIGN.CENTER)

        kps = page.get("key_points", [])
        dets = page.get("detail_content", [])

        gap = 250000
        margin = 500000
        total_w = sw - margin * 2
        card_w = (total_w - gap) // 2
        card_top = 200000 + tokens["content_title_box_height_emu"] + 350000
        card_h = sh - card_top - margin

        # 左卡片
        self._draw_card(slide, margin, card_top, card_w, card_h, "#FFFFFF", tokens)
        self._draw_accent_bar(slide, margin, card_top, card_w, 50000, tokens["colors"]["cover_main_title_color"])

        # 右卡片
        rx = margin + card_w + gap
        self._draw_card(slide, rx, card_top, card_w, card_h, "#FFFFFF", tokens)
        self._draw_accent_bar(slide, rx, card_top, card_w, 50000, tokens["colors"]["accent"])

        inner_m = 350000
        half_mid = len(kps) // 2 + 1 if len(kps) > 1 else len(kps)
        left_kps = kps[:half_mid]
        left_dets = dets[:half_mid]
        right_kps = kps[half_mid:]
        right_dets = dets[half_mid:]

        # 卡片内可用高度
        card_inner_h = card_h - 100000 - inner_m  # 顶部装饰条100000 + 内边距

        # 左半要点
        self._render_points(slide, margin + inner_m, card_top + 100000,
                             card_w - inner_m * 2, left_kps, left_dets, card_inner_h, tokens)
        # 右半要点
        self._render_points(slide, rx + inner_m, card_top + 100000,
                             card_w - inner_m * 2, right_kps, right_dets, card_inner_h, tokens)

    # ======================== 布局G：大数字突出 ========================

    def _render_big_number(self, slide, page, tokens):
        """大数字突出布局：适合数据展示，每个要点配一个大数字"""
        sw, sh = self.prs.slide_width, self.prs.slide_height
        self._draw_solid_bg(slide, "#FFFFFF")

        # 顶部装饰
        self._draw_accent_bar(slide, 0, 0, sw, 60000, tokens["colors"]["cover_main_title_color"])

        # 标题
        self._draw_textbox(slide, 600000, 200000, sw - 1200000, tokens["content_title_box_height_emu"],
                            page["title"], tokens["sizes"]["content_title_pt"],
                            tokens["colors"]["content_title_color"], bold=True, align=PP_ALIGN.CENTER)

        kps = page.get("key_points", [])
        dets = page.get("detail_content", [])
        count = max(len(kps), 1)

        margin = 600000
        gap = 300000
        total_w = sw - margin * 2
        col_w = (total_w - gap * (count - 1)) // count
        start_y = 200000 + tokens["content_title_box_height_emu"] + 400000
        available_h = sh - start_y - margin

        for idx, kp in enumerate(kps):
            cx = margin + idx * (col_w + gap)

            # 大数字（序号）
            num_size = min(1200000, available_h * 0.35)
            self._draw_textbox(slide, cx, start_y, col_w, int(num_size),
                                str(idx + 1), 72, tokens["colors"]["cover_main_title_color"],
                                bold=True, align=PP_ALIGN.CENTER)

            # 装饰线
            self._draw_accent_bar(slide, cx + col_w // 2 - 200000, start_y + int(num_size) + 100000,
                                  400000, 40000, tokens["colors"]["accent"])

            # 要点标题
            point_top = start_y + int(num_size) + 250000
            point_h = int(available_h * 0.20)
            self._draw_textbox(slide, cx, point_top, col_w, point_h,
                                kp, tokens["sizes"]["point_pt"],
                                tokens["colors"]["accent"], bold=True, align=PP_ALIGN.CENTER)

            # 详情
            if idx < len(dets) and dets[idx]:
                detail_top = point_top + point_h + 100000
                detail_h = available_h - (detail_top - start_y)
                self._draw_textbox(slide, cx, detail_top, col_w, int(detail_h),
                                    dets[idx], tokens["sizes"]["detail_pt"],
                                    tokens["colors"]["text_body"], align=PP_ALIGN.CENTER)

    # ======================== 布局H：横向图标行 ========================

    def _render_icon_row(self, slide, page, tokens):
        """横向图标行：3-4个圆形图标+标题+说明，横向排列"""
        sw, sh = self.prs.slide_width, self.prs.slide_height
        self._draw_solid_bg(slide, "#F8F9FC")

        # 顶部装饰
        self._draw_accent_bar(slide, 0, 0, sw, 60000, tokens["colors"]["accent"])

        # 标题
        self._draw_textbox(slide, 600000, 200000, sw - 1200000, tokens["content_title_box_height_emu"],
                            page["title"], tokens["sizes"]["content_title_pt"],
                            tokens["colors"]["content_title_color"], bold=True, align=PP_ALIGN.CENTER)

        kps = page.get("key_points", [])
        dets = page.get("detail_content", [])
        count = max(len(kps), 1)

        margin = 500000
        gap = 200000
        total_w = sw - margin * 2
        col_w = (total_w - gap * (count - 1)) // count
        start_y = 200000 + tokens["content_title_box_height_emu"] + 500000

        # 圆形图标大小
        circle_size = min(800000, col_w * 0.6)
        icon_colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD"]

        for idx, kp in enumerate(kps):
            cx = margin + idx * (col_w + gap)
            color = icon_colors[idx % len(icon_colors)]

            # 圆形图标背景
            circle = slide.shapes.add_shape(MSO_SHAPE.OVAL,
                                             Emu(cx + (col_w - circle_size) // 2), Emu(start_y),
                                             Emu(circle_size), Emu(circle_size))
            circle.fill.solid()
            circle.fill.fore_color.rgb = self._hex_to_rgb(color)
            circle.line.fill.background()
            self._add_shadow(circle._element, tokens["content_shadow_blur"], tokens["content_shadow_dist"], tokens["content_shadow_alpha"])

            # 图标内数字/符号
            p = circle.text_frame.paragraphs[0]
            p.text = str(idx + 1)
            p.font.size = Pt(32)
            p.font.bold = True
            p.font.color.rgb = RGBColor(255, 255, 255)
            p.alignment = PP_ALIGN.CENTER

            # 要点标题
            text_top = start_y + circle_size + 200000
            text_h = self._estimate_text_height(kp, tokens["sizes"]["point_pt"], col_w)
            self._draw_textbox(slide, cx, text_top, col_w, text_h,
                                kp, tokens["sizes"]["point_pt"],
                                tokens["colors"]["accent"], bold=True, align=PP_ALIGN.CENTER)

            # 详情
            if idx < len(dets) and dets[idx]:
                detail_top = text_top + text_h + 150000
                detail_h = sh - detail_top - margin
                self._draw_textbox(slide, cx, detail_top, col_w, int(detail_h),
                                    dets[idx], tokens["sizes"]["detail_pt"],
                                    tokens["colors"]["text_body"], align=PP_ALIGN.CENTER)

    # ======================== 布局I：金句聚焦 ========================

    def _render_quote_focus(self, slide, page, tokens):
        """金句聚焦：大字居中+装饰引号，适合核心观点展示"""
        sw, sh = self.prs.slide_width, self.prs.slide_height
        self._draw_solid_bg(slide, tokens["colors"]["cover_main_title_color"])

        # 页面标题
        self._draw_textbox(slide, 600000, 300000, sw - 1200000, tokens["content_title_box_height_emu"],
                            page["title"], tokens["sizes"]["content_title_pt"],
                            "#FFFFFF", bold=True, align=PP_ALIGN.CENTER)

        kps = page.get("key_points", [])
        dets = page.get("detail_content", [])
        if not kps:
            return

        # 居中卡片
        card_w = int(sw * 0.75)
        card_h = int(sh * 0.55)
        card_x = (sw - card_w) // 2
        card_y = (sh - card_h) // 2 + 200000
        card = self._draw_card(slide, card_x, card_y, card_w, card_h, "#FFFFFF", tokens)

        # 左上角大引号装饰
        quote_size = 600000
        self._draw_textbox(slide, card_x + 200000, card_y + 100000, quote_size, quote_size,
                            '“', 96, tokens["colors"]["accent"], bold=True)

        # 右下角大引号装饰
        self._draw_textbox(slide, card_x + card_w - quote_size - 200000, card_y + card_h - quote_size - 100000,
                            quote_size, quote_size,
                            '”', 96, tokens["colors"]["accent"], bold=True)

        # 金句内容（第一个要点作为主金句）
        inner_m = 800000
        main_text = kps[0] if kps else ""
        text_w = card_w - inner_m * 2
        main_h = self._estimate_text_height(main_text, 28, text_w)
        main_h = min(main_h, int(card_h * 0.4))

        self._draw_textbox(slide, card_x + inner_m, card_y + (card_h - main_h) // 2 - 200000,
                            text_w, main_h, main_text, 28,
                            tokens["colors"]["content_title_color"], bold=True, align=PP_ALIGN.CENTER)

        # 副标题/说明（详情或第二个要点）
        sub_text = ""
        if dets and dets[0]:
            sub_text = dets[0]
        elif len(kps) > 1:
            sub_text = kps[1]

        if sub_text:
            sub_h = self._estimate_text_height(sub_text, tokens["sizes"]["detail_pt"], text_w)
            sub_top = card_y + (card_h + main_h) // 2 + 100000
            self._draw_textbox(slide, card_x + inner_m, sub_top, text_w, sub_h,
                                sub_text, tokens["sizes"]["detail_pt"],
                                tokens["colors"]["text_body"], align=PP_ALIGN.CENTER)

        # 底部其他要点（如果有）
        if len(kps) > 2:
            bottom_y = card_y + card_h + 300000
            bottom_h = sh - bottom_y - 300000
            if bottom_h > 200000:
                remaining_kps = kps[2:]
                remaining_dets = dets[2:] if len(dets) > 2 else []
                self._render_points(slide, 600000, bottom_y, sw - 1200000,
                                     remaining_kps, remaining_dets, bottom_h, tokens)

    # ======================== 布局J：清单勾选 ========================

    def _render_list_check(self, slide, page, tokens):
        """清单勾选布局：带勾选框的列表，适合要点罗列"""
        sw, sh = self.prs.slide_width, self.prs.slide_height
        self._draw_solid_bg(slide, "#FFFFFF")

        # 顶部装饰
        self._draw_accent_bar(slide, 0, 0, sw, 60000, tokens["colors"]["accent"])

        # 标题
        self._draw_textbox(slide, 600000, 200000, sw - 1200000, tokens["content_title_box_height_emu"],
                            page["title"], tokens["sizes"]["content_title_pt"],
                            tokens["colors"]["content_title_color"], bold=True, align=PP_ALIGN.CENTER)

        kps = page.get("key_points", [])
        dets = page.get("detail_content", [])
        count = max(len(kps), 1)

        # 居中卡片
        card_w = int(sw * 0.85)
        card_x = (sw - card_w) // 2
        card_y = 200000 + tokens["content_title_box_height_emu"] + 300000
        card_h = sh - card_y - 400000
        self._draw_card(slide, card_x, card_y, card_w, card_h, "#FAFAFA", tokens)

        inner_m = 400000
        start_y = card_y + inner_m
        available_h = card_h - inner_m * 2
        content_w = card_w - inner_m * 2

        # 动态计算每行高度
        per_item = available_h // count
        item_h = min(per_item, 600000)
        gap = per_item - item_h

        # 勾选框大小
        check_size = 350000

        cur_y = start_y
        for idx, kp in enumerate(kps):
            # 勾选框
            check_box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                                Emu(card_x + inner_m), Emu(cur_y),
                                                Emu(check_size), Emu(check_size))
            check_box.fill.solid()
            check_box.fill.fore_color.rgb = self._hex_to_rgb(tokens["colors"]["accent"])
            check_box.line.fill.background()

            # 勾选符号
            p = check_box.text_frame.paragraphs[0]
            p.text = "✓"
            p.font.size = Pt(20)
            p.font.bold = True
            p.font.color.rgb = RGBColor(255, 255, 255)
            p.alignment = PP_ALIGN.CENTER

            # 要点文本
            text_x = card_x + inner_m + check_size + 200000
            text_w = content_w - check_size - 200000
            text_h = self._estimate_text_height(kp, tokens["sizes"]["point_pt"], text_w)
            text_h = min(text_h, item_h)

            self._draw_textbox(slide, text_x, cur_y, text_w, text_h,
                                kp, tokens["sizes"]["point_pt"],
                                tokens["colors"]["content_title_color"], bold=True)

            # 详情（缩进显示）
            if idx < len(dets) and dets[idx]:
                detail_y = cur_y + text_h + 50000
                detail_h = item_h - text_h - 50000
                if detail_h > 100000:
                    self._draw_textbox(slide, text_x + 200000, detail_y, text_w - 200000, int(detail_h),
                                        dets[idx], tokens["sizes"]["detail_pt"],
                                        tokens["colors"]["text_body"])

            cur_y += item_h + gap

    # ======================== 代码页 ========================

    def _render_code_page(self, slide, page, tokens):
        """代码页：深色背景 + 代码块"""
        sw, sh = self.prs.slide_width, self.prs.slide_height
        self._draw_solid_bg(slide, "#FFFFFF")

        self._draw_accent_bar(slide, 0, 0, sw, 60000, tokens["colors"]["cover_main_title_color"])
        self._draw_textbox(slide, 600000, 200000, sw - 1200000, tokens["content_title_box_height_emu"],
                            page["title"], tokens["sizes"]["content_title_pt"],
                            tokens["colors"]["content_title_color"], bold=True, align=PP_ALIGN.CENTER)

        margin = 600000
        code_x = margin
        code_y = 200000 + tokens["content_title_box_height_emu"] + 300000
        code_w = sw - margin * 2
        code_h = sh - code_y - margin

        code_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Emu(code_x), Emu(code_y), Emu(code_w), Emu(code_h))
        code_card.fill.solid()
        code_card.fill.fore_color.rgb = RGBColor(40, 44, 52)
        code_card.line.fill.background()
        self._add_shadow(code_card._element, tokens["content_shadow_blur"], tokens["content_shadow_dist"], tokens["content_shadow_alpha"])

        dot_colors = ["#FF5F56", "#FFBD2E", "#27C93F"]
        for i, c in enumerate(dot_colors):
            dot = slide.shapes.add_shape(MSO_SHAPE.OVAL, Emu(code_x + 250000 + i * 250000), Emu(code_y + 150000), Emu(120000), Emu(120000))
            dot.fill.solid()
            dot.fill.fore_color.rgb = self._hex_to_rgb(c)
            dot.line.fill.background()

        code_text = page.get("code_snippet", "")
        code_box = slide.shapes.add_textbox(Emu(code_x + 300000), Emu(code_y + 400000),
                                             Emu(code_w - 600000), Emu(code_h - 600000))
        tf = code_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = code_text
        p.font.name = "Consolas"
        p.font.size = Pt(tokens["sizes"]["code_pt"])
        p.font.color.rgb = RGBColor(171, 178, 191)

    # ======================== 主生成入口 ========================

    LAYOUT_MAP = {
        "right_content": "_render_right_content",
        "top_banner": "_render_top_banner",
        "center_focus": "_render_center_focus",
        "grid_cards": "_render_grid_cards",
        "timeline": "_render_timeline",
        "comparison": "_render_comparison",
        "big_number": "_render_big_number",
        "icon_row": "_render_icon_row",
        "quote_focus": "_render_quote_focus",
        "list_check": "_render_list_check",
    }

    def generate(self, outline_data: dict, image_paths: list, output_path: str, ai_colors: dict = None):
        design = self.theme_cfg.copy()
        default_color = {
            "section_content_color": "#333333",
            "cover_main_title_color": "#333333",
            "cover_subtitle_color": "#333333",
            "section_title_color": "#333333",
            "content_title_color": "#333333",
            "accent": "#333333",
            "text_body": "#333333"
        }
        design["colors"] = {**default_color, **design["colors"]}
        if ai_colors and isinstance(ai_colors, dict):
            design["colors"].update(ai_colors)

        if isinstance(image_paths, dict):
            cover_bg = image_paths.get("cover", "")
            last_bg = image_paths.get("last", "")
        elif isinstance(image_paths, list) and len(image_paths) >= 2:
            cover_bg = image_paths[0]
            last_bg = image_paths[1]
        else:
            cover_bg = ""
            last_bg = ""

        self.prs = Presentation()
        self.prs.slide_width = Emu(design["slide_width_emu"])
        self.prs.slide_height = Emu(design["slide_height_emu"])

        pages = outline_data["pages"]
        last_idx = len(pages) - 1

        for i, page in enumerate(pages):
            slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])

            if page["type"] == "cover":
                self._render_cover_page(slide, page, design, cover_bg)
            elif page["type"] == "summary" or i == last_idx:
                self._render_summary_page(slide, page, design, last_bg)
            elif page["type"] == "code":
                self._render_code_page(slide, page, design)
            else:
                layout_name = page.get("layout", "")
                method_name = self.LAYOUT_MAP.get(layout_name)
                if method_name:
                    getattr(self, method_name)(slide, page, design)
                else:
                    auto_layout = self._auto_choose_layout(page)
                    method_name = self.LAYOUT_MAP.get(auto_layout, "_render_right_content")
                    getattr(self, method_name)(slide, page, design)
                print(f"  📐 第{i+1}页布局: {layout_name or self._auto_choose_layout(page)}")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        self.prs.save(output_path)
        print(f"✅ PPT生成完毕：{output_path}")
        return output_path

    def _auto_choose_layout(self, page):
        kps = page.get("key_points", [])
        dets = page.get("detail_content", [])
        total_text_len = sum(len(i) for i in kps) + sum(len(i) for i in dets)
        point_count = len(kps)

        if point_count >= 4 or total_text_len > 700:
            return "timeline"
        elif point_count <= 2 and total_text_len < 300:
            return "grid_cards"
        elif point_count == 3 and total_text_len < 200:
            # 文字很短的3要点用大数字或图标行
            import random
            return random.choice(["big_number", "icon_row"])
        elif point_count == 3:
            return "center_focus"
        else:
            # 随机选择避免单调
            import random
            return random.choice(["right_content", "top_banner", "list_check"])


if __name__ == "__main__":
    mock_data = {
        "title": "测试",
        "pages": [
            {
                "type": "cover", "title": "测试PPT", "subtitle": "Test Presentation",
                "sections": [
                    {"title": "概述", "content": "核心概念介绍"},
                    {"title": "详解", "content": "深入分析"},
                    {"title": "总结", "content": "关键要点"}
                ],
                "key_points": [], "detail_content": []
            },
            {
                "type": "content", "title": "右侧内容布局", "layout": "right_content",
                "key_points": ["要点一", "要点二", "要点三"],
                "detail_content": ["详细说明1", "详细说明2", "详细说明3"]
            },
            {
                "type": "content", "title": "顶部横幅布局", "layout": "top_banner",
                "key_points": ["优势一", "优势二"],
                "detail_content": ["优势详解1", "优势详解2"]
            },
            {
                "type": "content", "title": "居中卡片布局", "layout": "center_focus",
                "key_points": ["特点A", "特点B", "特点C"],
                "detail_content": ["特点描述A", "特点描述B", "特点描述C"]
            },
            {
                "type": "content", "title": "卡片网格布局", "layout": "grid_cards",
                "key_points": ["模块1", "模块2", "模块3"],
                "detail_content": ["模块描述1", "模块描述2", "模块描述3"]
            },
            {
                "type": "content", "title": "时间线布局", "layout": "timeline",
                "key_points": ["步骤一", "步骤二", "步骤三", "步骤四"],
                "detail_content": ["步骤描述1", "步骤描述2", "步骤描述3", "步骤描述4"]
            },
            {
                "type": "content", "title": "对比分栏布局", "layout": "comparison",
                "key_points": ["优点A", "优点B", "缺点A", "缺点B"],
                "detail_content": ["优点描述A", "优点描述B", "缺点描述A", "缺点描述B"]
            },
            {
                "type": "code", "title": "代码示例",
                "code_snippet": "public class Hello {\n    public static void main(String[] args) {\n        System.out.println(\"Hello World\");\n    }\n}"
            },
            {
                "type": "summary", "title": "总结",
                "key_points": ["核心收获一", "核心收获二", "核心收获三"],
                "detail_content": ["收获描述1", "收获描述2", "收获描述3"]
            }
        ]
    }
    agent = PPTGenerateAgent(theme_name="business_blue")
    out_dir = "../static/ppt"
    os.makedirs(out_dir, exist_ok=True)
    ppt_save = os.path.join(out_dir, "layout_test.pptx")
    agent.generate(mock_data, ["", ""], ppt_save)
