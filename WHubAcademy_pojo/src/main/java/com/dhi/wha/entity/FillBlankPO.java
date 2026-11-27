package com.dhi.wha.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("fill_blank")
public class FillBlankPO {

    @TableId(type = IdType.AUTO)
    private Integer id;

    private Integer paperId;

    private String question;

    private String answer;
}
