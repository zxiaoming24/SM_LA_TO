package com.dhi.wha.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("resource_click")
public class ResourceClick {
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
     * 资源类型: VIDEO/PRACTICE/PPT/MIND_MAP/READING/ANIMATION/WORD/PAPER
     */
    private String resourceType;
    /**
     * 资源ID
     */
    private Long resourceId;
    /**
     * 点击时间
     */
    private LocalDateTime clickTime;
}
