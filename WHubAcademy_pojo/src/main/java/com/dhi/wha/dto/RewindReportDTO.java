package com.dhi.wha.dto;

import lombok.Data;

@Data
public class RewindReportDTO {
    private String userId;
    private String bvid;
    private String videoTitle;
    private Double rewindFrom;
    private Double rewindTo;
    private Integer rewindGap;
    private Boolean isConfused;
}