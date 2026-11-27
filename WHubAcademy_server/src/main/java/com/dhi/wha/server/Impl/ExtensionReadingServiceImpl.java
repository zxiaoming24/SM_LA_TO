package com.dhi.wha.server.Impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.dhi.wha.dto.ChatDTO;
import com.dhi.wha.dto.ExtensionReadingDTO;
import com.dhi.wha.entity.ExtensionReading;
import com.dhi.wha.mapper.ExtensionReadingMapper;
import com.dhi.wha.server.ExtensionReadingService;
import com.dhi.wha.server.SseConnectionService;
import com.dhi.wha.utils.AsyncUtil;
import com.dhi.wha.utils.HtmlGenerator;
import com.dhi.wha.utils.PythonSseClient;
import com.dhi.wha.vo.ChatResourceVO;
import com.dhi.wha.vo.ExtensionReadingVO;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;


@Slf4j
@Service
public class ExtensionReadingServiceImpl extends ServiceImpl<ExtensionReadingMapper, ExtensionReading>
        implements ExtensionReadingService {

    @Autowired
    private ExtensionReadingMapper extensionReadingMapper;

    @Resource
    private PythonSseClient pythonSseClient;

    @Resource
    private SseConnectionService sseConnectionService;

    @Resource
    private ObjectMapper objectMapper;

    /**
     * 提交生成拓展阅读任务
     *
     * @param request
     * @return
     */
    @Override
    public Map<String, Object> submitGenerateTask(ExtensionReadingDTO request) {
        String userIdStr = request.getUserId().toString();
        boolean hasSseConnection = sseConnectionService.isConnected(userIdStr);

        // 1. 初始化数据库记录 状态1-生成中
        ExtensionReading extensionReading = ExtensionReading.builder()
                .userId(request.getUserId())
                .text(request.getText())
                .createTime(LocalDateTime.now())
                .status(1)
                .build();
        extensionReadingMapper.insert(extensionReading);

        // 2. 封装返回前端数据
        Map<String, Object> result = new HashMap<>();
        result.put("id", extensionReading.getId());
        result.put("status", 1);
        result.put("msg", "拓展阅读材料生成中...");

        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("user_id", userIdStr);
        requestBody.put("user_input", "帮我生成" + request.getText() + "的拓展阅读");

        if (hasSseConnection) {
            // ========== SSE 连接已建立：通过 SSE 流式返回 + 存库 ==========
            AsyncUtil.execute(() -> {
                try {
                    pythonSseClient.consumePostSse("/chat", requestBody, jsonData -> {
                        // 1. 通过 SSE 连接转发给前端
                        sseConnectionService.sendMessage(userIdStr, "extension_stream", jsonData);

                        // 2. 监听 task_result 事件，保存到数据库
                        try {
                            JsonNode root = objectMapper.readTree(jsonData);
                            String eventType = root.path("type").asText("");
                            if ("task_result".equals(eventType)) {
                                JsonNode resultNode = root.path("result");
                                if (!resultNode.isMissingNode()) {
                                    saveExtensionResultFromJson(extensionReading.getId(), resultNode);
                                }
                            }
                        } catch (Exception e) {
                            log.error("处理SSE事件失败", e);
                        }
                    });
                } catch (Exception e) {
                    log.error("SSE流式调用Python失败", e);
                    ExtensionReading failBean = ExtensionReading.builder()
                            .id(extensionReading.getId())
                            .status(3)
                            .build();
                    extensionReadingMapper.updateById(failBean);
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
                                    saveExtensionResultFromJson(extensionReading.getId(), resultNode);
                                }
                            }
                        } catch (Exception e) {
                            log.error("处理SSE事件失败", e);
                        }
                    });
                } catch (Exception e) {
                    log.error("SSE流式调用Python失败", e);
                    ExtensionReading failBean = ExtensionReading.builder()
                            .id(extensionReading.getId())
                            .status(3)
                            .build();
                    extensionReadingMapper.updateById(failBean);
                }
            });
        }

        return result;
    }

    /**
     * 获取拓展阅读状态
     *
     * @param id
     * @return
     */
    @Override
    public Map<String, Object> getStatus(String id) {
        ExtensionReading extensionReading = null;
        if(!isNumber(id)){
            //不是数字，就根据资源id查询(py端的)
            extensionReading = extensionReadingMapper.getByResourceId(id);
        }else{
            //是数字，转换为Long类型的数据
            Long num = Long.parseLong(id);
            extensionReading = extensionReadingMapper.selectById(num);
        }

        Map<String, Object> map = new HashMap<>();
        map.put("id", id);
        map.put("status", extensionReading.getStatus());

        //核心：状态=2 成功时，自动把数据转成 HTML 返回！
        if (extensionReading.getStatus() == 2) {
            String html = HtmlGenerator.generateReadingHtml(extensionReading);
            map.put("htmlContent", html); // 前端直接 v-html 渲染
        } else {
            map.put("htmlContent", "");
        }

        map.put("text", extensionReading.getText());
        map.put("createTime", extensionReading.getCreateTime());
        map.put("suggestionWarning", extensionReading.getSuggestionWarning());

        return map;
    }

    @Override
    public List<ExtensionReadingVO> getExtensionReadingList(Long userId) {
        return extensionReadingMapper.getExtensionReadingList(userId);
    }

    @Override
    public Long saveExtension(ChatDTO chatDTO) {
        String userIdStr = chatDTO.getUserId().toString();
        boolean hasSseConnection = sseConnectionService.isConnected(userIdStr);

        // 1. 初始化数据库记录 状态1-生成中
        ExtensionReading extensionReading = ExtensionReading.builder()
                .userId(chatDTO.getUserId())
                .text(chatDTO.getText())
                .createTime(LocalDateTime.now())
                .status(1)
                .build();
        extensionReadingMapper.insert(extensionReading);

        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("user_id", userIdStr);
        requestBody.put("user_input", chatDTO.getText() + "的拓展阅读材料");

        if (hasSseConnection) {
            // ========== SSE 连接已建立：通过 SSE 流式返回 + 存库 ==========
            AsyncUtil.execute(() -> {
                try {
                    pythonSseClient.consumePostSse("/chat", requestBody, jsonData -> {
                        // 1. 通过 SSE 连接转发给前端
                        sseConnectionService.sendMessage(userIdStr, "extension_stream", jsonData);

                        // 2. 监听 task_result 事件，保存到数据库
                        try {
                            JsonNode root = objectMapper.readTree(jsonData);
                            String eventType = root.path("type").asText("");
                            if ("task_result".equals(eventType)) {
                                JsonNode resultNode = root.path("result");
                                if (!resultNode.isMissingNode()) {
                                    saveExtensionResultFromJson(extensionReading.getId(), resultNode);
                                }
                            }
                        } catch (Exception e) {
                            log.error("处理SSE事件失败", e);
                        }
                    });
                } catch (Exception e) {
                    log.error("SSE流式调用Python失败", e);
                    ExtensionReading failBean = ExtensionReading.builder()
                            .id(extensionReading.getId())
                            .status(3)
                            .build();
                    extensionReadingMapper.updateById(failBean);
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
                                    saveExtensionResultFromJson(extensionReading.getId(), resultNode);
                                }
                            }
                        } catch (Exception e) {
                            log.error("处理SSE事件失败", e);
                        }
                    });
                } catch (Exception e) {
                    log.error("SSE流式调用Python失败", e);
                    ExtensionReading failBean = ExtensionReading.builder()
                            .id(extensionReading.getId())
                            .status(3)
                            .build();
                    extensionReadingMapper.updateById(failBean);
                }
            });
        }

        return extensionReading.getId();
    }

    @Override
    public ChatResourceVO getExtensionInfoById(Integer taskId) {
        return extensionReadingMapper.getExtensionInfoById(taskId);
    }

    //工具方法: 判断是否为数字
    private static boolean isNumber(String str) {
        if (str == null || str.isEmpty()) return false;
        return str.matches("\\d+");
    }

    /**
     * 将 Python 返回的 result JSON 存入数据库
     */
    private void saveExtensionResultFromJson(Long extensionReadingId, JsonNode resultNode) {
        try {
            ExtensionReading extensionReading = extensionReadingMapper.selectById(extensionReadingId);
            if (extensionReading == null || extensionReading.getStatus() == 2) return;

            JsonNode extensionNode;
            String resourceId;

            JsonNode resourcesNode = resultNode.path("resources");
            if (!resourcesNode.isMissingNode() && resourcesNode.isObject()) {
                JsonNode generateExtNode = resourcesNode.path("generate_extension");
                if (!generateExtNode.isMissingNode()) {
                    extensionNode = generateExtNode.path("reading_material");
                    resourceId = extensionNode.path("resource_id").asText(null);
                } else {
                    extensionNode = resultNode.path("extension");
                    resourceId = resultNode.path("resource_id").asText(null);
                }
            } else {
                extensionNode = resultNode.path("extension");
                resourceId = resultNode.path("resource_id").asText(null);
            }

            if (extensionNode.isMissingNode() || extensionNode.isEmpty()) {
                JsonNode warningNode = resultNode.path("suggestion_warning");
                if (!warningNode.isMissingNode() && !warningNode.isNull()) {
                    extensionReading.setSuggestionWarning(warningNode.asText());
                    extensionReading.setStatus(1);
                    extensionReadingMapper.updateById(extensionReading);
                } else {
                    ExtensionReading failBean = ExtensionReading.builder()
                            .id(extensionReadingId)
                            .status(3)
                            .build();
                    extensionReadingMapper.updateById(failBean);
                }
                return;
            }

            String title = extensionNode.path("title").asText(null);
            String background = extensionNode.path("background").asText(null);
            String knowledgeDistinguish = extensionNode.path("knowledge_distinguish").asText(null);
            String principleExtend = extensionNode.path("principle_extend").asText(null);
            String mistakeAvoid = extensionNode.path("mistake_avoid").asText(null);
            String applicationScene = extensionNode.path("application_scene").asText(null);
            String personalSuggest = extensionNode.path("personal_suggest").asText(null);

            ExtensionReading updateBean = ExtensionReading.builder()
                    .id(extensionReadingId)
                    .title(title)
                    .text(title)
                    .background(background)
                    .knowledgeDistinguish(knowledgeDistinguish)
                    .principleExtend(principleExtend)
                    .mistakeAvoid(mistakeAvoid)
                    .applicationScene(applicationScene)
                    .personalSuggest(personalSuggest)
                    .resourceId(resourceId)
                    .status(2)
                    .build();

            extensionReadingMapper.updateById(updateBean);
        } catch (Exception e) {
            log.error("保存拓展阅读结果异常", e);
            ExtensionReading failBean = ExtensionReading.builder()
                    .id(extensionReadingId)
                    .status(3)
                    .build();
            extensionReadingMapper.updateById(failBean);
        }
    }
}
