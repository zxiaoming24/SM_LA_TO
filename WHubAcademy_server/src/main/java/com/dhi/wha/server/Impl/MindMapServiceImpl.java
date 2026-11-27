package com.dhi.wha.server.Impl;

import com.alibaba.fastjson.JSON;
import com.dhi.wha.constant.MindMapConstant;
import com.dhi.wha.dto.ChatDTO;
import com.dhi.wha.dto.MindMapInsertDTO;
import com.dhi.wha.entity.MindMap;
import com.dhi.wha.mapper.MindMapMapper;
import com.dhi.wha.server.MindMapService;

import com.dhi.wha.server.SseConnectionService;
import com.dhi.wha.utils.AsyncUtil;
import com.dhi.wha.utils.PythonSseClient;
import com.dhi.wha.vo.ChatResourceVO;
import com.dhi.wha.vo.MindMapVO;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
public class MindMapServiceImpl implements MindMapService {

    @Autowired
    private MindMapMapper mindMapMapper;

    @Resource
    private PythonSseClient pythonSseClient;

    @Resource
    private SseConnectionService sseConnectionService;

    @Resource
    private ObjectMapper objectMapper;

    /**
     * 提交生成任务
     * @param request
     * @return
     */
    @Override
    public Map<String, Object> submitGenerateTask(MindMapInsertDTO request) {
        String userIdStr = request.getUserId().toString();
        boolean hasSseConnection = sseConnectionService.isConnected(userIdStr);

        // 1. 初始化数据库记录 状态1-生成中
        MindMap mindMap = new MindMap();
        mindMap.setUserId(request.getUserId());
        mindMap.setText(request.getText());
        mindMap.setStatus(MindMapConstant.MindMap_STATUS_GENERATING);
        mindMapMapper.insert(mindMap);

        // 2. 封装返回前端数据
        Map<String, Object> result = new HashMap<>();
        result.put("taskId", mindMap.getId());
        result.put("status", MindMapConstant.MindMap_STATUS_GENERATING);
        result.put("msg", "思维导图生成中...");

        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("user_id", userIdStr);
        requestBody.put("user_input", "帮我生成" + request.getText() + "的思维导图");

        if (hasSseConnection) {
            // ========== SSE 连接已建立：通过 SSE 流式返回 + 存库 ==========
            AsyncUtil.execute(() -> {
                try {
                    pythonSseClient.consumePostSse("/chat", requestBody, jsonData -> {
                        // 1. 通过 SSE 连接转发给前端
                        sseConnectionService.sendMessage(userIdStr, "mindmap_stream", jsonData);

                        // 2. 监听 task_result 事件，保存到数据库
                        try {
                            JsonNode root = objectMapper.readTree(jsonData);
                            String eventType = root.path("type").asText("");
                            if ("task_result".equals(eventType)) {
                                JsonNode resultNode = root.path("result");
                                if (!resultNode.isMissingNode()) {
                                    saveMindMapResultFromJson(mindMap.getId(), resultNode);
                                }
                            }
                        } catch (Exception e) {
                            log.error("处理SSE事件失败", e);
                        }
                    });
                } catch (Exception e) {
                    log.error("SSE流式调用Python失败", e);
                    MindMap m = new MindMap();
                    m.setId(mindMap.getId());
                    m.setStatus(MindMapConstant.MindMap_STATUS_FAILED);
                    mindMapMapper.updateById(m);
                }
            });

        } else {
            // ========== 未建立 SSE 连接：仅保存到数据库 ==========
            AsyncUtil.execute(() -> {
                try {
                    pythonSseClient.consumePostSse("/chat", requestBody, jsonData -> {
                        // 监听 task_result 事件，保存到数据库（不转发给前端）
                        try {
                            JsonNode root = objectMapper.readTree(jsonData);
                            String eventType = root.path("type").asText("");
                            if ("task_result".equals(eventType)) {
                                JsonNode resultNode = root.path("result");
                                if (!resultNode.isMissingNode()) {
                                    saveMindMapResultFromJson(mindMap.getId(), resultNode);
                                }
                            }
                        } catch (Exception e) {
                            log.error("处理SSE事件失败", e);
                        }
                    });
                } catch (Exception e) {
                    log.error("SSE流式调用Python失败", e);
                    mindMap.setStatus(MindMapConstant.MindMap_STATUS_FAILED);
                    mindMapMapper.updateById(mindMap);
                }
            });
        }

        return result;
    }

    /**
     * 获取生成状态
     * @param taskId
     * @return
     */
    @Override
    public Map<String, Object> getStatus(Long taskId) {
        MindMap mindMap = mindMapMapper.selectById(taskId);
        Map<String, Object> map = new HashMap<>();
        map.put("id", taskId);
        map.put("status", mindMap.getStatus());
        map.put("value", mindMap.getValue());  //如果状态为2，就会有数据。
        map.put("text", mindMap.getText());
        map.put("createTime", mindMap.getCreateTime());
        map.put("suggestionWarning", mindMap.getSuggestionWarning());
        return map;
    }

    /**
     * 获取用户思维导图列表
     * @param userId
     * @return
     */
    @Override
    public List<MindMapVO> getMindMapList(Long userId) {
        List<MindMapVO> list = mindMapMapper.getMindMapList(userId);
        return list;
    }

    /**
     * 获取思维导图
     * @param mindMapId
     * @return
     */
    @Override
    public MindMap getById(String mindMapId) {
        MindMap mindMap = null;
        if(isNumber(mindMapId)){
            //是数字，就转换成Long
            Long num = Long.parseLong(mindMapId);
            mindMap = mindMapMapper.selectById(num);
        }else{
            //如果不是数字，就根据资源id查询
            mindMap = mindMapMapper.getByResourceId(mindMapId);
        }
        return mindMap;
    }

    /**
     * 删除思维导图
     * @param mindMapId
     */
    @Override
    public void deleteMindMapById(Long mindMapId){
        mindMapMapper.deleteById(mindMapId);
    }

    /**
     * 获取思维导图上/下页数据
     * @param mindMapId
     * @param userId
     * @param operation
     * @return
     */
    @Override
    public MindMap getMindMapPage(
            Long mindMapId, Long userId, Long operation
    ) {
        //1.根据用户id查询该用户的思维导图列表
        List<MindMap> mindMapList = mindMapMapper.selectByUserId(userId);
        //2.判断operation是0还是1，如果是0，则返回上一页，如果是1，则返回下一页
        if (operation == 0) {
            //for增强循环,返回上一页
            for(MindMap mindMap : mindMapList){
                if (mindMap.getId().equals(mindMapId)) {
                    return mindMapList.get(mindMapList.indexOf(mindMap) - 1);
                }
            }
        }else if (operation == 1) {
            //for增强循环,返回下一页
            for(MindMap mindMap : mindMapList){
                if (mindMap.getId().equals(mindMapId)) {
                    return mindMapList.get(mindMapList.indexOf(mindMap) + 1);
                }
            }
        }else{
            throw new RuntimeException("操作类型错误");
        }
        return null;
    }

    @Override
    public Long saveMindMap(ChatDTO chatDTO) {
        String userIdStr = chatDTO.getUserId().toString();
        boolean hasSseConnection = sseConnectionService.isConnected(userIdStr);

        // 1. 初始化数据库记录 状态1-生成中
        MindMap mindMap = new MindMap();
        mindMap.setUserId(chatDTO.getUserId());
        mindMap.setText(chatDTO.getText());
        mindMap.setStatus(MindMapConstant.MindMap_STATUS_GENERATING);
        mindMapMapper.insert(mindMap);

        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("user_id", userIdStr);
        requestBody.put("user_input", chatDTO.getText());

        if (hasSseConnection) {
            // ========== SSE 连接已建立：通过 SSE 流式返回 + 存库 ==========
            AsyncUtil.execute(() -> {
                try {
                    pythonSseClient.consumePostSse("/chat", requestBody, jsonData -> {
                        // 1. 通过 SSE 连接转发给前端
                        sseConnectionService.sendMessage(userIdStr, "mindmap_stream", jsonData);

                        // 2. 监听 task_result 事件，保存到数据库
                        try {
                            JsonNode root = objectMapper.readTree(jsonData);
                            String eventType = root.path("type").asText("");
                            if ("task_result".equals(eventType)) {
                                JsonNode resultNode = root.path("result");
                                if (!resultNode.isMissingNode()) {
                                    saveMindMapResultFromJson(mindMap.getId(), resultNode);
                                }
                            }
                        } catch (Exception e) {
                            log.error("处理SSE事件失败", e);
                        }
                    });
                } catch (Exception e) {
                    log.error("SSE流式调用Python失败", e);
                    MindMap m = new MindMap();
                    m.setId(mindMap.getId());
                    m.setStatus(MindMapConstant.MindMap_STATUS_FAILED);
                    mindMapMapper.updateById(m);
                }
            });

        } else {
            // ========== 未建立 SSE 连接：仅保存到数据库 ==========
            AsyncUtil.execute(() -> {
                try {
                    pythonSseClient.consumePostSse("/chat", requestBody, jsonData -> {
                        // 监听 task_result 事件，保存到数据库（不转发给前端）
                        try {
                            JsonNode root = objectMapper.readTree(jsonData);
                            String eventType = root.path("type").asText("");
                            if ("task_result".equals(eventType)) {
                                JsonNode resultNode = root.path("result");
                                if (!resultNode.isMissingNode()) {
                                    saveMindMapResultFromJson(mindMap.getId(), resultNode);
                                }
                            }
                        } catch (Exception e) {
                            log.error("处理SSE事件失败", e);
                        }
                    });
                } catch (Exception e) {
                    log.error("SSE流式调用Python失败", e);
                    mindMap.setStatus(MindMapConstant.MindMap_STATUS_FAILED);
                    mindMapMapper.updateById(mindMap);
                }
            });
        }

        return mindMap.getId();
    }

    @Override
    public ChatResourceVO getMindMapInfoById(Integer taskId) {
        //1.根据taskId查询数据库
        ChatResourceVO chatResourceVO = mindMapMapper.getMindMapInfoById(taskId);
        return chatResourceVO;
    }

    //工具方法: 判断是否为数字
    private static boolean isNumber(String str) {
        if (str == null || str.isEmpty()) return false;
        return str.matches("\\d+");
    }

    /**
     * 将 Python 返回的 result JSON 存入数据库
     */
    private void saveMindMapResultFromJson(Long mindMapId, JsonNode resultNode) {
        try {
            MindMap mindMap = mindMapMapper.selectById(mindMapId);
            if (mindMap == null || mindMap.getStatus() == MindMapConstant.MindMap_STATUS_GENERATED) return;

            JsonNode mindmapNode;
            String resourceId;
            String title;

            JsonNode resourcesNode = resultNode.path("resources");
            if (!resourcesNode.isMissingNode() && resourcesNode.isObject()) {
                JsonNode generateMindmapNode = resourcesNode.path("generate_mindmap");
                if (!generateMindmapNode.isMissingNode()) {
                    mindmapNode = generateMindmapNode.path("mindmap");
                    resourceId = mindmapNode.path("resource_id").asText(null);
                    title = mindmapNode.path("name").asText(null);
                } else {
                    mindmapNode = resultNode.path("mindmap");
                    resourceId = resultNode.path("resource_id").asText(null);
                    title = mindmapNode.path("name").asText(null);
                }
            } else {
                mindmapNode = resultNode.path("mindmap");
                resourceId = resultNode.path("resource_id").asText(null);
                title = null;
            }

            if (mindmapNode.isMissingNode() || mindmapNode.isNull()) {
                JsonNode warningNode = resultNode.path("suggestion_warning");
                if (!warningNode.isMissingNode() && !warningNode.isNull()) {
                    mindMap.setSuggestionWarning(warningNode.asText());
                    mindMap.setStatus(MindMapConstant.MindMap_STATUS_GENERATING);
                    mindMapMapper.updateById(mindMap);
                } else {
                    mindMap.setStatus(MindMapConstant.MindMap_STATUS_FAILED);
                    mindMapMapper.updateById(mindMap);
                }
                return;
            }

            mindMap.setValue(mindmapNode.toString());
            mindMap.setResourceId(resourceId);
            if (title != null && !title.isEmpty()) {
                mindMap.setText(title);
            }
            mindMap.setStatus(MindMapConstant.MindMap_STATUS_GENERATED);
            mindMapMapper.updateById(mindMap);
        } catch (Exception e) {
            log.error("保存思维导图结果异常", e);
            MindMap mindMap = new MindMap();
            mindMap.setId(mindMapId);
            mindMap.setStatus(MindMapConstant.MindMap_STATUS_FAILED);
            mindMapMapper.updateById(mindMap);
        }
    }
}
