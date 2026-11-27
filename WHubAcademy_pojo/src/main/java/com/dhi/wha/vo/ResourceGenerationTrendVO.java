package com.dhi.wha.vo;

import lombok.Data;

import java.util.List;

@Data
public class ResourceGenerationTrendVO {
    private RangeInfo rangeInfo;
    private ChartData chartData;
    private Summary summary;
    private ExtraInfo extraInfo;

    @Data
    public static class RangeInfo {
        private String type;
        private String startDate;
        private String endDate;
        private Integer totalDays;
    }

    @Data
    public static class ChartData {
        private List<String> dates;
        private List<Long> values;
        private List<Long> cumulativeValues;
    }

    @Data
    public static class Summary {
        private Long total;
        private Double avg;
        private Long max;
        private Long min;
        private Double growthRate;
    }

    @Data
    public static class ExtraInfo {
        private Integer weekNumber;
        private Integer year;
        private String monthRange;
        private String peakDay;
        private Long peakValue;
        private String yearRange;
        private String peakMonth;
        private Double monthlyAvg;
    }
}
