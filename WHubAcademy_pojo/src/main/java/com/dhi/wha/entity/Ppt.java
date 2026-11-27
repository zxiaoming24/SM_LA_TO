package com.dhi.wha.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("ppt")
public class Ppt {
    // id
    @TableId(type = IdType.AUTO)
    private Long id;
    //用户ID
    private Long userId;
    //任务ID
    private String taskId;
    //首图
    @TableField(value = "image_url")
    private String imageUrl;
    //标题
    @TableField(value = "ppt_title")
    private String pptTitle;
    //页数
    @TableField(value = "page_count")
    private Integer pageCount;
    //创建时间
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    @TableField(value = "created_at")
    private String createdAt;
    //状态 1-生成中 2-生成成功 3-生成失败
    private Integer status;
    //OSS的文件地址url
    @TableField(value = "oss_url")
    private String  ossUrl;
    //预览地址
    @TableField(value = "preview_url")
    private String previewUrl;

    private String resourceId;

    private String suggestionWarning;
}
