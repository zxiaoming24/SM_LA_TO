package com.dhi.wha.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("calendar")
public class Calendar {
    // id
    @TableId(type = IdType.AUTO)
    private Long id;
    // 用户id
    private Long userId;
    // 日期
    private LocalDateTime date;
    // 首次登录时间
    private LocalDateTime firstLogin;
    // 最后活跃时间
    private LocalDateTime lastActive;
    // 总时长 秒
    private Integer totalSeconds;
    // 复习次数
    private Integer reviewCount;
}
