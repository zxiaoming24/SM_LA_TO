package com.dhi.wha.server;

import com.baomidou.mybatisplus.extension.service.IService;
import com.dhi.wha.entity.UserOnline;
import java.util.List;

public interface UserOnlineService extends IService<UserOnline> {

    /**
     * 获取最近七天在线数据
     * @param userId
     * @return
     */
    List<UserOnline> getLast7DaysOnline(Long userId);

    /**
     * 获取用户昨日在线时长（秒）
     * @param userId 用户ID
     * @return 在线时长（秒），如果没有记录则返回0
     */
    Long getYesterdayOnlineDuration(Long userId);
}
