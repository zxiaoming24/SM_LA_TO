package com.dhi.wha.controller;

import com.dhi.wha.result.Result;
import com.dhi.wha.server.SseConnectionService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.HashMap;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/sse")
public class SseConnectionController {

    @Autowired
    private SseConnectionService sseConnectionService;

    /**
     * 建立 SSE 连接
     *
     * @param userId 用户唯一标识
     * @return SseEmitter 事件流
     */
    @GetMapping(value = "/connect/{userId}")
    public SseEmitter connect(@PathVariable String userId) {
        log.info("建立 SSE 连接, userId={}", userId);
        return sseConnectionService.connect(userId);
    }

    /**
     * 断开 SSE 连接
     *
     * @param userId 用户唯一标识
     * @return 断开结果
     */
    @DeleteMapping("/disconnect/{userId}")
    public Result<Map<String, Object>> disconnect(
            @PathVariable String userId
    ) {
        try {
            log.info("断开 SSE 连接, userId={}", userId);

            Map<String, Object> data = new HashMap<>();
            data.put("userId", userId);
            data.put("timestamp", System.currentTimeMillis());

            if (!sseConnectionService.isConnected(userId)) {
                data.put("success", false);
                return Result.error("用户未连接");
            }

            sseConnectionService.disconnect(userId);
            data.put("success", true);
            return Result.success(data);
        } catch (Exception e) {
            log.error("断开 SSE 连接失败, userId={},", userId, e);
            return Result.error("断开连接失败");
        }
    }
}