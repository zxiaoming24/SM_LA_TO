package com.dhi.wha.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

@Data
public class StudyPlanChoiceDTO {
    @JsonProperty("take_exam")
    private Boolean takeExam = true;
}
