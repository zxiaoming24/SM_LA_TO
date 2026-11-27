package com.dhi.wha.vo;

import lombok.Data;

@Data
public class MindMapVO {
    //思维导图id
    private Long id;
    //思维导图的基本信息
    private String text;
    //思维导图生成状态
    private Integer status;
    //思维导图生成时间
    private String createTime;
}
