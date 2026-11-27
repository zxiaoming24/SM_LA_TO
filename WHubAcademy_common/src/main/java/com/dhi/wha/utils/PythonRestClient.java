package com.dhi.wha.utils;

import org.springframework.http.*;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;
import javax.annotation.Resource;

@Component
public class PythonRestClient {

    //8.159.134.28
    private static final String BASE_URL = "http://localhost:8000";

    @Resource
    private RestTemplate restTemplate;

    // 原有POST方法，保持不变
    public Object post(String api, Object request) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Object> entity = new HttpEntity<>(request, headers);
        return restTemplate.postForObject(BASE_URL + api, entity, Object.class);
    }

    /**
     * 新增：POST请求，支持路径占位符 + JSON请求体
     * @param api 带路径占位符的接口路径 例：/paper/{userId}/save
     * @param requestBody JSON请求体对象
     * @param pathParams 路径占位符参数，按占位符顺序传入
     * @return 接口返回数据
     * 调用示例：postWithPathParam("/paper/{userId}/save", paperDto, "u_001")
     */
    public Object postWithPathParam(String api, Object requestBody, Object... pathParams) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Object> entity = new HttpEntity<>(requestBody, headers);
        String fullUrl = BASE_URL + api;
        return restTemplate.postForObject(fullUrl, entity, Object.class, pathParams);
    }

    /**
     * POST请求：仅路径占位符 + URL查询参数，无JSON请求体
     * @param api 带路径{xxx} + 查询{xxx}模板
     * @param allParams 按模板占位符顺序传入所有参数
     * @return 接口返回数据
     * 示例模板：/study_plan/{user_id}/generate?kp={kp}&entry={entry}
     * 调用：postWithPathQueryNoBody(api, "2", "力学", "plan")
     */
    public Object postWithPathAndQueryNoBody(String api, Object... allParams) {
        HttpHeaders headers = new HttpHeaders();
        // 无请求体无需json，可清空MediaType
        HttpEntity<Void> entity = new HttpEntity<>(null, headers);
        String fullUrl = BASE_URL + api;
        return restTemplate.exchange(fullUrl, HttpMethod.POST, entity, Object.class, allParams).getBody();
    }

    /**
     * 基础GET请求（无参数）
     */
    public Object get(String api) {
        return restTemplate.getForObject(BASE_URL + api, Object.class);
    }

    /**
     * GET 请求 - 拼接【路径参数】
     * 示例接口：/features/{userId}
     * 调用示例：getWithPathParam("/features/{userId}", "user_001")
     */
    public Object getWithPathParam(String api, Object... pathParams) {
        String fullUrl = BASE_URL + api;
        return restTemplate.getForObject(fullUrl, Object.class, pathParams);
    }

    /**
     * GET 请求 - 拼接【查询参数】
     * 示例接口：/search?type=video&id=1
     * 调用示例：getWithQueryParam("/search?type={type}&id={id}", "video", 1)
     */
    public Object getWithQueryParam(String api, Object... queryParams) {
        String fullUrl = BASE_URL + api;
        return restTemplate.getForObject(fullUrl, Object.class, queryParams);
    }

    /**
     * DELETE 请求，传JSON请求体
     * @param api 接口后缀
     * @param request 请求体参数
     * @return Object
     * 请求示例
     * pythonRestClient.delete("/paper/del", paramsMap);
     */
    public Object delete(String api, Object request) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Object> entity = new HttpEntity<>(request, headers);
        return restTemplate.exchange(BASE_URL + api, HttpMethod.DELETE, entity, Object.class).getBody();
    }

    /**
     * DELETE 请求 无请求体（路径参数）
     * 请求示例
     * pythonRestClient.deleteWithPathParam("/paper/{id}", 1);
     */
    public Object deleteWithPathParam(String api, Object... pathParams) {
        String fullUrl = BASE_URL + api;
        return restTemplate.exchange(fullUrl, HttpMethod.DELETE, null, Object.class, pathParams).getBody();
    }

    /**
     * DELETE 请求，支持路径参数 + JSON请求体
     * @param api 带路径占位符的接口路径 例：/route-market/{route_id}/delete
     * @param requestBody JSON请求体对象
     * @param pathParams 路径占位符参数，按占位符顺序传入
     * @return 接口返回数据
     */
    public Object deleteWithPathParamAndBody(String api, Object requestBody, Object... pathParams) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Object> entity = new HttpEntity<>(requestBody, headers);
        String fullUrl = BASE_URL + api;
        return restTemplate.exchange(fullUrl, HttpMethod.DELETE, entity, Object.class, pathParams).getBody();
    }

    /**
     * PUT 请求，支持路径参数 + JSON请求体
     * @param api 带路径占位符的接口路径 例：/route-market/{route_id}/update
     * @param requestBody JSON请求体对象
     * @param pathParams 路径占位符参数，按占位符顺序传入
     * @return 接口返回数据
     */
    public Object putWithPathParamAndBody(String api, Object requestBody, Object... pathParams) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Object> entity = new HttpEntity<>(requestBody, headers);
        String fullUrl = BASE_URL + api;
        return restTemplate.exchange(fullUrl, HttpMethod.PUT, entity, Object.class, pathParams).getBody();
    }


    /**
     * GET 请求：同时传递 路径参数 + 查询参数
     * @param api 接口路径，包含路径占位符 例：/user/{id}/info?name={name}&age={age}
     * @param params 按顺序传入【路径参数值、查询参数值】
     * @return 响应结果
     * 调用示例：getWithPathAndQueryParam("/user/{id}/info?name={name}", 1001, "test")
     */
    public Object getWithPathAndQueryParam(String api, Object... params) {
        String fullUrl = BASE_URL + api;
        return restTemplate.getForObject(fullUrl, Object.class, params);
    }
}