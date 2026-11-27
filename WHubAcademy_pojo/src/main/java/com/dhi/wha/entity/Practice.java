package com.dhi.wha.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("practice")
public class Practice {
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
     * 用户输入内容
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
    /**
     * 练习题目
     */
    private String title;
    /**
     * 难度
     */
    private String difficulty;
    /**
     * 描述
     */
    private String description;
    /**
     * 输入格式
     */
    private String inputFormat;
    /**
     * 输出格式
     */
    private String outputFormat;
    /**
     * 样例
     */
    @TableField(exist = false)
    private List<Example> examples;
    /**
     * 提示
     */
    @TableField(typeHandler = JacksonTypeHandler.class)
    private List<String> hints = new ArrayList<>();
    /**
     * 对应的知识点
     */
    @TableField(typeHandler = JacksonTypeHandler.class)
    private List<String> knowledgePoints = new ArrayList<>();
    /**
     * 对应的题目ID(python端的)
     */
    private String problemId;
    /**
     * 会话记录的id
     */
    private String sessionId;
    /**
     * 建议的提示
     */
    private String suggestionWarning;
}
