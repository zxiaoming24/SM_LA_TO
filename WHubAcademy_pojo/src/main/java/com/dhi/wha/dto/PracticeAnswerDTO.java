package com.dhi.wha.dto;

import lombok.Data;

@Data
public class PracticeAnswerDTO {
    /**
     * 用户id
     */
    private Long userId;
    /**
     * 编程练习题id
     */
    private Long practiceId;
    /**
     * 答案 用户的代码
     */
    private String answer;
    /**
     * 语言类型，也就是用户用了哪种语言。
     */
    private String language;
    /**
     * python中的recordId
     */
    private String recordId;
}
