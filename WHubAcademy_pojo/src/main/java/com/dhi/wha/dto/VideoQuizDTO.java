package com.dhi.wha.dto;

import lombok.Data;

@Data
public class VideoQuizDTO {
    /**
     * 用户ID
     */
    private String user_id;
    /**
     * 视频标题
     */
    private String video_title;
    /**
     * B站视频ID
     */
    private String bvid;
}
