package com.dhi.wha.utils;

import com.dhi.wha.entity.ExtensionReading;

public class HtmlGenerator {
    private HtmlGenerator() {}

    public static String generateReadingHtml(ExtensionReading data) {
        if (data == null) {
            return "<div>暂无拓展内容</div>";
        }

        // 改用传统拼接方式，不依赖文本块和formatted()
        return "<div style=\"max-width:800px; margin:20px auto; padding:20px; font-family:Microsoft YaHei; line-height:1.8; color:#333;\">"
                + "<h2 style=\"color:#2c3e50; border-left:4px solid #3498db; padding-left:12px;\">" + data.getTitle() + "</h2>"
                + "<div style=\"margin:16px 0;\">"
                + "<h3 style=\"color:#3498db; font-size:16px; font-weight:bold;\">📘 知识点背景溯源</h3>"
                + "<p>" + data.getBackground() + "</p>"
                + "</div>"
                + "<div style=\"margin:16px 0;\">"
                + "<h3 style=\"color:#3498db; font-size:16px; font-weight:bold;\">🔍 易混淆知识点辨析</h3>"
                + "<p>" + data.getKnowledgeDistinguish() + "</p>"
                + "</div>"
                + "<div style=\"margin:16px 0;\">"
                + "<h3 style=\"color:#3498db; font-size:16px; font-weight:bold;\">⚙️ 底层原理拓展</h3>"
                + "<p>" + data.getPrincipleExtend() + "</p>"
                + "</div>"
                + "<div style=\"margin:16px 0;\">"
                + "<h3 style=\"color:#3498db; font-size:16px; font-weight:bold;\">⚠️ 学习误区与避坑</h3>"
                + "<p>" + data.getMistakeAvoid() + "</p>"
                + "</div>"
                + "<div style=\"margin:16px 0;\">"
                + "<h3 style=\"color:#3498db; font-size:16px; font-weight:bold;\">💼 行业应用场景</h3>"
                + "<p>" + data.getApplicationScene() + "</p>"
                + "</div>"
                + "<div style=\"margin:16px 0; background:#f8f9fa; padding:12px; border-radius:8px;\">"
                + "<h3 style=\"color:#e67e22; font-size:16px; font-weight:bold;\">🎯 个性化学习建议</h3>"
                + "<p>" + data.getPersonalSuggest() + "</p>"
                + "</div>"
                + "</div>";
    }
}
