package com.dhi.wha.vo;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class VideoVO {
    /**
     * 视频ID
     */
    private Long id;
    /**
     * 用户输入
     */
    private String text;
    /**
     * 创建时间
     */
    private LocalDateTime createTime;
    /**
     * 状态 1-进行中 2-已完成 3-失败
     */
    private Integer status;
    /**
     * 批处理ID
     */
    private String batchId;

}
