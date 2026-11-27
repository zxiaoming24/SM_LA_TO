package com.dhi.wha.dto;

import lombok.Data;

@Data
public class ExtensionReadingDTO {
    // 用户ID
    private Long userId;
    // 拓展阅读材料的问题
    private String text;
}
