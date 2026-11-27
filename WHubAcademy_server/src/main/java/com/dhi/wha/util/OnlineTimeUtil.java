package com.dhi.wha.util;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.dhi.wha.entity.UserOnline;
import com.dhi.wha.server.UserOnlineService;
import org.springframework.stereotype.Component;
import javax.annotation.Resource;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;

@Component
public class OnlineTimeUtil {

    // 替换Mapper为Service
    @Resource
    private UserOnlineService userOnlineService;

    /**
     * 记录用户在线时长（以秒为单位累加）
     */
    public void recordActive(Long userId) {
        if (userId == null) return;

        LocalDate today = LocalDate.now();
        LocalDateTime now = LocalDateTime.now();

        // 查询今天的记录
        LambdaQueryWrapper<UserOnline> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(UserOnline::getUserId, userId);
        wrapper.eq(UserOnline::getStatDate, today);
        UserOnline online = userOnlineService.getOne(wrapper);

        if (online == null) {
            // 第一次访问：新建记录，调用service.save自动同步日历
            UserOnline newRecord = new UserOnline();
            newRecord.setUserId(userId);
            newRecord.setStatDate(today);
            newRecord.setFirstLogin(now);
            newRecord.setLastActive(now);
            newRecord.setTotalSeconds(0L);
            userOnlineService.save(newRecord);
        } else {
            // 计算间隔秒数
            long seconds = ChronoUnit.SECONDS.between(online.getLastActive(), now);
            if (seconds <= 0) return;

            // 累加秒数
            long totalSeconds = online.getTotalSeconds() + seconds;
            online.setTotalSeconds(totalSeconds);
            online.setLastActive(now);
            // 调用service.updateById自动同步日历
            userOnlineService.updateById(online);
        }
    }
}