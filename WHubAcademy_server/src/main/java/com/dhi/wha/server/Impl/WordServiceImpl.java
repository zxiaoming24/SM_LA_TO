package com.dhi.wha.server.Impl;


import com.dhi.wha.dto.ChatDTO;
import com.dhi.wha.dto.WordDTO;
import com.dhi.wha.entity.Word;
import com.dhi.wha.mapper.WordMapper;
import com.dhi.wha.server.SseConnectionService;
import com.dhi.wha.server.WordService;
import com.dhi.wha.utils.AsyncUtil;
import com.dhi.wha.utils.PythonSseClient;
import com.dhi.wha.vo.ChatResourceVO;
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
public class WordServiceImpl implements WordService {


    @Autowired
    private WordMapper wordMapper;

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
    public Map<String, Object> submitTask(WordDTO request) {
        String userIdStr = request.getUserId().toString();
        boolean hasSseConnection = sseConnectionService.isConnected(userIdStr);

        // 1.初始化数据库记录 1=生成中
        Word word = new Word();
        word.setUserId(request.getUserId());
        word.setText(request.getText());
        word.setCreateTime(LocalDateTime.now());
        word.setStatus(1);
        wordMapper.insert(word);

        Map<String, Object> result = new HashMap<>();
        result.put("id", word.getId());
        result.put("status", 1);
        result.put("msg", "讲解文档生成中...");

        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("user_id", userIdStr);
        requestBody.put("user_input", "帮我生成" + request.getText() + "的讲解文档");

        if (hasSseConnection) {
            // ========== SSE 连接已建立：通过 SSE 流式返回 + 存库 ==========
            AsyncUtil.execute(() -> {
                try {
                    pythonSseClient.consumePostSse("/chat", requestBody, jsonData -> {
                        // 1. 通过 SSE 连接转发给前端
                        sseConnectionService.sendMessage(userIdStr, "word_stream", jsonData);

                        // 2. 监听 task_result 事件，保存到数据库
                        try {
                            JsonNode root = objectMapper.readTree(jsonData);
                            String eventType = root.path("type").asText("");
                            if ("task_result".equals(eventType)) {
                                JsonNode resultNode = root.path("result");
                                if (!resultNode.isMissingNode()) {
                                    saveWordResultFromJson(word.getId(), resultNode, true);
                                }
                            }
                        } catch (Exception e) {
                            log.error("处理SSE事件失败", e);
                        }
                    });
                } catch (Exception e) {
                    log.error("SSE流式调用Python失败", e);
                    Word w = new Word();
                    w.setId(word.getId());
                    w.setStatus(3);
                    wordMapper.updateById(w);
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
                                    saveWordResultFromJson(word.getId(), resultNode, true);
                                }
                            }
                        } catch (Exception e) {
                            log.error("处理SSE事件失败", e);
                        }
                    });
                } catch (Exception e) {
                    log.error("SSE流式调用Python失败", e);
                    word.setStatus(3);
                    wordMapper.updateById(word);
                }
            });
        }

        return result;
    }

    /**
     * 获取任务状态
     * @param id
     * @return
     */
    @Override
    public Map<String, Object> getStatus(String id) {
        if (isNumber(id)){
            //如果是number就转换成数字查询
            Long num = Long.parseLong(id);
            Word word = wordMapper.selectById(num);
            Map<String, Object> map = new HashMap<>();
            map.put("id", num);
            map.put("userId", word.getUserId());
            map.put("text", word.getText());
            map.put("status", word.getStatus());
            map.put("createTime", word.getCreateTime());
            map.put("ossUrl", word.getOssUrl());
            map.put("resourceId", word.getResourceId());
            map.put("suggestionWarning", word.getSuggestionWarning());
            return map;
        }else{
            //如果不是number就转换成resourceId查询
            Word word = wordMapper.selectByResourceId(id);
            Map<String, Object> map = new HashMap<>();
            map.put("id", word.getId());
            map.put("userId", word.getUserId());
            map.put("text", word.getText());
            map.put("status", word.getStatus());
            map.put("createTime", word.getCreateTime());
            map.put("ossUrl", word.getOssUrl());
            map.put("resourceId", word.getResourceId());
            map.put("suggestionWarning", word.getSuggestionWarning());
            return map;
        }
    }

    /**
     * 获取用户讲解文档列表
     * @param userId
     * @return
     */
    @Override
    public List<Word> getByUserId(Long userId) {
        return wordMapper.getWordListByUserId(userId);
    }

    /**
     * 删除讲解文档
     * /word/delete/{id}
     * @param id
     * @return
     */
    @Override
    public void deleteWordById(Long id) {
        wordMapper.deleteById(id);
    }

    @Override
    public Long saveWord(ChatDTO chatDTO) {
        String userIdStr = chatDTO.getUserId().toString();
        boolean hasSseConnection = sseConnectionService.isConnected(userIdStr);

        // 1. 初始化数据库记录 状态1-生成中
        Word word = new Word();
        word.setUserId(chatDTO.getUserId());
        word.setText(chatDTO.getText());
        word.setCreateTime(LocalDateTime.now());
        word.setStatus(1);
        wordMapper.insert(word);

        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("user_id", userIdStr);
        requestBody.put("user_input", chatDTO.getText() + "的讲解文档");

        if (hasSseConnection) {
            // ========== SSE 连接已建立：通过 SSE 流式返回 + 存库 ==========
            AsyncUtil.execute(() -> {
                try {
                    pythonSseClient.consumePostSse("/chat", requestBody, jsonData -> {
                        // 1. 通过 SSE 连接转发给前端
                        sseConnectionService.sendMessage(userIdStr, "word_stream", jsonData);

                        // 2. 监听 task_result 事件，保存到数据库
                        try {
                            JsonNode root = objectMapper.readTree(jsonData);
                            String eventType = root.path("type").asText("");
                            if ("task_result".equals(eventType)) {
                                JsonNode resultNode = root.path("result");
                                if (!resultNode.isMissingNode()) {
                                    saveWordResultFromJson(word.getId(), resultNode, false);
                                }
                            }
                        } catch (Exception e) {
                            log.error("处理SSE事件失败", e);
                        }
                    });
                } catch (Exception e) {
                    log.error("SSE流式调用Python失败", e);
                    Word w = new Word();
                    w.setId(word.getId());
                    w.setStatus(3);
                    wordMapper.updateById(w);
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
                                    saveWordResultFromJson(word.getId(), resultNode, false);
                                }
                            }
                        } catch (Exception e) {
                            log.error("处理SSE事件失败", e);
                        }
                    });
                } catch (Exception e) {
                    log.error("SSE流式调用Python失败", e);
                    word.setStatus(3);
                    wordMapper.updateById(word);
                }
            });
        }

        return word.getId();
    }

    @Override
    public ChatResourceVO getWordInfoById(Integer taskId) {
        return wordMapper.getWordInfoById(taskId);
    }

    //工具方法: 判断是否为数字
    private static boolean isNumber(String str) {
        if (str == null || str.isEmpty()) return false;
        return str.matches("\\d+");
    }

    /**
     * 将 Python 返回的 result JSON 存入数据库
     * @param wordId 记录ID
     * @param resultNode result节点
     * @param includeContent 是否保存 doc_content（submitTask需要，saveWord不需要）
     */
    private void saveWordResultFromJson(Long wordId, JsonNode resultNode, boolean includeContent) {
        try {
            log.info("saveWordResultFromJson: wordId={}, resultNode has resources={}",
                    wordId, resultNode.has("resources"));

            Word word = wordMapper.selectById(wordId);
            if (word == null || word.getStatus() == 2) {
                log.info("saveWordResultFromJson: word不存在或已完成, wordId={}, status={}",
                        wordId, word == null ? "null" : word.getStatus());
                return;
            }

            JsonNode documentNode;

            JsonNode resourcesNode = resultNode.path("resources");
            if (!resourcesNode.isMissingNode() && resourcesNode.isObject()) {
                JsonNode generateDocNode = resourcesNode.path("generate_document");
                if (!generateDocNode.isMissingNode()) {
                    documentNode = generateDocNode.path("document");
                } else {
                    documentNode = resultNode.path("document");
                }
            } else {
                documentNode = resultNode.path("document");
            }

            log.info("saveWordResultFromJson: documentNode isMissing={}, isEmpty={}",
                    documentNode.isMissingNode(), documentNode.isEmpty());

            if (documentNode.isMissingNode() || documentNode.isEmpty()) {
                JsonNode warningNode = resultNode.path("suggestion_warning");
                if (!warningNode.isMissingNode() && !warningNode.isNull()) {
                    word.setSuggestionWarning(warningNode.asText());
                    word.setStatus(1);
                    wordMapper.updateById(word);
                } else {
                    word.setSuggestionWarning("");
                    wordMapper.updateById(word);
                }
                return;
            }

            String resourceId = documentNode.path("resource_id").asText(null);
            if (resourceId == null || resourceId.isEmpty()) {
                resourceId = documentNode.path("_content_id").asText(null);
            }
            String ossUrl = documentNode.path("oss_url").asText(null);
            String title = documentNode.path("title").asText(null);

            log.info("saveWordResultFromJson: resourceId={}, ossUrl={}", resourceId, ossUrl);

            word.setOssUrl(ossUrl);
            word.setResourceId(resourceId);
            if (title != null && !title.isEmpty()) {
                word.setText(title);
            }
            word.setStatus(2);

            if (includeContent) {
                String docContent = documentNode.path("doc_content").asText(null);
                word.setLongText(docContent);
            }

            int rows = wordMapper.updateById(word);
            log.info("saveWordResultFromJson: updateById返回行数={}, wordId={}", rows, wordId);
        } catch (Exception e) {
            log.error("保存讲解文档结果异常, wordId={}", wordId, e);
            Word word = new Word();
            word.setId(wordId);
            word.setStatus(3);
            wordMapper.updateById(word);
        }
    }

}
