package com.dhi.wha.dto;

import lombok.Data;

@Data
public class CompareDTO {
    /**
     * 编程练习题id
     */
    private Long practiceId;
    /**
     * A用户提交记录id
     */
    private Long submissionAId;
    /**
     * B用户提交记录id
     */
    private Long submissionBId;
}
