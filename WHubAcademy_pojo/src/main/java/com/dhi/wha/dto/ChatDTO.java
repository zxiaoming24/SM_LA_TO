package com.dhi.wha.dto;

import lombok.Data;

import java.util.List;

@Data
public class ChatDTO {
    private Long userId;
    private String text;
    private Integer rsType;
    private String sessionId;
    //超级智能体时传入，包含资源类型列表（0ppt,1思维导图,2讲解文档,3拓展阅读,4编程题,5视频,6动画,7非编程题,8学习计划）
    private List<Integer> rsArray;
}
