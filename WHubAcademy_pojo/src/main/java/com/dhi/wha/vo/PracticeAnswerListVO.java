package com.dhi.wha.vo;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDateTime;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class PracticeAnswerListVO {
    /**
     * 主键id
     */
    private Long id;
    /**
     * 练习题ID
     */
    private Long practiceId;
    /**
     * 创建时间
     */
    private LocalDateTime createTime;
    /**
     * 状态 1-未完成 2-完成 3-失败
     */
    private Integer status;
    /**
     * 通过或失败
     */
    private String verdict;
    /**
     * 分数
     */
    private Integer score;
}
