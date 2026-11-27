package com.dhi.wha.dto;

import lombok.Data;

@Data
public class AnimationDTO {
    /**
     * 用户id
     */
    private Long userId;
    /**
     * 用户输入
     */
    private String text;
    /**
     * 是否启用TTS
     */
    private Boolean enableTts;
}
