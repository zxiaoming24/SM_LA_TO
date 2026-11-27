package com.dhi.wha.sse;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.*;

@Slf4j
public class SseTaskEngine {

    private final String runId;
    private final ObjectMapper objectMapper;
    private final SseEmitter emitter;
    private final Map<String, List<SseEventListener>> listeners = new HashMap<>();

    public SseTaskEngine(String runId, ObjectMapper objectMapper) {
        this.runId = runId;
        this.objectMapper = objectMapper;
        this.emitter = new SseEmitter(0L); // 无超时
        emitter.onCompletion(() -> log.info("SSE 连接完成, runId={}", runId));
        emitter.onTimeout(() -> log.warn("SSE 连接超时, runId={}", runId));
        emitter.onError(e -> log.error("SSE 连接异常, runId={}", runId, e));
    }

    /**
     * 注册一个监听器到指定事件类型
     */
    public void registerListener(String eventType, SseEventListener listener) {
        listeners.computeIfAbsent(eventType, k -> new ArrayList<>()).add(listener);
    }

    /**
     * 处理一条从 Python 来的 SSE 事件（由外部调用）
     */
    public void processEvent(String jsonData) {
        try {
            JsonNode root = objectMapper.readTree(jsonData);
            String eventType = root.path("type").asText("");

            // 1. 转发给前端
            sendToClient(eventType, jsonData);

            // 2. 通知所有监听该事件类型的监听器
            List<SseEventListener> list = listeners.get(eventType);
            if (list != null) {
                for (SseEventListener listener : list) {
                    listener.onEvent(runId, eventType, root);
                }
            }
        } catch (Exception e) {
            log.error("处理 SSE 事件失败, runId={}, data={}", runId, jsonData, e);
        }
    }

    private void sendToClient(String eventType, String jsonData) {
        try {
            emitter.send(SseEmitter.event()
                    .id(UUID.randomUUID().toString())
                    .name(eventType)
                    .data(jsonData, MediaType.APPLICATION_JSON));
        } catch (Exception e) {
            log.error("向前端发送 SSE 失败, runId={}", runId, e);
        }
    }

    public SseEmitter getEmitter() {
        return emitter;
    }

    /**
     * 正常结束 SSE
     */
    public void complete() {
        try {
            emitter.complete();
        } catch (Exception ignored) {}
    }

    /**
     * 异常结束 SSE
     */
    public void completeWithError(Throwable e) {
        try {
            emitter.completeWithError(e);
        } catch (Exception ignored) {}
    }
}
