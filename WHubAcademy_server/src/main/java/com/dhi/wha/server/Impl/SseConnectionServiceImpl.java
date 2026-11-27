package com.dhi.wha.server.Impl;

import com.dhi.wha.server.SseConnectionService;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Slf4j
@Service
public class SseConnectionServiceImpl implements SseConnectionService {

    @Autowired
    private ObjectMapper objectMapper;

    /**
     * 存储所有用户的 SSE 连接
     */
    private final Map<String, SseEmitter> emitterMap = new ConcurrentHashMap<>();

    @Override
    public SseEmitter connect(String userId) {
        if (userId == null || userId.isEmpty()) {
            throw new IllegalArgumentException("userId 不能为空");
        }

        // 如果该用户已有连接，先关闭旧连接
        disconnect(userId);

        // 创建新的 SseEmitter，设置超时时间为0（不超时）
        SseEmitter emitter = new SseEmitter(0L);

        // 注册回调
        emitter.onCompletion(() -> {
            log.info("SSE 连接完成, userId={}", userId);
            emitterMap.remove(userId);
        });
        emitter.onTimeout(() -> {
            log.warn("SSE 连接超时, userId={}", userId);
            emitterMap.remove(userId);
        });
        emitter.onError(e -> {
            log.error("SSE 连接异常, userId={}", userId, e);
            emitterMap.remove(userId);
        });

        emitterMap.put(userId, emitter);
        log.info("SSE 连接建立, userId={}", userId);

        // 发送连接成功事件
        try {
            Map<String, Object> connectionEvent = new HashMap<>();
            connectionEvent.put("type", "connection");
            connectionEvent.put("userId", userId);
            connectionEvent.put("status", "connected");
            connectionEvent.put("success", true);
            connectionEvent.put("timestamp", System.currentTimeMillis());

            String jsonData = objectMapper.writeValueAsString(connectionEvent);
            emitter.send(SseEmitter.event()
                    .name("connection")
                    .data(jsonData, MediaType.APPLICATION_JSON));
        } catch (IOException e) {
            log.error("发送连接成功事件失败, userId={}", userId, e);
            emitterMap.remove(userId);
            throw new RuntimeException("发送连接事件失败", e);
        }

        return emitter;
    }

    @Override
    public void sendMessage(String userId, String eventType, String data) {
        if (userId == null || userId.isEmpty()) {
            log.warn("发送消息失败: userId 为空");
            return;
        }

        SseEmitter emitter = emitterMap.get(userId);
        if (emitter == null) {
            log.warn("用户未建立 SSE 连接, userId={}", userId);
            return;
        }

        try {
            emitter.send(SseEmitter.event()
                    .name(eventType)
                    .data(data, MediaType.APPLICATION_JSON));
            log.debug("SSE 消息发送成功, userId={}, eventType={}", userId, eventType);
        } catch (IOException e) {
            log.error("SSE 消息发送失败, userId={}, eventType={}", userId, eventType, e);
            emitterMap.remove(userId);
        }
    }

    @Override
    public void disconnect(String userId) {
        if (userId == null || userId.isEmpty()) {
            return;
        }

        SseEmitter emitter = emitterMap.remove(userId);
        if (emitter != null) {
            try {
                emitter.complete();
                log.info("SSE 连接已断开, userId={}", userId);
            } catch (Exception e) {
                log.warn("关闭 SSE 连接时出现异常, userId={}", userId, e);
            }
        }
    }

    @Override
    public boolean isConnected(String userId) {
        if (userId == null || userId.isEmpty()) {
            return false;
        }
        return emitterMap.containsKey(userId);
    }
}