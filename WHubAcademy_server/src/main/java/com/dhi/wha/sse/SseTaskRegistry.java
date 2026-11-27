package com.dhi.wha.sse;

import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Component
public class SseTaskRegistry {

    private final Map<String, SseTaskEngine> taskMap = new ConcurrentHashMap<>();

    public void register(String runId, SseTaskEngine engine) {
        taskMap.put(runId, engine);
    }

    public SseTaskEngine get(String runId) {
        return taskMap.get(runId);
    }

    public void remove(String runId) {
        taskMap.remove(runId);
    }
}
