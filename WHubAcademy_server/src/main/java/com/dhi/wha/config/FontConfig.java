package com.dhi.wha.config;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import javax.annotation.PostConstruct;
import java.awt.*;
import java.io.InputStream;

/**
 * 字体配置类，用于注册中文字体到Java GraphicsEnvironment
 * 解决POI渲染PPT时中文乱码问题
 */
@Slf4j
@Component
public class FontConfig {

    /**
     * 应用启动时注册中文字体
     */
    @PostConstruct
    public void registerChineseFonts() {
        GraphicsEnvironment ge = GraphicsEnvironment.getLocalGraphicsEnvironment();
        
        // 注册常见中文字体
        String[] fontPaths = {
            "/fonts/NotoSansCJK-Regular.otf",  // Noto中文字体
            "/fonts/simhei.ttf",               // 黑体
            "/fonts/simsun.ttc"                // 宋体
        };

        for (String fontPath : fontPaths) {
            try (InputStream is = getClass().getResourceAsStream(fontPath)) {
                if (is != null) {
                    Font font = Font.createFont(Font.TRUETYPE_FONT, is);
                    ge.registerFont(font);
                    log.info("成功注册字体: {}", font.getFamily());
                } else {
                    log.warn("未找到字体文件: {}", fontPath);
                }
            } catch (Exception e) {
                log.warn("注册字体失败: {}, 错误: {}", fontPath, e.getMessage());
            }
        }

        // 输出已注册的字体列表供调试
        Font[] allFonts = ge.getAllFonts();
        log.info("系统可用字体数量: {}", allFonts.length);
        for (Font font : allFonts) {
            if (font.getFamily().contains("Noto") || 
                font.getFamily().contains("SimHei") || 
                font.getFamily().contains("SimSun") ||
                font.getFamily().contains("Microsoft")) {
                log.info("可用中文字体: {}", font.getFamily());
            }
        }
    }
}
