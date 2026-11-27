package com.dhi.wha.server.Impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.dhi.wha.dto.AnimationDTO;
import com.dhi.wha.dto.ChatDTO;
import com.dhi.wha.entity.Animation;
import com.dhi.wha.mapper.AnimationMapper;
import com.dhi.wha.server.AnimationService;
import com.dhi.wha.server.SseConnectionService;
import com.dhi.wha.utils.AsyncUtil;
import com.dhi.wha.utils.PythonSseClient;
import com.dhi.wha.vo.ChatResourceVO;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class AnimationServiceImpl extends ServiceImpl<AnimationMapper, Animation>
        implements AnimationService {


    @Autowired
    private AnimationMapper animationMapper;

    @Resource
    private PythonSseClient pythonSseClient;

    @Resource
    private SseConnectionService sseConnectionService;

    @Resource
    private ObjectMapper objectMapper;


    @Override
    public Map<String, Object> generateAnimation(AnimationDTO animationDTO) {
        String userIdStr = animationDTO.getUserId().toString();
        boolean hasSseConnection = sseConnectionService.isConnected(userIdStr);

        // 1.封装数据
        Animation animation = new Animation();
        animation.setUserId(animationDTO.getUserId());
        animation.setText(animationDTO.getText());
        animation.setCreateTime(LocalDateTime.now());
        animation.setStatus(1);
        animationMapper.insert(animation);

        // 2.封装传给前端的数据
        Map<String, Object> result = new HashMap<>();
        result.put("id", animation.getId());
        result.put("status", 1);
        result.put("msg", "动画正在生成中...");

        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("user_id", userIdStr);
        requestBody.put("user_input", "帮我生成" + animationDTO.getText() + "的动画");
        requestBody.put("enable_tts", false);

        if (hasSseConnection) {
            // ========== SSE 连接已建立：通过 SSE 流式返回 + 存库 ==========
            AsyncUtil.execute(() -> {
                try {
                    pythonSseClient.consumePostSse("/chat", requestBody, jsonData -> {
                        // 1. 通过 SSE 连接转发给前端
                        sseConnectionService.sendMessage(userIdStr, "animation_stream", jsonData);

                        // 2. 监听 task_result 事件，保存到数据库
                        try {
                            JsonNode root = objectMapper.readTree(jsonData);
                            String eventType = root.path("type").asText("");
                            if ("task_result".equals(eventType)) {
                                JsonNode resultNode = root.path("result");
                                if (!resultNode.isMissingNode()) {
                                    saveAnimationResultFromJson(animation.getId(), resultNode);
                                }
                            }
                        } catch (Exception e) {
                            log.error("处理SSE事件失败", e);
                        }
                    });
                } catch (Exception e) {
                    log.error("SSE流式调用Python失败", e);
                    Animation p = new Animation();
                    p.setId(animation.getId());
                    p.setStatus(3);
                    animationMapper.updateById(p);
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
                                    saveAnimationResultFromJson(animation.getId(), resultNode);
                                }
                            }
                        } catch (Exception e) {
                            log.error("处理SSE事件失败", e);
                        }
                    });
                } catch (Exception e) {
                    log.error("SSE流式调用Python失败", e);
                    animation.setStatus(3);
                    animationMapper.updateById(animation);
                }
            });
        }

        return result;
    }

    @Override
    public Animation pollAnimation(String id) {
        Animation animation = null;
        //1.判断是否为数字
        if (isNumber(id)) {
            //2.是数字类型，将id转为数字
            Long num = Long.parseLong(id);
            animation = animationMapper.pollAnimation(num);
        }else{
            //如果不是数字就是资源id(py端的)
            animation = animationMapper.pollAnimationByResourceId(id);
        }
        return animation;
    }

    @Override
    public Long saveAnimation(ChatDTO chatDTO) {
        String userIdStr = chatDTO.getUserId().toString();
        boolean hasSseConnection = sseConnectionService.isConnected(userIdStr);

        Animation animation = new Animation();
        animation.setUserId(chatDTO.getUserId());
        animation.setText(chatDTO.getText());
        animation.setCreateTime(LocalDateTime.now());
        animation.setStatus(1);
        animationMapper.insert(animation);

        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("user_id", userIdStr);
        requestBody.put("topic", chatDTO.getText());
        requestBody.put("enable_tts", false);

        if (hasSseConnection) {
            // ========== SSE 连接已建立：通过 SSE 流式返回 + 存库 ==========
            AsyncUtil.execute(() -> {
                try {
                    pythonSseClient.consumePostSse("/chat", requestBody, jsonData -> {
                        // 1. 通过 SSE 连接转发给前端
                        sseConnectionService.sendMessage(userIdStr, "animation_stream", jsonData);

                        // 2. 监听 task_result 事件，保存到数据库
                        try {
                            JsonNode root = objectMapper.readTree(jsonData);
                            String eventType = root.path("type").asText("");
                            if ("task_result".equals(eventType)) {
                                JsonNode resultNode = root.path("result");
                                if (!resultNode.isMissingNode()) {
                                    saveAnimationResultFromJson(animation.getId(), resultNode);
                                }
                            }
                        } catch (Exception e) {
                            log.error("处理SSE事件失败", e);
                        }
                    });
                } catch (Exception e) {
                    log.error("SSE流式调用Python失败", e);
                    Animation p = new Animation();
                    p.setId(animation.getId());
                    p.setStatus(3);
                    animationMapper.updateById(p);
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
                                    saveAnimationResultFromJson(animation.getId(), resultNode);
                                }
                            }
                        } catch (Exception e) {
                            log.error("处理SSE事件失败", e);
                        }
                    });
                } catch (Exception e) {
                    log.error("SSE流式调用Python失败", e);
                    animation.setStatus(3);
                    animationMapper.updateById(animation);
                }
            });
        }

        return animation.getId();
    }

    /**
     * 获取用户动画列表
     * @param userId
     * @return
     */
    @Override
    public List<Animation> listByUserId(Long userId) {
        return animationMapper.listByUserId(userId);
    }

    @Override
    public ChatResourceVO getAnimationInfoById(Integer taskId) {
        return animationMapper.getAnimationInfoById(taskId);
    }

    //工具方法: 判断是否为数字
    private static boolean isNumber(String str) {
        if (str == null || str.isEmpty()) return false;
        return str.matches("\\d+");
    }

    /**
     * 将 Python 返回的 result JSON 存入数据库
     */
    private void saveAnimationResultFromJson(Long animationId, JsonNode resultNode) {
        try {
            Animation animation = animationMapper.selectById(animationId);
            if (animation == null || animation.getStatus() == 2) return;

            JsonNode animationNode = resultNode.path("animation");
            if (animationNode.isMissingNode() || animationNode.isEmpty()) {
                // 检查是否有 suggestion_warning
                JsonNode warningNode = resultNode.path("suggestion_warning");
                if (!warningNode.isMissingNode() && !warningNode.isNull()) {
                    animation.setSuggestionWarning(warningNode.asText());
                    animation.setStatus(1);
                    animationMapper.updateById(animation);
                } else {
                    animation.setStatus(3);
                    animationMapper.updateById(animation);
                }
                return;
            }

            // 从 result 层取 resource_id
            String resourceId = resultNode.path("resource_id").asText(null);
            String html = animationNode.path("html").asText(null);

            animation.setHtml(html);
            animation.setResourceId(resourceId);
            animation.setStatus(2);
            animationMapper.updateById(animation);
        } catch (Exception e) {
            log.error("保存动画结果异常", e);
            Animation animation = new Animation();
            animation.setId(animationId);
            animation.setStatus(3);
            animationMapper.updateById(animation);
        }
    }
}
