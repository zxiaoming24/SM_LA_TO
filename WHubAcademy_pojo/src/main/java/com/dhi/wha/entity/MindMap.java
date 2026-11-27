package com.dhi.wha.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("mind_map")
public class MindMap {
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
     * 状态 1=正常 0=生成失败
     */
    private Integer status;

    /**
     * 思维导图标题
     */
    private String text;

    /**
     * 创建时间
     */
    private LocalDateTime createTime;

    /**
     * 思维导图JSON数据（前端直接渲染）
     */
    private String value;

    private String resourceId;

    private String suggestionWarning;
}
