package com.dhi.wha.dto;

import lombok.Data;

import java.util.List;

@Data
public class CommentPostDTO {
    private String userId;
    private String content;
    private String title;
    private String url;
    private Integer zone;
    private List<String> tags;
}
