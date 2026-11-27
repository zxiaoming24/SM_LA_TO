package com.dhi.wha.server.Impl;

import com.dhi.wha.entity.Ppt;
import com.dhi.wha.mapper.PracticeMapper;
import com.dhi.wha.mapper.VideoMapper;
import com.dhi.wha.mapper.WordMapper;
import com.dhi.wha.mapper.ExtensionReadingMapper;
import com.dhi.wha.mapper.MindMapMapper;
import com.dhi.wha.mapper.PaperMapper;
import com.dhi.wha.mapper.AnimationMapper;
import com.dhi.wha.mapper.PptMapper;
import com.dhi.wha.server.CollectResourceService;
import com.dhi.wha.utils.PythonRestClient;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;

@Slf4j
@Service
public class CollectResourceServiceImpl implements CollectResourceService {

    @Autowired
    private PythonRestClient pythonRestClient;

    @Autowired
    private PracticeMapper practiceMapper;

    @Autowired
    private WordMapper wordMapper;

    @Autowired
    private VideoMapper videoMapper;

    @Autowired
    private ExtensionReadingMapper extensionReadingMapper;

    @Autowired
    private MindMapMapper mindMapMapper;

    @Autowired
    private PaperMapper paperMapper;

    @Autowired
    private AnimationMapper animationMapper;

    @Autowired
    private PptMapper pptMapper;

    @Override
    public Object collectResources(Map<String, Object> request) {
        // userId
        Integer userId = null;
        Object userIdObj = request.get("userId");
        if (userIdObj != null) {
            userId = Integer.parseInt(userIdObj.toString());
        }

        // resourceType
        String resourceType = null;
        Object typeObj = request.get("resourceType");
        if (typeObj != null) {
            resourceType = typeObj.toString();
        }

        // resourceId
        Integer resourceId = null;
        Object resIdObj = request.get("resourceId");
        if (resIdObj != null) {
            resourceId = Integer.parseInt(resIdObj.toString());
        }

        if (userId == null || resourceType == null || resourceId == null) {
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("success", false);
            errorResult.put("message", "参数不完整");
            return errorResult;
        }

        String pythonResourceId = null;
        String title = null;

        try {
            if ("practice".equals(resourceType)) {
                pythonResourceId = practiceMapper.getProblemId(resourceId.longValue());
                title = practiceMapper.getTitleById(resourceId.longValue());
            } else if ("document".equals(resourceType)) {
                pythonResourceId = wordMapper.getResourceIdById(resourceId);
                title = wordMapper.getTitleById(resourceId.longValue());
            } else if ("video".equals(resourceType)) {
                pythonResourceId = videoMapper.getResourceIdById(resourceId.longValue());
                title = videoMapper.getTitleById(resourceId.longValue());
            } else if ("extension".equals(resourceType)) {
                pythonResourceId = extensionReadingMapper.getResourceIdById(resourceId.longValue());
                title = extensionReadingMapper.getTitleById(resourceId.longValue());
            } else if ("mindmap".equals(resourceType)) {
                pythonResourceId = mindMapMapper.getResourceIdById(resourceId.longValue());
                title = mindMapMapper.getTitleById(resourceId.longValue());
            } else if ("question".equals(resourceType)) {
                pythonResourceId = paperMapper.getResourceIdById(resourceId.longValue());
                title = paperMapper.getTitleById(resourceId.longValue());
            } else if ("animation".equals(resourceType)) {
                pythonResourceId = animationMapper.getResourceIdById(resourceId.longValue());
                title = animationMapper.getTitleById(resourceId.longValue());
            } else if ("ppt".equals(resourceType)) {
                pythonResourceId = pptMapper.getResourceIdById(resourceId.longValue());
                Ppt ppt = pptMapper.selectById(resourceId.longValue());
                if (ppt != null) {
                    title = ppt.getTaskId(); // PPT标题放在taskId字段中
                }
            } else {
                Map<String, Object> errorResult = new HashMap<>();
                errorResult.put("success", false);
                errorResult.put("message", "暂不支持该资源类型");
                return errorResult;
            }
        } catch (Exception e) {
            log.error("查询资源ID失败", e);
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("success", false);
            errorResult.put("message", "查询资源ID失败");
            return errorResult;
        }

        if (pythonResourceId == null) {
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("success", false);
            errorResult.put("message", "资源不存在");
            return errorResult;
        }

        try {
            Map<String, Object> body = new HashMap<>();
            body.put("user_id", userId.toString());
            body.put("resource_type", resourceType);
            body.put("resource_id", pythonResourceId);
            body.put("title",title);

            Object pythonRes = pythonRestClient.post("/companion/favorite/add", body);
            return pythonRes;
        } catch (Exception e) {
            log.error("调用Python端收藏接口失败", e);
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("success", false);
            errorResult.put("message", "收藏失败");
            return errorResult;
        }
    }

    @Override
    public Object cancelCollect(Map<String, Object> request) {
        String userId = (String) request.get("user_id");
        String resourceType = (String) request.get("resource_type");
        String resourceId = (String) request.get("resource_id");

        if (userId == null || resourceType == null || resourceId == null) {
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("success", false);
            errorResult.put("message", "参数不完整");
            return errorResult;
        }

        try {
            Map<String, Object> body = new HashMap<>();
            body.put("user_id", userId.toString());
            body.put("resource_type", resourceType);
            body.put("resource_id", resourceId);

            Object pythonRes = pythonRestClient.post("/companion/favorite/remove", body);
            return pythonRes;
        } catch (Exception e) {
            log.error("调用Python端取消收藏接口失败", e);
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("success", false);
            errorResult.put("message", "取消收藏失败");
            return errorResult;
        }
    }

    @Override
    public Object getCollectionList(String userId) {
        if (userId == null || userId.isEmpty()) {
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("success", false);
            errorResult.put("message", "用户ID不能为空");
            return errorResult;
        }

        try {
            Object pythonRes = pythonRestClient.getWithPathParam("/companion/favorites/{user_id}", userId);
            return pythonRes;
        } catch (Exception e) {
            log.error("调用Python端获取收藏列表接口失败", e);
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("success", false);
            errorResult.put("message", "获取收藏列表失败");
            return errorResult;
        }
    }
}