package com.dhi.wha.utils;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import javax.annotation.Resource;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.function.Consumer;

@Component
@Slf4j
public class PythonSseClient {

    private static final String BASE_URL = "http://localhost:8000";

    @Resource
    private RestTemplate restTemplate;

    @Resource
    private ObjectMapper objectMapper;

    /**
     * 以 POST 方式连接 Python SSE 端点，每解析到一个完整事件就回调 consumer
     *
     * @param uri           接口路径，如 "/test"
     * @param requestBody   请求体参数（将序列化为 JSON）
     * @param eventConsumer 事件消费者
     */
    public void consumePostSse(String uri, Map<String, Object> requestBody, Consumer<String> eventConsumer) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(requestBody, headers);
        String fullUrl = BASE_URL + uri;

        restTemplate.execute(fullUrl, HttpMethod.POST, request -> {
            // 写入请求体
            request.getHeaders().setContentType(MediaType.APPLICATION_JSON);
            request.getBody().write(objectMapper.writeValueAsBytes(requestBody));
        }, response -> {
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(response.getBody(), StandardCharsets.UTF_8))) {
                String line;
                StringBuilder dataBuffer = new StringBuilder();
                while ((line = reader.readLine()) != null) {
                    if (line.isEmpty()) {
                        if (dataBuffer.length() > 0) {
                            eventConsumer.accept(dataBuffer.toString().trim());
                            dataBuffer.setLength(0);
                        }
                        continue;
                    }
                    if (line.startsWith("data:")) {
                        String jsonData = line.substring(5);
                        if (dataBuffer.length() > 0) {
                            dataBuffer.append("\n");
                        }
                        dataBuffer.append(jsonData);
                    }
                }
                if (dataBuffer.length() > 0) {
                    eventConsumer.accept(dataBuffer.toString().trim());
                }
            } catch (Exception e) {
                log.error("SSE 流读取异常", e);
            }
            return null;
        });
    }
}
