package com.dhi.wha.vo;


import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import com.dhi.wha.entity.Question;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;

@Data
public class PracticeAnswerVO {
    /**
     * 主键ID
     */
    private Long id;
    /**
     * 创建时间
     */
    private LocalDateTime createTime;
    /**
     * 状态 1-提交中 2-提交成功 3-提交失败
     */
    private Integer status;
    /**
     * 代码的测试结果
     */
    private String verdict;
    /**
     * 分数
     */
    private Integer score;
    /**
     * 通过的测试用例数
     */
    private Integer passedTests;
    /**
     * 总的测试用例数
     */
    private Integer totalTests;
    /**
     * 建议
     */
    private List<String> suggestion;
    /**
     * 鼓励
     */
    private String encouragement;
    /**
     * 语言
     */
    private String language;
    /**
     * 测试用例
     */
    @TableField(typeHandler = JacksonTypeHandler.class)
    private Question question;
}
