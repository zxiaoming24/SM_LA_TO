package com.dhi.wha.dto;

import lombok.Data;

@Data
public class VisualizationDTO {
    // 历史记录id
    private Long historyId;
    // 可视化代码
    private String code;
    // 可视化的类型
    private String algorithmType;
    // 语言
    private String language;
}
