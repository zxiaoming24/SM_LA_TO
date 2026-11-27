package com.dhi.wha.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("word")
public class Word {
    // id
    @TableId(type = IdType.AUTO)
    private Long id;
    // userId
    private Long userId;
    // 文档内容
    private String longText;
    // 文档生成文本
    private String text;
    // 文档的创建时间
    private LocalDateTime createTime;
    // 文档生成状态
    private Integer status;
    // 文档的默认图片
    private String image;
    // 文档的OSS存储路径
    private String ossUrl;
    // 文档的Python端的id
    private String resourceId;
    private String suggestionWarning;
}