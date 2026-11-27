package com.dhi.wha.controller;

import com.dhi.wha.entity.Calendar;
import com.dhi.wha.result.Result;
import com.dhi.wha.server.CalendarService;
import com.dhi.wha.vo.CalendarVO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import javax.annotation.Resource;
import java.util.List;
import java.util.stream.Collectors;

@Slf4j
@RestController
@RequestMapping("/draw")
public class CalendarController {
    @Resource
    private CalendarService calendarService;

    /**
     * 10.4 查询某年某月日历图学习信息
     * GET /draw/calendarChartData/{userId}/{year}/{month}
     */
    @GetMapping("/calendarChartData/{userId}/{year}/{month}")
    public Result<List<CalendarVO>> calendarChartData(
            @PathVariable Long userId,
            @PathVariable Integer year,
            @PathVariable Integer month
    ) {
        List<Calendar> calendarList = calendarService.listMonthCalendar(userId, year, month);
        // 实体转VO格式化时间
        List<CalendarVO> voList = calendarList.stream()
                .map(CalendarVO::convert)
                .collect(Collectors.toList());
        return Result.success(voList);
    }

    @PutMapping("/review/{userId}")
    public Result<Object> reviewCount(@PathVariable Long userId){
        log.info("复习次数统计, userId: {}", userId);
        calendarService.reviewCount(userId);
        return Result.success();
    }
}
