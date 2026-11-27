package com.dhi.wha.dto;

import lombok.Data;
import java.io.Serializable;

@Data
public class ChatQueryDTO implements Serializable {
    // 必传：当前用户ID
    private Long userId;
    // 游标：上一页最后一条chat的id，首次不传null
    private Long lastId;
    // 固定每页20条
    private final Integer pageSize = 10;
}
