package com.dhi.wha.vo;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class PracticeVO {
    /**
     * 编程练习题id
     */
    private Long id;
    /**
     * 用户id
     */
    private Long userId;
    /**
     * 输入内容
     */
    private String text;
    /**
     * 创建时间
     */
    private LocalDateTime createTime;
    /**
     * 状态 1-生成中 2-生成成功 3-生成失败
     */
    private Integer status;
}
