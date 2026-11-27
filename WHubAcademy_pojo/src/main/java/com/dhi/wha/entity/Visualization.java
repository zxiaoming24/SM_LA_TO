package com.dhi.wha.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("visualization")
public class Visualization {
    // 可视化id
    @TableId(type = IdType.AUTO)
    private Long id;
    // 历史记录id
    private Long historyId;
    // 对应的代码
    private String code;
    // 可视化的类型
    private String detectedType;
    // 原先的代码
    private String originalCode;
    // 用户的编译语言
    private String language;
}
