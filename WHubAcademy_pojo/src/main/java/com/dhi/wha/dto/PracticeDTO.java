package com.dhi.wha.dto;

import lombok.Data;

@Data
public class PracticeDTO {
    // 用户ID
    private Long userId;
    // 编程练习题的用户输入
    private String text;
}
