package com.dhi.wha.server.Impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.dhi.wha.entity.Calendar;
import com.dhi.wha.mapper.CalendarMapper;
import com.dhi.wha.server.CalendarService;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.List;

@Service
public class CalendarServiceImpl extends ServiceImpl<CalendarMapper, Calendar>
        implements CalendarService {

    @Override
    public List<Calendar> listMonthCalendar(Long userId, Integer year, Integer month) {
        // 当月第一天 00:00:00
        LocalDate firstDay = LocalDate.of(year, month, 1);
        LocalDateTime start = LocalDateTime.of(firstDay, LocalTime.MIN);
        // 下一月第一天作为结束边界（不包含）
        LocalDate nextMonth = firstDay.plusMonths(1);
        LocalDateTime end = LocalDateTime.of(nextMonth, LocalTime.MIN);

        LambdaQueryWrapper<Calendar> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Calendar::getUserId, userId)
                .ge(Calendar::getDate, start)
                .lt(Calendar::getDate, end)
                .orderByAsc(Calendar::getDate);
        return list(wrapper);
    }

    @Override
    public void reviewCount(Long userId) {
        LocalDate today = LocalDate.now();
        LocalDateTime startOfDay = LocalDateTime.of(today, LocalTime.MIN);
        LocalDateTime endOfDay = LocalDateTime.of(today, LocalTime.MAX);

        LambdaQueryWrapper<Calendar> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Calendar::getUserId, userId)
                .ge(Calendar::getDate, startOfDay)
                .le(Calendar::getDate, endOfDay);

        Calendar calendar = getOne(wrapper);
        if (calendar != null) {
            calendar.setReviewCount(calendar.getReviewCount() + 1);
            updateById(calendar);
        }
    }
}
