package com.dhi.wha.dto;

import lombok.Data;

@Data
public class MindMapInsertDTO {
    // 用户ID
    private Long userId;
    // 思维导图问题
    private String text;
}
