package com.dhi.wha.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("single_choice")
public class SingleChoicePO {

    @TableId(type = IdType.AUTO)
    private Integer id;

    private Integer paperId;

    private String question;

    private String optionA;
    private String optionB;
    private String optionC;
    private String optionD;

    private String answer;
}
