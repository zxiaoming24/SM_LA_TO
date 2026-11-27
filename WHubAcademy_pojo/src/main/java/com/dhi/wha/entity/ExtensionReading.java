package com.dhi.wha.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("extension_reading")
public class ExtensionReading {
    /**
     * 主键ID
     */
    @TableId(type = IdType.AUTO)
    private Long id;
    /**
     * 用户ID（已加索引，查询飞快）
     */
    private Long userId;
    /**
     * 创建时间
     */
    private LocalDateTime createTime;
    /**
     * 状态 1-生成中 2-生成成功 3-生成失败
     */
    private Integer status;
    /**
     * 输入内容
     */
    private String text;
    /**
     * 标题
     */
    private String title;
    /**
     * 背景
     */
    private String background;
    /**
     * 知识点区分
     */
    private String knowledgeDistinguish;
    /**
     * 拓展原理
     */
    private String principleExtend;
    /**
     * 错误规避
     */
    private String mistakeAvoid;
    /**
     * 应用场景
     */
    private String applicationScene;
    /**
     * 个人建议
     */
    private String personalSuggest;

    private String resourceId;

    private String suggestionWarning;
}
