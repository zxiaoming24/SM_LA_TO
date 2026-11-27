package com.dhi.wha.controller;

import com.dhi.wha.result.Result;
import com.dhi.wha.server.RadarChartService;
import com.dhi.wha.vo.RadarChartVO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/draw")
public class RadarChartController {

    @Autowired
    private RadarChartService radarChartService;


    /**
     * 获取雷达图数据
     * @param userId
     * @return
     */
    @GetMapping("/radarMap/{userId}")
    public Result<Object> getRadarChartData(@PathVariable Long userId){
        log.info("获取雷达图数据");
        List<RadarChartVO> radarChartVOList = radarChartService.getRadarChartData(userId);
        return Result.success(radarChartVOList);
    }

    /**
     * 查询资源总量信息
     * @param userId
     * @return 资源总量列表 [ppt, 思维导图, 讲解文档, 拓展阅读, 编程题, 视频, 动画, 试卷, 学习计划]
     */
    @GetMapping("/rsAllMsg/{userId}")
    public Result<Object> getResourceTotalCount(@PathVariable Long userId){
        log.info("查询资源总量信息, userId: {}", userId);
        List<Integer> resourceCounts = radarChartService.getResourceTotalCount(userId);
        return Result.success(resourceCounts);
    }

    /**
     * 查询学习计划进度信息
     * @param userId
     * @return 学习计划进度列表
     */
    @GetMapping("/planProgressMsg/{userId}")
    public Result<Object> getPlanProgressMsg(@PathVariable Long userId){
        log.info("查询学习计划进度信息, userId: {}", userId);
        List<Map<String, Object>> planProgressList = radarChartService.getPlanProgressMsg(userId);
        return Result.success(planProgressList);
    }

}
