package com.dhi.wha.dto;

import lombok.Data;
import java.util.Map;

@Data
public class PracticeStreamRequestDTO {
    private Long userId;
    private String text;
    private String taskType;                // 对应 Python 的 task_type
    private Map<String, Object> extraParams; // 对应 Python 的 extra_params
    private Boolean enableTts = false;
    private Boolean confirmed = false;
    private String overrideSuggestions;
}