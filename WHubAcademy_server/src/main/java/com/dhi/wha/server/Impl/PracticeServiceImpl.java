package com.dhi.wha.server.Impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.dhi.wha.dto.ChatDTO;
import com.dhi.wha.dto.PracticeDTO;
import com.dhi.wha.entity.Example;
import com.dhi.wha.entity.Practice;
import com.dhi.wha.mapper.PracticeMapper;
import com.dhi.wha.server.ExampleService;
import com.dhi.wha.server.PracticeService;
import com.dhi.wha.server.SseConnectionService;
import com.dhi.wha.utils.AsyncUtil;
import com.dhi.wha.utils.PythonSseClient;
import com.dhi.wha.vo.ChatResourceVO;
import com.dhi.wha.vo.PracticeVO;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.TransactionStatus;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionTemplate;

import javax.annotation.Resource;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
public class PracticeServiceImpl extends ServiceImpl<PracticeMapper, Practice> implements PracticeService {

    @Resource
    private PracticeMapper practiceMapper;

    @Resource
    private ExampleService exampleService;

    // 注入编程式事务（核心）
    @Resource
    private TransactionTemplate transactionTemplate;

    @Resource
    private ObjectMapper objectMapper;

    @Resource
    private PythonSseClient pythonSseClient;

    @Resource
    private SseConnectionService sseConnectionService;

    /**
     * 提交生成编程练习题任务
     *
     * @param request
     * @return
     */
    @Override
    public Map<String, Object> submitGenerateTask(PracticeDTO request) {
        String userIdStr = request.getUserId().toString();
        boolean hasSseConnection = sseConnectionService.isConnected(userIdStr);

        if (hasSseConnection) {
            // ========== SSE 连接已建立：通过 SSE 流式返回 + 存库 ==========
            Practice practice = Practice.builder()
                    .userId(request.getUserId())
                    .text(request.getText())
                    .status(1)
                    .createTime(LocalDateTime.now())
                    .build();
            practiceMapper.insert(practice);

            Map<String, Object> requestBody = new HashMap<>();
            requestBody.put("user_id", userIdStr);
            requestBody.put("user_input", "帮我生成" + request.getText() + "的编程题");

            AsyncUtil.execute(() -> {
                try {
                    pythonSseClient.consumePostSse("/chat", requestBody, jsonData -> {
                        // 1. 通过 SSE 连接转发给前端
                        sseConnectionService.sendMessage(userIdStr, "practice_stream", jsonData);

                        // 2. 监听 task_result 事件，保存到数据库
                        try {
                            JsonNode root = objectMapper.readTree(jsonData);
                            String eventType = root.path("type").asText("");
                            if ("task_result".equals(eventType)) {
                                JsonNode resultNode = root.path("result");
                                if (!resultNode.isMissingNode()) {
                                    savePracticeResultFromJson(practice.getId(), resultNode);
                                }
                            }
                        } catch (Exception e) {
                            log.error("处理SSE事件失败", e);
                        }
                    });
                } catch (Exception e) {
                    log.error("SSE流式调用Python失败", e);
                    Practice p = new Practice();
                    p.setId(practice.getId());
                    p.setStatus(3);
                    practiceMapper.updateById(p);
                }
            });

            Map<String, Object> result = new HashMap<>();
            result.put("id", practice.getId());
            result.put("status", 1);
            result.put("msg", "编程练习题生成中...");
            return result;

        } else {
            // ========== 未建立 SSE 连接：普通 POST 方式 ==========
            return submitGenerateTaskNoSse(request);
        }
    }

    /**
     * 非SSE方式：通过SSE流调用Python /chat，仅保存到数据库
     */
    private Map<String, Object> submitGenerateTaskNoSse(PracticeDTO request) {
        Practice practice = Practice.builder()
                .userId(request.getUserId())
                .text(request.getText())
                .status(1)
                .createTime(LocalDateTime.now())
                .build();
        practiceMapper.insert(practice);

        Map<String, Object> result = new HashMap<>();
        result.put("id", practice.getId());
        result.put("status", 1);
        result.put("msg", "编程练习题生成中...");

        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("user_id", request.getUserId().toString());
        requestBody.put("user_input", "帮我生成关于" + request.getText() + "的编程题");

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
                                savePracticeResultFromJson(practice.getId(), resultNode);
                            }
                        }
                    } catch (Exception e) {
                        log.error("处理SSE事件失败", e);
                    }
                });
            } catch (Exception e) {
                log.error("SSE流式调用Python失败", e);
                practice.setStatus(3);
                practiceMapper.updateById(practice);
            }
        });

        return result;
    }

    /**
     * 获取编程练习题列表
     *
     * @param userId
     * @return
     */
    @Override
    public List<PracticeVO> getPracticeList(Long userId) {
        return practiceMapper.getPracticeList(userId);
    }

    /**
     * 获取编程练习题详情
     *
     * @param id
     * @return
     */
    @Override
    public Practice getPracticeById(Long id) {
        // 1. 根据ID查询题目主体
        Practice practice = practiceMapper.selectPracticeWithDetails(id);

        // 2. 查询该题目的所有示例（样例）
        List<Example> exampleList = exampleService.lambdaQuery()
                .eq(Example::getPracticeId, id)
                .list();

        // 3. 把样例 set 给实体 → 前端就能拿到了
        if (practice != null) {
            practice.setExamples(exampleList);
        }

        // 4. 返回完整数据
        return practice;
    }

    /**
     * 删除编程练习题
     *
     * @param id
     */
    @Transactional
    @Override
    public void deletePracticeById(Long id) {
        // 1. 删除该题目对应的所有示例
        exampleService.lambdaUpdate()
                .eq(Example::getPracticeId, id)
                .remove();

        // 2. 删除题目主表
        this.removeById(id);
    }

    @Override
    public Long savePractice(ChatDTO chatDTO) {
        String userIdStr = chatDTO.getUserId().toString();
        boolean hasSseConnection = sseConnectionService.isConnected(userIdStr);

        if (hasSseConnection) {
            // ========== SSE 连接已建立：通过 SSE 流式返回 + 存库 ==========
            Practice practice = Practice.builder()
                    .userId(chatDTO.getUserId())
                    .text(chatDTO.getText())
                    .status(1)
                    .sessionId(chatDTO.getSessionId())
                    .createTime(LocalDateTime.now())
                    .build();
            practiceMapper.insert(practice);

            Map<String, Object> requestBody = new HashMap<>();
            requestBody.put("user_id", userIdStr);
            requestBody.put("user_input", chatDTO.getText());

            AsyncUtil.execute(() -> {
                try {
                    pythonSseClient.consumePostSse("/chat", requestBody, jsonData -> {
                        // 1. 通过 SSE 连接转发给前端
                        sseConnectionService.sendMessage(userIdStr, "practice_stream", jsonData);

                        // 2. 监听 task_result 事件，保存到数据库
                        try {
                            JsonNode root = objectMapper.readTree(jsonData);
                            String eventType = root.path("type").asText("");
                            if ("task_result".equals(eventType)) {
                                JsonNode resultNode = root.path("result");
                                if (!resultNode.isMissingNode()) {
                                    savePracticeResultFromJson(practice.getId(), resultNode);
                                }
                            }
                        } catch (Exception e) {
                            log.error("处理SSE事件失败", e);
                        }
                    });
                } catch (Exception e) {
                    log.error("SSE流式调用Python失败", e);
                    Practice p = new Practice();
                    p.setId(practice.getId());
                    p.setStatus(3);
                    practiceMapper.updateById(p);
                }
            });

            return practice.getId();

        } else {
            // ========== 未建立 SSE 连接：普通 POST 方式 ==========
            return savePracticeNoSse(chatDTO);
        }
    }

    /**
     * 非SSE方式：通过SSE流调用Python /chat，仅保存到数据库
     */
    private Long savePracticeNoSse(ChatDTO chatDTO) {
        String userIdStr = chatDTO.getUserId().toString();
        Practice practice = Practice.builder()
                .userId(chatDTO.getUserId())
                .text(chatDTO.getText())
                .status(1)
                .sessionId(chatDTO.getSessionId())
                .createTime(LocalDateTime.now())
                .build();
        practiceMapper.insert(practice);

        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("user_id", userIdStr);
        requestBody.put("user_input", chatDTO.getText());

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
                                savePracticeResultFromJson(practice.getId(), resultNode);
                            }
                        }
                    } catch (Exception e) {
                        log.error("处理SSE事件失败", e);
                    }
                });
            } catch (Exception e) {
                log.error("SSE流式调用Python失败", e);
                practice.setStatus(3);
                practiceMapper.updateById(practice);
            }
        });
        return practice.getId();
    }

    @Override
    public Practice getPractice(String id) {
        // 1. 判断类型并解析
        if (isNumber(id)) {
            // 是数字类型，转为 Long/Integer/Double
            Long num = Long.parseLong(id);
            // 数字业务逻辑
            // 1. 根据ID查询题目主体
            Practice practice = practiceMapper.selectPracticeWithDetails(num);

            // 2. 查询该题目的所有示例（样例）
            List<Example> exampleList = exampleService.lambdaQuery()
                    .eq(Example::getPracticeId, id)
                    .list();

            // 3. 把样例 set 给实体 → 前端就能拿到了
            if (practice != null) {
                practice.setExamples(exampleList);
            }

            // 4. 返回完整数据
            return practice;
        } else {
            // 是普通字符串类型
            // 字符串业务逻辑
            return practiceMapper.getByProblemId(id);
        }
    }

    @Override
    public ChatResourceVO getPracticeInfoById(Integer taskId) {
        return practiceMapper.getPracticeInfoById(taskId);
    }

    @Override
    public String getSuggestionWarningById(Long practiceId) {
        return practiceMapper.getSuggestionWarningById(practiceId);
    }

    //工具方法: 判断是否为数字
    private static boolean isNumber(String str) {
        if (str == null || str.isEmpty()) return false;
        return str.matches("\\d+");
    }

    /**
     * 将 Python 返回的 result JSON 存入数据库（事务处理）
     */
    private void savePracticeResultFromJson(Long practiceId, JsonNode resultNode) {
        try {
            Practice practice = practiceMapper.selectById(practiceId);
            if (practice == null || practice.getStatus() == 2) return;

            JsonNode problemNode;
            String problemId;

            JsonNode resourcesNode = resultNode.path("resources");
            if (!resourcesNode.isMissingNode() && resourcesNode.isObject()) {
                JsonNode generatePracticeNode = resourcesNode.path("generate_practice");
                if (!generatePracticeNode.isMissingNode()) {
                    problemNode = generatePracticeNode.path("practice");
                    problemId = problemNode.path("problem_id").asText(null);
                } else {
                    problemNode = resultNode.path("practice");
                    problemId = problemNode.path("problem_id").asText(null);
                    if (problemId == null || problemId.isEmpty()) {
                        problemId = resultNode.path("resource_id").asText(null);
                    }
                }
            } else {
                problemNode = resultNode.path("practice");
                problemId = problemNode.path("problem_id").asText(null);
                if (problemId == null || problemId.isEmpty()) {
                    problemId = resultNode.path("resource_id").asText(null);
                }
            }

            JsonNode warningNode = problemNode.path("suggestion_warning");
            if (!warningNode.isMissingNode() && !warningNode.isNull()) {
                practice.setSuggestionWarning(warningNode.asText());
                practice.setStatus(1);
                practiceMapper.updateById(practice);
                return;
            }

            String title = problemNode.path("title").asText();
            String difficulty = problemNode.path("difficulty").asText();
            String description = problemNode.path("description").asText();
            String inputFormat = problemNode.path("input_format").asText();
            String outputFormat = problemNode.path("output_format").asText();

            JsonNode examplesNode = problemNode.path("examples");
            JsonNode hintsNode = problemNode.path("hints");
            JsonNode kpNode = problemNode.path("knowledge_points");

            String finalProblemId = problemId;
            Boolean success = transactionTemplate.execute((TransactionStatus status) -> {
                try {
                    practice.setTitle(title);
                    practice.setDifficulty(difficulty);
                    practice.setDescription(description);
                    practice.setInputFormat(inputFormat);
                    practice.setOutputFormat(outputFormat);
                    practice.setProblemId(finalProblemId);
                    practice.setStatus(2);
                    practice.setHints(objectMapper.convertValue(hintsNode, new TypeReference<List<String>>() {}));
                    practice.setKnowledgePoints(objectMapper.convertValue(kpNode, new TypeReference<List<String>>() {}));
                    practiceMapper.updateById(practice);

                    if (examplesNode.isArray()) {
                        List<Example> exampleList = new ArrayList<>();
                        for (JsonNode ex : examplesNode) {
                            Example example = Example.builder()
                                    .practiceId(practiceId)
                                    .input(ex.path("input").asText())
                                    .output(ex.path("output").asText())
                                    .explanation(ex.path("explanation").asText())
                                    .build();
                            exampleList.add(example);
                        }
                        exampleService.saveBatch(exampleList);
                    }
                    return true;
                } catch (Exception e) {
                    status.setRollbackOnly();
                    return false;
                }
            });

            if (Boolean.FALSE.equals(success)) {
                practice.setStatus(3);
                practiceMapper.updateById(practice);
            }
        } catch (Exception e) {
            log.error("保存练习结果异常", e);
            Practice practice = new Practice();
            practice.setId(practiceId);
            practice.setStatus(3);
            practiceMapper.updateById(practice);
        }
    }
}
