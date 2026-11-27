package com.dhi.wha.vo;

import lombok.Data;

import java.util.List;

@Data
public class RadarChartVO {
    private List<Integer> value;
    private String name;
}
