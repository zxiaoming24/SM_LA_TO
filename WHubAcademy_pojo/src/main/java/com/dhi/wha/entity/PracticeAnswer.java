package com.dhi.wha.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import net.sf.jsqlparser.expression.DateTimeLiteralExpression;

import java.time.LocalDateTime;
import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
@TableName(autoResultMap = true , value = "practice_answer")
public class PracticeAnswer {
    /**
     * 主键id
     */
    @TableId(type = IdType.AUTO)
    private Long id;
    /**
     * 编程练习题id
     */
    private Long practiceId;
    /**
     * 用户id
     */
    private Long userId;
    /**
     * 状态 1-提交中 2-提交成功 3-提交失败
     */
    private Integer status;
    /**
     * 答案 用户的代码
     */
    private String answer;
    /**
     * 分数
     */
    private Integer score;
    /**
     * 建议
     */
    @TableField(typeHandler = JacksonTypeHandler.class)
    private List<String> suggestion;
    /**
     * 结果 Accepted(通过)  WrongAnswer(错误)
     */
    private String verdict;
    /**
     * 通过的测试用例数
     */
    private Integer passedTests;
    /**
     * 总的测试用例数
     */
    private Integer totalTests;
    /**
     * 鼓励
     */
    private String encouragement;
    /**
     * 创建时间
     */
    private LocalDateTime createTime;
    /**
     * 语言
     */
    private String language;

    /**
     * 测试用例
     */
    @TableField(typeHandler = JacksonTypeHandler.class)
    private Question question;
    /**
     * 测试用例结果
     */
    private Integer submissionId;
}
