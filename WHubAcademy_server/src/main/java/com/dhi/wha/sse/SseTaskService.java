package com.dhi.wha.sse;

import com.dhi.wha.utils.AsyncUtil;
import com.dhi.wha.utils.PythonSseClient;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class SseTaskService {

    private final PythonSseClient pythonSseClient;
    private final ObjectMapper objectMapper;
    private final SseTaskRegistry taskRegistry;

    /**
     * 启动一个 SSE 任务（直接调用 Python POST 流接口）
     *
     * @param pythonUri        Python 流接口，如 "/test"
     * @param requestBody      发给 Python 的请求体参数
     * @param eventListeners   事件类型 → 监听器列表
     * @return runId
     */
    public String startTask(String pythonUri,
                            Map<String, Object> requestBody,
                            Map<String, List<SseEventListener>> eventListeners) {
        // 从请求体提取 run_id，若无则生成一个
        String runId = (String) requestBody.getOrDefault("run_id", UUID.randomUUID().toString());

        // 1. 创建引擎，注册监听器
        SseTaskEngine engine = new SseTaskEngine(runId, objectMapper);
        if (eventListeners != null) {
            eventListeners.forEach((eventType, listeners) ->
                    listeners.forEach(listener -> engine.registerListener(eventType, listener)));
        }
        taskRegistry.register(runId, engine);

        // 2. 异步调用 Python 流接口，将事件喂给引擎
        AsyncUtil.execute(() -> {
            try {
                pythonSseClient.consumePostSse(pythonUri, requestBody, engine::processEvent);
                // Python 流正常结束
                engine.complete();
            } catch (Exception e) {
                log.error("消费 Python SSE 流异常, runId={}", runId, e);
                engine.completeWithError(e);
            } finally {
                taskRegistry.remove(runId);
            }
        });

        return runId;
    }

    /**
     * 获取指定 runId 的 SseEmitter（供 Controller 返回给前端）
     */
    public SseEmitter getEmitter(String runId) {
        SseTaskEngine engine = taskRegistry.get(runId);
        return engine != null ? engine.getEmitter() : null;
    }
}
