package com.dhi.wha.vo;

import lombok.Data;

@Data
public class ChatResourceVO {
    private String id;
    private Integer status;
    private String text;
    private String createTime;
    private String suggestionWarning;
}
