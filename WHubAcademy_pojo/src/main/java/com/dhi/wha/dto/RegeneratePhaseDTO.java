package com.dhi.wha.dto;

import lombok.Data;

@Data
public class RegeneratePhaseDTO {
    /**
     * 阶段索引
     */
    private Integer phase_index;
    /**
     * 计划ID
     */
    private String plan_id;
}
