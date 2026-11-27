package com.dhi.wha.dto;

import lombok.Data;

@Data
public class WordDTO {
    //用户id
    private Long userId;
    //文档生成文本
    private String text;
}
