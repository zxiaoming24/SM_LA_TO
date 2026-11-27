package com.dhi.wha.server;

import java.util.Map;

public interface CollectResourceService {
    /**
     * 收藏资源
     * @param request 收藏请求参数
     * @return 收藏结果
     */
    Object collectResources(Map<String, Object> request);

    /**
     * 取消收藏
     * @param request 取消收藏请求参数
     * @return 取消收藏结果
     */
    Object cancelCollect(Map<String, Object> request);

    /**
     * 获取收藏列表
     * @param userId 用户ID
     * @return 收藏列表
     */
    Object getCollectionList(String userId);
}
