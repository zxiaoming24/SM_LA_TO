package com.dhi.wha.dto;

import lombok.Data;

@Data
public class VideoDTO {
    /**
     * 用户id
     */
    private Long userId;
    /**
     * 用户输入的文本
     */
    private String text;
}
