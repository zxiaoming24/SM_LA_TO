package com.dhi.wha.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

@Data
public class LocalGenerationEvaluationDTO {
    /**
     * 评估id
     */
    @JsonProperty("assessment_id")
    private String assessmentId;
    /**
     * 局部类型
     */
    @JsonProperty("part_type")
    private String partType;
    /**
     * 局部索引
     */
    @JsonProperty("part_index")
    private Integer partIndex;
}
