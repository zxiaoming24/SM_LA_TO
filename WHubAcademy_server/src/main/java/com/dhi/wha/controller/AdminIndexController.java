package com.dhi.wha.controller;

import com.dhi.wha.result.Result;
import com.dhi.wha.server.AdminIndexService;
import com.dhi.wha.vo.ResourceBasicInfoVO;
import com.dhi.wha.vo.ResourceClickVO;
import com.dhi.wha.vo.ResourceGenerationTrendVO;
import com.dhi.wha.vo.UserBasicInfoVO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@Slf4j
@RestController
@RequestMapping("/admin")
public class AdminIndexController {

    @Autowired
    private AdminIndexService adminIndexService;

    @GetMapping("/user/basicInfo")
    public Result<UserBasicInfoVO> getUserBasicInfo(){
        log.info("查询用户相关数据");
        UserBasicInfoVO basicInfo = adminIndexService.getUserBasicInfo();
        return Result.success(basicInfo);
    }

    @GetMapping("/resource/basicInfo")
    public Result<ResourceBasicInfoVO> getResourceBasicInfo(){
        log.info("查询资源相关数据");
        ResourceBasicInfoVO basicInfo = adminIndexService.getResourceBasicInfo();
        return Result.success(basicInfo);
    }

    @GetMapping("/popularResourcesRank")
    public Result<List<ResourceClickVO>> getPopularResourcesRank(){
        log.info("查询用户喜爱资源排行榜");
        List<ResourceClickVO> rank = adminIndexService.getPopularResourcesRank();
        return Result.success(rank);
    }

    @GetMapping("/resourceGenerationTrend/{rangeType}")
    public Result<ResourceGenerationTrendVO> getResourceGenerationTrend(@PathVariable String rangeType){
        log.info("查询资源生成趋势图数据, rangeType: {}", rangeType);
        ResourceGenerationTrendVO trend = adminIndexService.getResourceGenerationTrend(rangeType);
        return Result.success(trend);
    }
}
