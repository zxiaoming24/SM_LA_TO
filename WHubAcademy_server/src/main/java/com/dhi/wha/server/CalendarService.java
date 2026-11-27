package com.dhi.wha.server;

import com.baomidou.mybatisplus.extension.service.IService;
import com.dhi.wha.entity.Calendar;

import java.util.List;

public interface CalendarService extends IService<Calendar> {
    /**
     * 根据用户id、年月查询当月日历学习记录
     */
    List<Calendar> listMonthCalendar(Long userId, Integer year, Integer month);

    /**
     *  获取某年某月某日学习记录
     */
    void reviewCount(Long userId);
}
