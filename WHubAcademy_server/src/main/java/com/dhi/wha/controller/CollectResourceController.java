package com.dhi.wha.controller;

import com.dhi.wha.result.Result;
import com.dhi.wha.server.CollectResourceService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@Slf4j
@RestController
public class CollectResourceController {

    @Autowired
    private CollectResourceService collectResourceService;

    /**
     * 收藏资源
     * @param request 收藏请求参数
     * @return 收藏结果
     */
    @PostMapping("/CollectResources")
    public Result<Object> collectResources(@RequestBody Map<String, Object> request) {
        log.info("收藏资源, request: {}", request);
        Object result = collectResourceService.collectResources(request);
        return Result.success(result);
    }

    /**
     * 取消收藏
     * @param request 取消收藏请求参数
     * @return 取消收藏结果
     */
    @PostMapping("/CancelCollect")
    public Result<Object> cancelCollect(@RequestBody Map<String, Object> request) {
        try {
            log.info("取消收藏, request: {}", request);
            Object result = collectResourceService.cancelCollect(request);
            return Result.success(result);
        } catch (Exception e) {
            log.error("取消收藏失败", e);
            return Result.error("取消收藏失败");
        }
    }

    /**
     * 获取收藏列表
     * @param userId 用户ID
     * @return 收藏列表
     */
    @GetMapping("/getCollectionList/{userId}")
    public Result<Object> getCollectionList(@PathVariable String userId) {
        log.info("获取收藏列表, userId: {}", userId);
        Object result = collectResourceService.getCollectionList(userId);
        return Result.success(result);
    }
}
