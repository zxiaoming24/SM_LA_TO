package com.dhi.wha.vo;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class ExtensionReadingVO {
    private Long id;
    private Long userId;
    private String text;
    private LocalDateTime createTime;
    private Integer status;
}
