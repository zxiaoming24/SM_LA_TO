package com.dhi.wha.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("video")
public class Video {
    // 视频id
    @TableId(type = IdType.AUTO)
    private Long id;
    // 状态 1-查询中 2-成功  3-失败
    private Integer status;
    // 用户id
    private Long userId;
    // 用户输入的文本
    private String text;
    // 创建时间
    private LocalDateTime createTime;
    // 标题
    private String title;
    // 视频链接
    private String url;
    // 封面图片链接
    private String thumbnail;
    // 时长
    private String duration;
    // 作者
    private String author;
    // 播放次数
    private String playCount;
    // 描述
    private String description;
    // 同一次搜索的批次ID，用于前端轮询分组查询
    private String batchId;
    // python端的id
    private String resourceId;
    // 提示
    private String suggestionWarning;
}
