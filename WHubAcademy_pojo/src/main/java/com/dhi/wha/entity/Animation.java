package com.dhi.wha.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;


@Data
@TableName("animation")
public class Animation {
    /**
     * 主键id
     */
    @TableId(type = IdType.AUTO)
    private Long id;
    /**
     * 用户id
     */
    private Long userId;
    /**
     * 状态
     */
    private Integer status;
    /**
     * 文本
     */
    private String text;
    /**
     * 创建时间
     */
    private LocalDateTime createTime;
    /**
     * html
     */
    private String html;

    private String resourceId;

    private String suggestionWarning;
}
