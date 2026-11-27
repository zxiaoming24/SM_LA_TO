package com.dhi.wha.dto;


import lombok.Data;
import java.util.List;

@Data
public class VideoWatchDTO {
    private String userId;
    private VideoInfoDTO videoInfo;
    private WatchDataDTO watchData;

    @Data
    public static class VideoInfoDTO {
        private String title;
        private String author;
        private String url;
        private String bvid;
    }

    @Data
    public static class WatchDataDTO {
        private String watchDuration;
        private String totalDuration;
        private String completionRate;
        private Integer pauseCount;
        private Integer rewindCount;
        private List<RewindEventDTO> rewindEvents;
        private EngagementSignalsDTO engagementSignals;
    }

    @Data
    public static class RewindEventDTO {
        private Integer from;
        private Integer to;
        private String time;
    }

    @Data
    public static class EngagementSignalsDTO {
        private Integer significantRewinds;
        private Integer totalRewinds;
        private Boolean userActive;
        private String watchProgress;
    }
}
