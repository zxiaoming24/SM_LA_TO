package com.dhi.wha.vo;

import lombok.Data;

import java.util.List;
import java.util.Map;

/**
 * 学习方案VO（当前选择的方案和方案列表）
 */
@Data
public class PlanVO {

    /**
     * 用户ID
     */
    private String userId;

    /**
     * 当前选择的方案ID
     */
    private String planId;

    /**
     * 所有方案列表
     */
    private List<Map<String, Object>> plans;
}
