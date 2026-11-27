package com.dhi.wha.controller;

import com.dhi.wha.dto.AdoptRouteDTO;
import com.dhi.wha.dto.EvaluateRouteDTO;
import com.dhi.wha.result.Result;
import com.dhi.wha.server.RouteMarketService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/channelMarket")
public class RouteMarketController {

    @Autowired
    private RouteMarketService routeMarketService;

    /**
     * 获取路径市场的分类
     * @return 封装后的分类数据
     */
    @GetMapping("/categories")
    public Result<Object> getCategories() {
        return routeMarketService.getCategories();
    }

    /**
     * 获取路径市场的列表
     * @param userId 用户id（必须）
     * @param sort 排序方式：hot热度，rating评分，new最新（非必须）
     * @param search 搜索内容（非必须）
     * @return 封装后的路径列表数据
     */
    @GetMapping("/getRouteList")
    public Result<Object> getRouteList(
            @RequestParam String userId,
            @RequestParam(required = false) String sort,
            @RequestParam(required = false) String search) {
        return routeMarketService.getRouteList(userId, sort, search);
    }

    /**
     * 获取路径市场的详情
     * @param routeId 路径id（必须）
     * @return 封装后的路径详情数据
     */
    @GetMapping("/getRouteDetail/{routeId}")
    public Result<Object> getRouteDetail(@PathVariable String routeId) {
        return routeMarketService.getRouteDetail(routeId);
    }

    /**
     * 采纳路径市场中的路径
     * @param routeId 路径id（必须）
     * @param adoptRouteDTO 采纳参数
     * @return 封装后的采纳结果数据
     */
    @PostMapping("/adoptRoute/{routeId}")
    public Result<Object> adoptRoute(
            @PathVariable String routeId,
            @RequestBody AdoptRouteDTO adoptRouteDTO) {
        return routeMarketService.adoptRoute(routeId, adoptRouteDTO);
    }

    /**
     * 获取路径市场中用户已采纳的路径
     * @param userId 用户id（必须）
     * @return 封装后的已采纳路径数据
     */
    @GetMapping("/getAdoptedRoutes/{userId}")
    public Result<Object> getAdoptedRoutes(@PathVariable String userId) {
        return routeMarketService.getAdoptedRoutes(userId);
    }

    /**
     * 用户对路径进行评价
     * @param routeId 路径id（必须）
     * @param evaluateRouteDTO 评价参数
     * @return 封装后的评价结果数据
     */
    @PostMapping("/evaluateRoute/{routeId}")
    public Result<Object> evaluateRoute(
            @PathVariable String routeId,
            @RequestBody EvaluateRouteDTO evaluateRouteDTO) {
        return routeMarketService.evaluateRoute(routeId, evaluateRouteDTO);
    }

    /**
     * 用户将自己的计划经过AI整理
     * @param requestData 请求数据
     * @return 封装后的AI整理结果数据
     */
    @PostMapping("/aiArrangeRoute")
    public Result<Object> aiArrangeRoute(@RequestBody Map<String, Object> requestData) {
        return routeMarketService.aiArrangeRoute(requestData);
    }

    /**
     * 将用户的路径发布到路径市场
     * @param requestData 请求数据
     * @return 封装后的发布结果数据
     */
    @PostMapping("/publishRouteToMarket")
    public Result<Object> publishRouteToMarket(@RequestBody Map<String, Object> requestData) {
        return routeMarketService.publishRouteToMarket(requestData);
    }

    /**
     * 删除路径市场中的路径（仅发布者可删）
     * @param routeId 路径id（必须）
     * @param userId 请求数据（包含user_id）
     * @return 封装后的删除结果数据
     */
    @DeleteMapping("/deleteRoute/{routeId}/{userId}")
    public Result<Object> deleteRoute(
            @PathVariable String routeId,
            @PathVariable String userId) {
        return routeMarketService.deleteRoute(routeId, userId);
    }

    /**
     * 编辑路径市场中的路径（仅发布者可编辑）
     * @param routeId 路径id（必须）
     * @param requestData 请求数据
     * @return 封装后的编辑结果数据
     */
    @PutMapping("/updateRoute/{routeId}")
    public Result<Object> updateRoute(
            @PathVariable String routeId,
            @RequestBody Map<String, Object> requestData) {
        return routeMarketService.updateRoute(routeId, requestData);
    }
}
