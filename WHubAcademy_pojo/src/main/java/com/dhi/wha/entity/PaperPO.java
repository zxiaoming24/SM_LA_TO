package com.dhi.wha.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("paper")
public class PaperPO {

    @TableId(type = IdType.AUTO)
    private Integer id;

    private Integer userId;

    private String paperName;

    private LocalDateTime createTime;

    private Integer status;

    private String resourceId;

    private String suggestionWarning;

    private String sessionId;
}
