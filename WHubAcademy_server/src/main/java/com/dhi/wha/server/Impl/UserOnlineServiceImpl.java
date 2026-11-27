package com.dhi.wha.server.Impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.dhi.wha.entity.Calendar;
import com.dhi.wha.entity.UserOnline;
import com.dhi.wha.mapper.UserOnlineMapper;
import com.dhi.wha.server.CalendarService;
import com.dhi.wha.server.UserOnlineService;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Service
public class UserOnlineServiceImpl extends ServiceImpl<UserOnlineMapper, UserOnline> implements UserOnlineService {

    @Resource
    private CalendarService calendarService;


    /**
     * 查询用户近7天的在线时长
     * 如果某天没有数据，返回该天学习时长为0的记录，保证返回7条数据
     */
    @Override
    public List<UserOnline> getLast7DaysOnline(Long userId) {
        LocalDate today = LocalDate.now();
        LocalDate sevenDaysAgo = today.minusDays(6); // 近7天

        LambdaQueryWrapper<UserOnline> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(UserOnline::getUserId, userId)
                .ge(UserOnline::getStatDate, sevenDaysAgo)
                .le(UserOnline::getStatDate, today)
                .orderByAsc(UserOnline::getStatDate);

        List<UserOnline> dbList = this.list(wrapper);

        // 将数据库查询结果按日期映射，方便查找
        Map<LocalDate, UserOnline> dateMap = new HashMap<>();
        if (dbList != null) {
            for (UserOnline online : dbList) {
                if (online.getStatDate() != null) {
                    dateMap.put(online.getStatDate(), online);
                }
            }
        }

        // 遍历近7天，补齐缺失的日期（学习时长为0）
        List<UserOnline> result = new ArrayList<>();
        for (int i = 0; i < 7; i++) {
            LocalDate date = sevenDaysAgo.plusDays(i);
            UserOnline online = dateMap.get(date);
            if (online == null) {
                // 该天无数据，构造一条时长为0的记录
                online = new UserOnline();
                online.setUserId(userId);
                online.setStatDate(date);
                online.setTotalSeconds(0L);
                online.setFirstLogin(date.atStartOfDay());
                online.setLastActive(date.atStartOfDay());
            }
            result.add(online);
        }

        return result;
    }

    @Override
    public Long getYesterdayOnlineDuration(Long userId) {
        LocalDate yesterday = LocalDate.now().minusDays(1);

        LambdaQueryWrapper<UserOnline> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(UserOnline::getUserId, userId)
                .eq(UserOnline::getStatDate, yesterday);

        UserOnline userOnline = this.getOne(wrapper);
        return userOnline != null ? userOnline.getTotalSeconds() : 0L;
    }


    // ========== 重写新增、更新，后置同步日历 ==========
    @Override
    public boolean save(UserOnline entity) {
        boolean success = super.save(entity);
        if (success) {
            syncToCalendar(entity);
        }
        return success;
    }

    @Override
    public boolean updateById(UserOnline entity) {
        boolean success = super.updateById(entity);
        if (success) {
            syncToCalendar(entity);
        }
        return success;
    }

    /**
     * 同步单条UserOnline数据到calendar日历表
     */
    private void syncToCalendar(UserOnline online) {
        Long userId = online.getUserId();
        LocalDate statDate = online.getStatDate();
        LocalDateTime dayStart = LocalDateTime.of(statDate, LocalTime.MIN);

        // 查询用户当日日历记录
        Calendar existCalendar = calendarService.lambdaQuery()
                .eq(Calendar::getUserId, userId)
                .eq(Calendar::getDate, dayStart)
                .one();

        Calendar calendar = Optional.ofNullable(existCalendar).orElse(new Calendar());
        calendar.setUserId(userId);
        calendar.setDate(dayStart);

        // 首次登录：保留更早时间
        if (existCalendar == null || online.getFirstLogin().isBefore(existCalendar.getFirstLogin())) {
            calendar.setFirstLogin(online.getFirstLogin());
        } else {
            calendar.setFirstLogin(existCalendar.getFirstLogin());
        }

        // 最后活跃：保留更晚时间
        if (existCalendar == null || online.getLastActive().isAfter(existCalendar.getLastActive())) {
            calendar.setLastActive(online.getLastActive());
        } else {
            calendar.setLastActive(existCalendar.getLastActive());
        }

        // 在线总时长
        calendar.setTotalSeconds(online.getTotalSeconds().intValue());

        // 复习次数不受在线同步影响，保留原有值
        if (existCalendar != null) {
            calendar.setReviewCount(existCalendar.getReviewCount());
        } else {
            calendar.setReviewCount(0);
        }

        // 存在更新，不存在新增
        calendarService.saveOrUpdate(calendar);
    }
}
