package com.dhi.wha.dto;

import lombok.Data;

@Data
public class CommentDTO {
    private String content;
    private String url;
    private String userId;
    private String postId;
    private String parentReplyId;
}
