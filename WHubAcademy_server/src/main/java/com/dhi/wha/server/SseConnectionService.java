package com.dhi.wha.server;

import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

/**
 * SSE 连接管理服务
 */
public interface SseConnectionService {

    /**
     * 建立 SSE 连接
     *
     * @param userId 用户ID
     * @return SseEmitter
     */
    SseEmitter connect(String userId);

    /**
     * 向指定用户发送消息
     *
     * @param userId    用户ID
     * @param eventType 事件类型
     * @param data      消息内容（JSON字符串）
     */
    void sendMessage(String userId, String eventType, String data);

    /**
     * 断开指定用户的 SSE 连接
     *
     * @param userId 用户ID
     */
    void disconnect(String userId);

    /**
     * 检查用户是否已建立 SSE 连接
     *
     * @param userId 用户ID
     * @return true=已连接, false=未连接
     */
    boolean isConnected(String userId);
}