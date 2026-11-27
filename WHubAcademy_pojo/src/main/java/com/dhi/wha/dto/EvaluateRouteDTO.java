package com.dhi.wha.dto;

import lombok.Data;

@Data
public class EvaluateRouteDTO {
    private String user_id;
    private int rating;
    private String comment;
}