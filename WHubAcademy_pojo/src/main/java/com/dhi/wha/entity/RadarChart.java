package com.dhi.wha.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import lombok.Data;
import java.util.Arrays;
import java.util.List;

@Data
@TableName("radar_chart")
public class RadarChart {

    @TableId(type = IdType.AUTO)
    private Long id;

    // 自动 List <-> JSON 互转
    @TableField(typeHandler = JacksonTypeHandler.class)
    private List<Integer> preData = Arrays.asList(0, 0, 0, 0, 0, 0, 0, 0);

    @TableField(typeHandler = JacksonTypeHandler.class)
    private List<Integer> curData = Arrays.asList(0, 0, 0, 0, 0, 0, 0, 0);
}