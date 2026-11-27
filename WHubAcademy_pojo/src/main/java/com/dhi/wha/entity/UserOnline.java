package com.dhi.wha.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
@TableName("user_online")
public class UserOnline {
    /**
     * 主键ID
     */
    @TableId(type = IdType.AUTO)
    private Long id;
    /**
     * 用户ID
     */
    private Long userId;
    /**
     * 统计日期
     */
    private LocalDate statDate;
    /**
     * 首次登录时间
     */
    private LocalDateTime firstLogin;
    /**
     * 最后活跃时间
     */
    private LocalDateTime lastActive;
    /**
     * 在线时长（秒）
     */
    private Long totalSeconds;
}
