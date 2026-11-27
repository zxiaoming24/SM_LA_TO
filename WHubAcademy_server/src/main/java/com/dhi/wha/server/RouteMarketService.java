package com.dhi.wha.server;

import com.dhi.wha.dto.AdoptRouteDTO;
import com.dhi.wha.dto.EvaluateRouteDTO;
import com.dhi.wha.result.Result;

import java.util.Map;

public interface RouteMarketService {

    /**
     * 获取路径市场的分类
     * @return 封装后的分类数据
     */
    Result<Object> getCategories();

    /**
     * 获取路径市场的列表
     * @param userId 用户id
     * @param sort 排序方式：hot热度，rating评分，new最新
     * @param search 搜索内容
     * @return 封装后的路径列表数据
     */
    Result<Object> getRouteList(String userId, String sort, String search);

    /**
     * 获取路径市场的详情
     * @param routeId 路径id
     * @return 封装后的路径详情数据
     */
    Result<Object> getRouteDetail(String routeId);

    /**
     * 采纳路径市场中的路径
     * @param routeId 路径id
     * @param adoptRouteDTO 采纳参数
     * @return 封装后的采纳结果数据
     */
    Result<Object> adoptRoute(String routeId, AdoptRouteDTO adoptRouteDTO);

    /**
     * 获取路径市场中用户已采纳的路径
     * @param userId 用户id
     * @return 封装后的已采纳路径数据
     */
    Result<Object> getAdoptedRoutes(String userId);

    /**
     * 用户对路径进行评价
     * @param routeId 路径id
     * @param evaluateRouteDTO 评价参数
     * @return 封装后的评价结果数据
     */
    Result<Object> evaluateRoute(String routeId, EvaluateRouteDTO evaluateRouteDTO);

    /**
     * 用户将自己的计划经过AI整理
     * @param requestData 请求数据
     * @return 封装后的AI整理结果数据
     */
    Result<Object> aiArrangeRoute(Map<String, Object> requestData);

    /**
     * 将用户的路径发布到路径市场
     * @param requestData 请求数据
     * @return 封装后的发布结果数据
     */
    Result<Object> publishRouteToMarket(Map<String, Object> requestData);

    /**
     * 删除路径市场中的路径
     * @param routeId 路径id
     * @param userId 请求数据（包含user_id）
     * @return 封装后的删除结果数据
     */
    Result<Object> deleteRoute(String routeId, String userId);

    /**
     * 编辑路径市场中的路径（仅发布者可编辑）
     * @param routeId 路径id
     * @param requestData 请求数据
     * @return 封装后的编辑结果数据
     */
    Result<Object> updateRoute(String routeId, Map<String, Object> requestData);
}
