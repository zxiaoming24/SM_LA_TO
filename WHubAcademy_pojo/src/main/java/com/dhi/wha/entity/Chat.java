package com.dhi.wha.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Data
@TableName("chat")
public class Chat {
    @TableId(type = IdType.AUTO)
    private Long id;
    private Long userId;
    private String taskId;
    private String type;
    private String content;
    private Integer status;
    private Integer rsType;
    // 新增：整条resource json存在这里
    @TableField(typeHandler = JacksonTypeHandler.class)
    private Map<String,Object> resource;
    private LocalDateTime createTime;
    @TableField(value = "is_batch_generate")
    private Boolean isBatchGenerate;
}
