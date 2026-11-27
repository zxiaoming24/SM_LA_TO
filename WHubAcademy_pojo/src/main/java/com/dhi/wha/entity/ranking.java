package com.dhi.wha.entity;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class ranking {
    /**
     * 排行榜
     */
    private Long userId;
    /**
     * 用户名
     */
    private String username;
    /**
     * 分数
     */
    private Integer score;
    /**
     * 头像
     */
    private String avatar;
    /**
     * 代码预览
     */
    private String codePreview;
    /**
     * 创建时间
     */
    private LocalDateTime createTime;
    /**
     * 提交代码的id
     */
    private Integer submissionId;
}
