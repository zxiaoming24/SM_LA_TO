package com.dhi.wha.server;

import com.baomidou.mybatisplus.extension.service.IService;
import com.dhi.wha.entity.RadarChart;
import com.dhi.wha.vo.RadarChartVO;

import java.util.List;
import java.util.Map;

public interface RadarChartService extends IService<RadarChart> {
    /**
     * 获取雷达图数据
     * @param userId
     * @return
     */
    List<RadarChartVO> getRadarChartData(Long userId);

    /**
     * 查询资源总量信息
     * @param userId
     * @return 资源总量列表 [ppt, 思维导图, 讲解文档, 拓展阅读, 编程题, 视频, 动画, 试卷, 学习计划]
     */
    List<Integer> getResourceTotalCount(Long userId);

    /**
     * 查询学习计划进度信息
     * @param userId
     * @return 学习计划进度列表
     */
    List<Map<String, Object>> getPlanProgressMsg(Long userId);
}