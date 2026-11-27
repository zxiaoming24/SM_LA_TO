package com.dhi.wha.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Builder;
import lombok.Data;

@Data
@Builder
@TableName("example")
public class Example {
    /**
     * 主键ID
     */
    @TableId(type = IdType.AUTO)
    private Long id;
    /**
     * 练习ID
     */
    private Long practiceId;
    /**
     * 输入
     */
    private String input;
    /**
     * 输出
     */
    private String output;
    /**
     * 解释说明
     */
    private String explanation;
}
