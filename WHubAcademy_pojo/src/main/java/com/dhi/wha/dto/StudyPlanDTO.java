package com.dhi.wha.dto;

import lombok.Data;

@Data
public class StudyPlanDTO {
    private String text;
    private String userId;
    private boolean enableTts;
}
