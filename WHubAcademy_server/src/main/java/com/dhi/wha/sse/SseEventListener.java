package com.dhi.wha.sse;

import com.fasterxml.jackson.databind.JsonNode;

/**
 * 业务模块实现此接口，处理 SSE 中的特定事件
 */
public interface SseEventListener {

    /**
     * 收到指定事件类型时回调
     *
     * @param runId     任务唯一标识（格式如 practice_12）
     * @param eventType 事件类型，如 "task_result"
     * @param data      事件的完整 JSON 数据（已解析为 JsonNode）
     */
    void onEvent(String runId, String eventType, JsonNode data);
}