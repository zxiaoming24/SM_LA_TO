package com.dhi.wha.vo;

import lombok.Data;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

@Data
public class CalendarVO {
    private Long id;
    private Long userId;
    private String date;
    private String firstLogin;
    private String lastActive;
    private Integer totalSeconds;
    private Integer reviewCount;

    private static final DateTimeFormatter DAY_FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd");
    private static final DateTimeFormatter DATETIME_FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");

    public static CalendarVO convert(com.dhi.wha.entity.Calendar calendar) {
        CalendarVO vo = new CalendarVO();
        vo.setId(calendar.getId());
        vo.setUserId(calendar.getUserId());
        vo.setDate(calendar.getDate().toLocalDate().format(DAY_FMT));
        vo.setFirstLogin(calendar.getFirstLogin().format(DATETIME_FMT));
        vo.setLastActive(calendar.getLastActive().format(DATETIME_FMT));
        vo.setTotalSeconds(calendar.getTotalSeconds());
        vo.setReviewCount(calendar.getReviewCount());
        return vo;
    }
}
