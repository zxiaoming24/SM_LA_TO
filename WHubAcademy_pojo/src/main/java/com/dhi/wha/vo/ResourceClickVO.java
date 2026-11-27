package com.dhi.wha.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ResourceClickVO {
    /**
     * 资源类型
     */
    private String resourceType;
    /**
     * 点击次数
     */
    private Long clickCount;
    /**
     * 占比（百分比）
     */
    private Double percentage;
}
