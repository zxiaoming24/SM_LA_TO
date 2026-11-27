package com.dhi.wha.server.Impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.dhi.wha.business.ResourceDispatcher;
import com.dhi.wha.constant.MindMapConstant;
import com.dhi.wha.constant.PptStatusConstant;
import com.dhi.wha.dto.*;
import com.dhi.wha.entity.*;
import com.dhi.wha.mapper.*;
import com.dhi.wha.server.*;
import com.dhi.wha.utils.AliOssUtil;
import com.dhi.wha.utils.AsyncUtil;
import com.dhi.wha.utils.PythonRestClient;
import com.dhi.wha.utils.PythonSseClient;
import com.dhi.wha.vo.ChatResourceVO;
import com.dhi.wha.vo.PlanVO;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import javax.annotation.Resource;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.URL;
import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.atomic.AtomicReference;

import static java.util.List.of;

@Service
@Slf4j
public class ChatServiceImpl extends ServiceImpl<ChatMapper, Chat> implements ChatService {

    @Autowired
    private ChatService chatService;

    @Autowired
    private ChatMapper chatMapper;

    @Autowired
    private ResourceDispatcher resourceDispatcher;

    @Autowired
    private PythonRestClient pythonRestClient;

    @Resource
    private PythonSseClient pythonSseClient;

    @Resource
    private SseConnectionService sseConnectionService;

    @Resource
    private ObjectMapper objectMapper;

    @Autowired
    private LoginMapper loginMapper;

    @Autowired
    private PracticeMapper practiceMapper;

    @Autowired
    private VideoMapper videoMapper;

    @Autowired
    private WordMapper wordMapper;

    @Autowired
    private ExtensionReadingMapper extensionReadingMapper;

    @Autowired
    private MindMapMapper mindMapMapper;

    @Autowired
    private PptMapper pptMapper;

    @Autowired
    private PaperMapper paperMapper;

    @Autowired
    private SingleChoiceService singleChoiceService;

    @Autowired
    private MultipleChoiceService multipleChoiceService;

    @Autowired
    private JudgeService judgeService;

    @Autowired
    private FillBlankService fillBlankService;

    @Autowired
    private ShortAnswerService shortAnswerService;

    @Autowired
    private ExampleService exampleService;

    @Autowired
    private AliOssUtil aliOssUtil;

    /**
     * 获取AI的回答
     * @param chatDTO
     * @return
     */
    @Transactional
    @Override
    public Map<String, Object> getAIAnswer(ChatDTO chatDTO) {
        String userIdStr = chatDTO.getUserId().toString();
        boolean hasSseConnection = sseConnectionService.isConnected(userIdStr);

        // 用户数据封装
        Chat chat = new Chat();
        chat.setUserId(chatDTO.getUserId());
        chat.setType("user");
        chat.setContent(chatDTO.getText());
        chat.setStatus(2);
        chat.setCreateTime(LocalDateTime.now());
        chatMapper.insert(chat);

        // ai回答封装
        Chat aiChat = new Chat();
        aiChat.setUserId(chatDTO.getUserId());
        aiChat.setType("ai");
        aiChat.setStatus(1);
        aiChat.setCreateTime(LocalDateTime.now());
        chatMapper.insert(aiChat);

        if(chatDTO.getRsType() == null){
            //为空，表示普通对话
            Map<String, Object> pythonParam = new HashMap<>();
            pythonParam.put("user_id", userIdStr);
            pythonParam.put("user_input", chatDTO.getText());

            // ========== 同步调用，等待Python返回 ==========
            AtomicReference<String> replyContent = new AtomicReference<>("");
            AtomicReference<String> replyStatus = new AtomicReference<>("");
            try {
                pythonSseClient.consumePostSse("/chat", pythonParam, jsonData -> {
                    // 如果有SSE连接，将每个事件转发给前端
                    if (hasSseConnection) {
                        sseConnectionService.sendMessage(userIdStr, "chat_stream", jsonData);
                    }

                    // 监听 task_result 事件，保存到数据库并收集content
                    try {
                        JsonNode root = objectMapper.readTree(jsonData);
                        String eventType = root.path("type").asText("");
                        if ("task_result".equals(eventType)) {
                            JsonNode resultNode = root.path("result");
                            if (!resultNode.isMissingNode()) {
                                List<String> content = saveChatResultFromJson(aiChat.getId(), chatDTO.getUserId(), resultNode);
                                if (content != null) {
                                    replyContent.set(content.get(1));
                                    replyStatus.set(content.get(0));
                                }
                            }
                        }
                    } catch (Exception e) {
                        log.error("处理SSE事件失败", e);
                    }
                });

                // 返回Python的回复内容给前端
                Map<String, Object> result = new HashMap<>();
                result.put("type", "ai");
                result.put("rsType", null);
                if(replyStatus.get().equals("registration_complete")){
                    result.put("des_stage","registration_complete");
                    result.put("guidance", replyContent.get());
                } else if (replyStatus.get().equals("need_more_info")) {
                    result.put("status","need_more_info");
                    result.put("content", replyContent.get());
                } else{
                    result.put("content", replyContent.get());
                    log.info("正常对话");
                }
                return result;

            } catch (Exception e) {
                log.error("SSE流式调用Python失败", e);
                aiChat.setContent("AI服务异常，请稍后重试");
                aiChat.setStatus(3);
                chatMapper.updateById(aiChat);

                Map<String, Object> errMap = new HashMap<>();
                errMap.put("type", "ai");
                errMap.put("rsType", null);
                return errMap;
            }
        }
        else if (chatDTO.getRsType() == 99) {
            //超级智能体：多资源生成
            return handleSuperAgentRequest(chatDTO, aiChat);
        }
        else{
            Map<String,Object> res = new HashMap<>();
            res.put("type","ai");
            res.put("content","正在根据您的特征信息来生成资源...");
            res.put("rsType",chatDTO.getRsType());
            res.put("id", aiChat.getId());

            //原来case 0~9全部删掉，替换这一行
            Map<String,Object> resource = resourceDispatcher.doCreateResource(chatDTO.getRsType(), chatDTO);
            res.put("resource",resource);


            //补充聊天记录
            aiChat.setContent("正在根据您的特征信息来生成资源...");
            aiChat.setResource(resource);
            aiChat.setRsType(chatDTO.getRsType());
            Object taskIdObj = resource.get("taskId");
            aiChat.setTaskId(taskIdObj == null ? "" : taskIdObj.toString());
            chatMapper.updateById(aiChat);
            return res;
        }
    }

    /**
     * 获取资源生成结果
     * @param userId
     * @param rsType
     * @param taskId
     * @return
     */
    @Override
    public Map<String, Object> getResourceDispatcher(Integer userId, Integer rsType, String taskId) {
        Map<String,Object> res = new HashMap<>();
        Map<String,Object> resource = new HashMap<>();
        res.put("rsType",rsType);
        res.put("type", "ai");
        resource.put("taskId",taskId);
        //1.查询出来的数据需要根据状态来判断1，2，3
        ChatResourceVO chatResourceVO = resourceDispatcher.getResourceId(taskId, rsType, userId);
        if(chatResourceVO != null && chatResourceVO.getStatus().equals(1)){
            //资源还在生成中
            resource.put("status",1);
            resource.put("text",chatResourceVO.getText());
            resource.put("createTime",chatResourceVO.getCreateTime());
            resource.put("suggestionWarning",chatResourceVO.getSuggestionWarning());
            res.put("content","正在根据您的特征信息来生成资源...");
            res.put("resource",resource);
        } else if (chatResourceVO != null && chatResourceVO.getStatus().equals(2)) {
            //资源生成完成
            resource.put("status",2);
            resource.put("text",chatResourceVO.getText());
            resource.put("createTime",chatResourceVO.getCreateTime());
            res.put("content","生成完成!");
            res.put("resource",resource);
            chatMapper.updateStatusByTaskIdAndUserIdAndRsType(2,taskId, rsType, userId,resource,"生成完成！");
        }else{
            resource.put("status",3);
            if (chatResourceVO != null) {
                resource.put("text",chatResourceVO.getText());
            }
            if (chatResourceVO != null) {
                resource.put("createTime",chatResourceVO.getCreateTime());
            }
            res.put("content","生成失败!");
            res.put("resource",resource);
            chatMapper.updateStatusByTaskIdAndUserIdAndRsType(3,taskId, rsType, userId,resource,"生成失败~");
        }
        return res;
    }

    /**
     * 重新获取生成资源
     * @param userId
     * @param rsType
     * @param taskId
     * @return
     */
    @Override
    public Map<String, Object> refetchResourceDispatcher(Integer userId, Integer rsType, String taskId) {
        //1.根据三个参数查询chat的数据库
        Long aiId = chatMapper.getTextByUserIdAndRsTypeAndTaskId(userId,rsType,taskId);
        String text = chatMapper.getTextByAIId(aiId - 1);
        //2.封装成ChatDTO
        ChatDTO chatDTO = new ChatDTO();
        chatDTO.setUserId(Long.valueOf(userId));
        chatDTO.setText(text);
        chatDTO.setRsType(rsType);
        //3.调用自己的创建方法
        return chatService.getAIAnswer(chatDTO);
    }

    /**
     * 获取用户聊天记录
     * @param chatQueryDTO
     * @return
     */
    @Override
    public List<Chat> selectChatByUserId(ChatQueryDTO chatQueryDTO) {
        return chatMapper.selectChatByUserId(chatQueryDTO.getUserId(),chatQueryDTO.getLastId(),chatQueryDTO.getPageSize());
    }

    @Override
    public Object chatWithContext(ChatContextDTO chatContextDTO) {
        Map<String, Object> body = new HashMap<>();
        body.put("user_id", chatContextDTO.getUser_id());
        body.put("user_input", chatContextDTO.getUser_input());
        body.put("page_context", chatContextDTO.getPage_context());
        return pythonRestClient.post("/chat/context", body);
    }

    @Override
    public Map<String, Object> selectPlan(Map<String, Object> request) {
        log.info("选择学习方案, request: {}", request);
        Map<String, Object> body = new HashMap<>();
        body.put("user_id", request.get("user_id"));
        body.put("plan_id", request.get("plan_id"));
        body.put("plan_name", request.get("plan_name"));
        return (Map<String, Object>) pythonRestClient.post("/api/plan/select", body);
    }

    @Override
    public PlanVO getPlanByUserId(Long userId) {
        log.info("获取学习方案, userId: {}", userId);
        String userIdStr = userId.toString();

        PlanVO planVO = new PlanVO();

        // 1. 请求当前用户所选的方案
        Map<String, Object> selectedResult = (Map<String, Object>) pythonRestClient.getWithPathParam("/api/plan/selected/{userId}", userIdStr);
        if (selectedResult != null && Boolean.TRUE.equals(selectedResult.get("success"))) {
            Map<String, Object> plan = (Map<String, Object>) selectedResult.get("plan");
            if (plan != null) {
                planVO.setUserId(String.valueOf(plan.get("user_id")));
                planVO.setPlanId(String.valueOf(plan.get("plan_id")));
            }
        }

        // 2. 请求所有方案列表
        Map<String, Object> optionsResult = (Map<String, Object>) pythonRestClient.getWithPathParam("/api/plan/options/{userId}", userIdStr);
        if (optionsResult != null && Boolean.TRUE.equals(optionsResult.get("success"))) {
            List<Map<String, Object>> plans = (List<Map<String, Object>>) optionsResult.get("plans");
            planVO.setPlans(plans);
        }

        return planVO;
    }

    @Override
    public Map<String, Object> sendGreetings(Long userId) {
        log.info("发送问候（主动提醒）, userId: {}", userId);
        String userIdStr = userId.toString();

        // 使用查询参数请求 Python 端
        Map<String, Object> result = (Map<String, Object>) pythonRestClient.getWithQueryParam("/api/proactive/check?user_id={user_id}", userIdStr);
        return result;
    }

    /**
     * 将 Python 返回的 result JSON 存入数据库，返回存入的 content
     * result 数据结构：
     *   - 普通对话：result.data.reply 或 result.data.data.reply
     *   - 画像构建：result.data.data.des_stage / desStage
     *   - 收集画像：result.status == "need_more_info" 或 result.data.status == "need_more_info"
     */
    private List<String> saveChatResultFromJson(Long aiChatId, Long userId, JsonNode resultNode) {
        try {
            List<String> res = new ArrayList<>();
            Chat aiChat = chatMapper.selectById(aiChatId);
            if (aiChat == null || aiChat.getStatus() == 2) return null;

            // 普通对话时 reply 在 result.data.reply 或 result.data.data.reply
            JsonNode dataNode = resultNode.path("data");
            JsonNode innerDataNode = dataNode.path("data");

            // 检查 des_stage（画像构建完成）- des_stage 可能在 result.data 层或 result 层
            JsonNode desStageNode = dataNode.path("des_stage");
            if (desStageNode.isMissingNode()) {
                desStageNode = dataNode.path("desStage");
            }
            if (desStageNode.isMissingNode()) {
                desStageNode = resultNode.path("des_stage");
            }
            if (desStageNode.isMissingNode()) {
                desStageNode = resultNode.path("desStage");
            }

            if (!desStageNode.isMissingNode() && !desStageNode.isNull()) {
                // 场景1：画像构建完成
                String guidance = dataNode.path("guidance").asText(null);
                if (guidance == null || guidance.isEmpty()) {
                    guidance = resultNode.path("guidance").asText("");
                }
                aiChat.setContent(guidance);
                aiChat.setStatus(2);
                chatMapper.updateById(aiChat);

                // 更新用户画像状态
                User user = loginMapper.getById(userId);
                if (user != null) {
                    user.setIsBuildProfile(1);
                    user.setIsNew(false);
                    user.setType(1);
                    loginMapper.updateById(user);
                }
                res.add("registration_complete");
                res.add(guidance);
                return res;
            }

            // 检查 status（收集画像信息）- status 可能在 result 层或 result.data 层
            String status = resultNode.path("status").asText("");
            if (status == null || status.isEmpty()) {
                status = dataNode.path("status").asText("");
            }
            if ("need_more_info".equals(status)) {
                // 场景2：收集画像信息 - follow_up_questions 可能在 result 层或 result.data 层
                JsonNode questionsNode = resultNode.path("follow_up_questions");
                if (questionsNode.isMissingNode()) {
                    questionsNode = dataNode.path("follow_up_questions");
                }
                String firstQuestion = "抱歉~信息丢失了";
                if (questionsNode.isArray() && questionsNode.size() > 0) {
                    firstQuestion = questionsNode.get(0).asText("抱歉~信息丢失了");
                }
                aiChat.setContent(firstQuestion);
                aiChat.setStatus(2);
                chatMapper.updateById(aiChat);
                res.add("need_more_info");
                res.add(firstQuestion);
                return res;
            }

            // 场景3：普通对话 - 优先取 result.data.reply，没有则取 result.data.data.reply，再没有则取 result.reply
            String reply = dataNode.path("reply").asText(null);
            if (reply == null || reply.isEmpty()) {
                reply = innerDataNode.path("reply").asText(null);
            }
            if (reply == null || reply.isEmpty()) {
                reply = resultNode.path("reply").asText("");
            }

            aiChat.setContent(reply);
            aiChat.setStatus(2);
            chatMapper.updateById(aiChat);
            res.add("normal_chat");
            res.add(reply);
            return res;

        } catch (Exception e) {
            log.error("保存聊天结果异常", e);
            Chat aiChat = new Chat();
            aiChat.setId(aiChatId);
            aiChat.setStatus(3);
            chatMapper.updateById(aiChat);
            return null;
        }
    }

    /**
     * 超级智能体请求处理：多资源生成
     * 根据rsArray中的资源类型创建占位记录，异步调用Python超级智能体，
     * 解析结果后保存到数据库并更新AI聊天回复
     */
    private Map<String, Object> handleSuperAgentRequest(ChatDTO chatDTO, Chat aiChat) {
        String userIdStr = chatDTO.getUserId().toString();
        Long userId = chatDTO.getUserId();
        List<Integer> rsArray = chatDTO.getRsArray();

        //删除预先创建的aiChat记录，超级智能体需要为每个资源类型创建独立的记录
        chatMapper.deleteById(aiChat.getId());

        Map<String, Object> res = new HashMap<>();
        res.put("rsType", 99);

        List<Map<String, Object>> detail = new ArrayList<>();
        // rsType -> taskId 的映射，用于异步保存结果
        Map<Integer, Object> rsTypeToTaskId = new HashMap<>();
        Map<Integer, String> rsTypeToBatchId = new HashMap<>();
        // rsType -> aiChatId 的映射，用于异步更新AI聊天回复
        Map<Integer, Long> rsTypeToAiChatId = new HashMap<>();

        for (Integer rsType : rsArray) {
            //学习计划不能多个生成，跳过
            if (rsType == 8) continue;

            //为每个资源类型创建独立的AI聊天记录
            Chat resourceAiChat = new Chat();
            resourceAiChat.setUserId(userId);
            resourceAiChat.setType("ai");
            resourceAiChat.setContent("正在根据您的特征信息来生成资源...");
            resourceAiChat.setRsType(rsType);
            resourceAiChat.setIsBatchGenerate(true);
            resourceAiChat.setStatus(1);
            resourceAiChat.setCreateTime(LocalDateTime.now());
            chatMapper.insert(resourceAiChat);
            rsTypeToAiChatId.put(rsType, resourceAiChat.getId());

            Map<String, Object> detailItem = new HashMap<>();
            detailItem.put("type", "ai");
            detailItem.put("content", "正在根据您的特征信息来生成资源...");
            detailItem.put("rsType", rsType);

            Map<String, Object> resource = new HashMap<>();
            resource.put("status", resourceAiChat.getStatus());

            switch (rsType) {
                case 0:
                    //PPT：创建占位记录
                    Ppt ppt = new Ppt();
                    ppt.setUserId(userId);
                    ppt.setPptTitle(chatDTO.getText());
                    ppt.setStatus(PptStatusConstant.PPT_STATUS_GENERATING);
                    ppt.setCreatedAt(String.valueOf(LocalDateTime.now()));
                    pptMapper.insert(ppt);
                    resource.put("taskId", ppt.getId());
                    rsTypeToTaskId.put(0, ppt.getId());
                    break;
                case 1:
                    //思维导图：创建占位记录
                    MindMap mindMap = new MindMap();
                    mindMap.setUserId(userId);
                    mindMap.setText(chatDTO.getText());
                    mindMap.setStatus(MindMapConstant.MindMap_STATUS_GENERATING);
                    mindMap.setCreateTime(LocalDateTime.now());
                    mindMapMapper.insert(mindMap);
                    resource.put("taskId", mindMap.getId());
                    rsTypeToTaskId.put(1, mindMap.getId());
                    break;
                case 2:
                    //讲解文档：创建占位记录
                    Word word = new Word();
                    word.setUserId(userId);
                    word.setText(chatDTO.getText());
                    word.setStatus(1);
                    word.setCreateTime(LocalDateTime.now());
                    wordMapper.insert(word);
                    resource.put("taskId", word.getId());
                    rsTypeToTaskId.put(2, word.getId());
                    break;
                case 3:
                    //拓展阅读：创建占位记录
                    ExtensionReading ext = ExtensionReading.builder()
                            .userId(userId)
                            .text(chatDTO.getText())
                            .status(1)
                            .createTime(LocalDateTime.now())
                            .build();
                    extensionReadingMapper.insert(ext);
                    resource.put("taskId", ext.getId());
                    rsTypeToTaskId.put(3, ext.getId());
                    break;
                case 4:
                    //编程题：创建占位记录
                    Practice practice = Practice.builder()
                            .userId(userId)
                            .text(chatDTO.getText())
                            .status(1)
                            .createTime(LocalDateTime.now())
                            .build();
                    practiceMapper.insert(practice);
                    resource.put("taskId", practice.getId());
                    rsTypeToTaskId.put(4, practice.getId());
                    break;
                case 5:
                    //视频：创建占位记录
                    String batchId = UUID.randomUUID().toString().replace("-", "");
                    Video taskRecord = new Video();
                    taskRecord.setUserId(userId);
                    taskRecord.setText(chatDTO.getText());
                    taskRecord.setBatchId(batchId);
                    taskRecord.setStatus(1);
                    taskRecord.setCreateTime(LocalDateTime.now());
                    videoMapper.insert(taskRecord);
                    resource.put("taskId", batchId);
                    rsTypeToBatchId.put(5, batchId);
                    rsTypeToTaskId.put(5, taskRecord.getId());
                    break;
                case 7:
                    //理论题：创建占位记录
                    PaperPO paperPO = new PaperPO();
                    paperPO.setUserId(userId.intValue());
                    paperPO.setPaperName(chatDTO.getText());
                    paperPO.setStatus(1);
                    paperPO.setCreateTime(LocalDateTime.now());
                    paperMapper.insert(paperPO);
                    resource.put("taskId", paperPO.getId());
                    rsTypeToTaskId.put(7, paperPO.getId());
                    break;
                default:
                    resource.put("taskId", null);
                    break;
            }

            detailItem.put("resource", resource);
            detail.add(detailItem);

            //更新对应的AI聊天记录，存储taskId
            Long aiChatId = rsTypeToAiChatId.get(rsType);
            if (aiChatId != null) {
                Chat updateChat = new Chat();
                updateChat.setId(aiChatId);
                updateChat.setResource(resource);
                Object taskIdObj = resource.get("taskId");
                updateChat.setTaskId(taskIdObj == null ? "" : taskIdObj.toString());
                chatMapper.updateById(updateChat);
            }
        }

        res.put("detail", detail);

        //检查是否有SSE连接，用于转发事件给前端
        boolean hasSseConnection = sseConnectionService.isConnected(userIdStr);

        //异步调用Python超级智能体
        AsyncUtil.execute(() -> {
            try {
                Map<String, Object> pythonParam = new HashMap<>();
                pythonParam.put("user_id", userIdStr);
                pythonParam.put("user_input", chatDTO.getText());

                pythonSseClient.consumePostSse("/chat", pythonParam, jsonData -> {
                    try {
                        //如果有SSE连接，将每个事件转发给前端
                        if (hasSseConnection) {
                            sseConnectionService.sendMessage(userIdStr, "super_agent_stream", jsonData);
                        }

                        JsonNode root = objectMapper.readTree(jsonData);
                        String eventType = root.path("type").asText("");
                        if ("task_result".equals(eventType)) {
                            JsonNode resultNode = root.path("result");
                            if (!resultNode.isMissingNode()) {
                                String reply = resultNode.path("reply").asText("");
                                //按句号分割reply，过滤空白片段
                                String[] replyParts = reply.split("。");
                                List<String> validParts = new ArrayList<>();
                                for (String part : replyParts) {
                                    String trimmed = part.trim();
                                    if (!trimmed.isEmpty()) {
                                        validParts.add(trimmed);
                                    }
                                }

                                JsonNode resourcesNode = resultNode.path("resources");

                                //异步保存各资源到数据库
                                if (!resourcesNode.isMissingNode() && resourcesNode.isObject()) {
                                    //记录已处理的资源索引，用于匹配reply分割片段
                                    int replyIndex = 0;
                                    Iterator<Map.Entry<String, JsonNode>> fields = resourcesNode.fields();
                                    while (fields.hasNext()) {
                                        Map.Entry<String, JsonNode> entry = fields.next();
                                        String resourceKey = entry.getKey();
                                        JsonNode resourceData = entry.getValue();
                                        Integer mappedRsType = mapResourceKeyToRsType(resourceKey);
                                        if (mappedRsType != null) {
                                            saveSuperAgentResource(mappedRsType, rsTypeToTaskId, rsTypeToBatchId,
                                                    userId, chatDTO.getText(), resourceData);
                                            //更新对应AI聊天记录的回复内容：优先使用summary，否则使用reply分割片段
                                            Long mappedAiChatId = rsTypeToAiChatId.get(mappedRsType);
                                            if (mappedAiChatId != null) {
                                                String content = resourceData.path("summary").asText(null);
                                                if (content == null || content.isEmpty()) {
                                                    //使用reply按句号分割的对应片段
                                                    if (replyIndex < validParts.size()) {
                                                        content = validParts.get(replyIndex);
                                                    } else {
                                                        content = reply;
                                                    }
                                                }
                                                replyIndex++;
                                                Chat updateChat = new Chat();
                                                updateChat.setId(mappedAiChatId);
                                                updateChat.setContent(content);
                                                updateChat.setStatus(2);
                                                chatMapper.updateById(updateChat);
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    } catch (Exception e) {
                        log.error("超级智能体处理SSE事件失败", e);
                    }
                });
            } catch (Exception e) {
                log.error("超级智能体SSE调用失败", e);
                //更新所有AI聊天记录为失败状态
                for (Map.Entry<Integer, Long> entry : rsTypeToAiChatId.entrySet()) {
                    Chat failChat = new Chat();
                    failChat.setId(entry.getValue());
                    failChat.setContent("超级智能体处理异常，请稍后重试");
                    failChat.setStatus(3);
                    chatMapper.updateById(failChat);
                }
            }
        });

        return res;
    }

    /**
     * 将Python返回的资源key映射为rsType
     */
    private Integer mapResourceKeyToRsType(String resourceKey) {
        switch (resourceKey) {
            case "search_video": return 5;
            case "generate_practice": return 4;
            case "generate_mindmap": return 1;
            case "generate_ppt": return 0;
            case "generate_document": return 2;
            case "generate_extension": return 3;
            case "generate_animation": return 6;
            case "generate_questions": return 7;
            default:
                log.warn("未知的超级智能体资源类型: {}", resourceKey);
                return null;
        }
    }

    /**
     * 保存超级智能体返回的资源数据到数据库
     */
    private void saveSuperAgentResource(Integer rsType, Map<Integer, Object> rsTypeToTaskId,
                                        Map<Integer, String> rsTypeToBatchId, Long userId, String text,
                                        JsonNode resourceData) {
        try {
            switch (rsType) {
                case 0:
                    Long pptId = (Long) rsTypeToTaskId.get(0);
                    if (pptId != null) {
                        saveSuperAgentPptResult(pptId, resourceData);
                    }
                    break;
                case 1:
                    Long mindMapId = (Long) rsTypeToTaskId.get(1);
                    if (mindMapId != null) {
                        saveSuperAgentMindMapResult(mindMapId, resourceData);
                    }
                    break;
                case 2:
                    Long wordId = (Long) rsTypeToTaskId.get(2);
                    if (wordId != null) {
                        saveSuperAgentWordResult(wordId, resourceData);
                    }
                    break;
                case 3:
                    Long extId = (Long) rsTypeToTaskId.get(3);
                    if (extId != null) {
                        saveSuperAgentExtensionResult(extId, resourceData);
                    }
                    break;
                case 4:
                    Long practiceId = (Long) rsTypeToTaskId.get(4);
                    if (practiceId != null) {
                        saveSuperAgentPracticeResult(practiceId, resourceData);
                    }
                    break;
                case 5:
                    Long videoRecordId = (Long) rsTypeToTaskId.get(5);
                    String batchId = rsTypeToBatchId.get(5);
                    if (videoRecordId != null && batchId != null) {
                        saveSuperAgentVideoResult(videoRecordId, userId, text, batchId, resourceData);
                    }
                    break;
                case 7:
                    Integer paperId = (Integer) rsTypeToTaskId.get(7);
                    if (paperId != null) {
                        saveSuperAgentPaperResult(paperId, resourceData);
                    }
                    break;
                default:
                    log.info("超级智能体资源类型 {} 暂未实现保存逻辑", rsType);
                    break;
            }
        } catch (Exception e) {
            log.error("保存超级智能体资源失败, rsType: {}", rsType, e);
        }
    }

    /**
     * 保存超级智能体返回的编程题结果
     */
    private void saveSuperAgentPracticeResult(Long practiceId, JsonNode resourceData) {
        try {
            Practice practice = practiceMapper.selectById(practiceId);
            if (practice == null || practice.getStatus() == 2) return;

            JsonNode practiceNode = resourceData.path("practice");
            if (practiceNode.isMissingNode()) return;

            String problemId = practiceNode.path("problem_id").asText(null);
            String title = practiceNode.path("title").asText("");
            String difficulty = practiceNode.path("difficulty").asText("");
            String description = practiceNode.path("description").asText("");
            String inputFormat = practiceNode.path("input_format").asText("");
            String outputFormat = practiceNode.path("output_format").asText("");

            JsonNode hintsNode = practiceNode.path("hints");
            JsonNode kpNode = practiceNode.path("knowledge_points");
            JsonNode examplesNode = practiceNode.path("examples");

            practice.setProblemId(problemId);
            practice.setTitle(title);
            practice.setText(title);
            practice.setDifficulty(difficulty);
            practice.setDescription(description);
            practice.setInputFormat(inputFormat);
            practice.setOutputFormat(outputFormat);
            practice.setStatus(2);
            practice.setHints(objectMapper.convertValue(hintsNode, new com.fasterxml.jackson.core.type.TypeReference<List<String>>() {}));
            practice.setKnowledgePoints(objectMapper.convertValue(kpNode, new com.fasterxml.jackson.core.type.TypeReference<List<String>>() {}));
            practiceMapper.updateById(practice);

            //保存示例
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

            log.info("超级智能体编程题结果保存成功, practiceId: {}", practiceId);
        } catch (Exception e) {
            log.error("保存超级智能体编程题结果异常", e);
            Practice practice = new Practice();
            practice.setId(practiceId);
            practice.setStatus(3);
            practiceMapper.updateById(practice);
        }
    }

    /**
     * 保存超级智能体返回的视频结果
     */
    private void saveSuperAgentVideoResult(Long taskRecordId, Long userId, String text,
                                           String batchId, JsonNode resourceData) {
        try {
            JsonNode videosNode = resourceData.path("videos");
            if (videosNode.isMissingNode() || !videosNode.isArray() || videosNode.isEmpty()) {
                Video taskRecord = new Video();
                taskRecord.setId(taskRecordId);
                taskRecord.setStatus(2);
                videoMapper.updateById(taskRecord);
                return;
            }

            for (JsonNode videoNode : videosNode) {
                Video video = new Video();
                video.setUserId(userId);
                video.setText(videoNode.path("title").asText(null));
                video.setBatchId(batchId);
                video.setTitle(videoNode.path("title").asText(null));
                video.setUrl(videoNode.path("url").asText(null));
                video.setThumbnail(videoNode.path("thumbnail").asText(null));
                video.setDuration(videoNode.path("duration").asText(null));
                video.setAuthor(videoNode.path("author").asText(null));
                video.setPlayCount(videoNode.path("play_count").asText(null));
                video.setDescription(videoNode.path("description").asText(null));
                video.setStatus(2);
                video.setCreateTime(LocalDateTime.now());
                videoMapper.insert(video);
            }

            Video taskRecord = new Video();
            taskRecord.setId(taskRecordId);
            taskRecord.setStatus(2);
            videoMapper.updateById(taskRecord);

            log.info("超级智能体视频结果保存成功, taskRecordId: {}, batchId: {}", taskRecordId, batchId);
        } catch (Exception e) {
            log.error("保存超级智能体视频结果异常", e);
            Video taskRecord = new Video();
            taskRecord.setId(taskRecordId);
            taskRecord.setStatus(3);
            videoMapper.updateById(taskRecord);
        }
    }

    /**
     * 保存超级智能体返回的讲解文档结果
     */
    private void saveSuperAgentWordResult(Long wordId, JsonNode resourceData) {
        try {
            Word word = wordMapper.selectById(wordId);
            if (word == null || word.getStatus() == 2) return;

            JsonNode documentNode = resourceData.path("document");
            if (documentNode.isMissingNode()) {
                word.setStatus(3);
                wordMapper.updateById(word);
                return;
            }

            String resourceId = documentNode.path("resource_id").asText(null);
            String ossUrl = documentNode.path("oss_url").asText(null);
            String docContent = documentNode.path("doc_content").asText(null);
            String title = documentNode.path("title").asText(null);

            word.setResourceId(resourceId);
            word.setOssUrl(ossUrl);
            word.setLongText(docContent);
            if (title != null && !title.isEmpty()) {
                word.setText(title);
            }
            word.setStatus(2);
            wordMapper.updateById(word);

            log.info("超级智能体讲解文档结果保存成功, wordId: {}", wordId);
        } catch (Exception e) {
            log.error("保存超级智能体讲解文档结果异常", e);
            Word word = new Word();
            word.setId(wordId);
            word.setStatus(3);
            wordMapper.updateById(word);
        }
    }

    /**
     * 保存超级智能体返回的拓展阅读结果
     */
    private void saveSuperAgentExtensionResult(Long extId, JsonNode resourceData) {
        try {
            ExtensionReading ext = extensionReadingMapper.selectById(extId);
            if (ext == null || ext.getStatus() == 2) return;

            JsonNode readingNode = resourceData.path("reading_material");
            if (readingNode.isMissingNode()) {
                ext.setStatus(3);
                extensionReadingMapper.updateById(ext);
                return;
            }

            String resourceId = readingNode.path("resource_id").asText(null);
            String title = readingNode.path("title").asText(null);
            String background = readingNode.path("background").asText(null);
            String knowledgeDistinguish = readingNode.path("knowledge_distinguish").asText(null);
            String principleExtend = readingNode.path("principle_extend").asText(null);
            String mistakeAvoid = readingNode.path("mistake_avoid").asText(null);
            String applicationScene = readingNode.path("application_scene").asText(null);
            String personalSuggest = readingNode.path("personal_suggest").asText(null);

            ext.setResourceId(resourceId);
            ext.setTitle(title);
            if (title != null && !title.isEmpty()) {
                ext.setText(title);
            }
            ext.setBackground(background);
            ext.setKnowledgeDistinguish(knowledgeDistinguish);
            ext.setPrincipleExtend(principleExtend);
            ext.setMistakeAvoid(mistakeAvoid);
            ext.setApplicationScene(applicationScene);
            ext.setPersonalSuggest(personalSuggest);
            ext.setStatus(2);
            extensionReadingMapper.updateById(ext);

            log.info("超级智能体拓展阅读结果保存成功, extId: {}", extId);
        } catch (Exception e) {
            log.error("保存超级智能体拓展阅读结果异常", e);
            ExtensionReading ext = ExtensionReading.builder()
                    .id(extId)
                    .status(3)
                    .build();
            extensionReadingMapper.updateById(ext);
        }
    }

    /**
     * 保存超级智能体返回的PPT结果
     */
    private void saveSuperAgentPptResult(Long pptId, JsonNode resourceData) {
        try {
            Ppt ppt = pptMapper.selectById(pptId);
            if (ppt == null || ppt.getStatus() == PptStatusConstant.PPT_STATUS_GENERATED) return;

            JsonNode pptNode = resourceData.path("ppt");
            if (pptNode.isMissingNode()) {
                ppt.setStatus(PptStatusConstant.PPT_STATUS_FAILED);
                pptMapper.updateById(ppt);
                return;
            }

            String status = pptNode.path("status").asText("");
            if ("success".equals(status)) {
                String resourceId = pptNode.path("resource_id").asText(null);
                String topic = pptNode.path("topic").asText(null);
                int pages = pptNode.path("pages").asInt(0);
                String ossUrl = pptNode.path("oss_url").asText(null);

                ppt.setResourceId(resourceId);
                ppt.setPptTitle(topic);
                ppt.setPageCount(pages);
                ppt.setOssUrl(ossUrl);
                ppt.setStatus(PptStatusConstant.PPT_STATUS_GENERATED);

                // 异步将PPT第一张幻灯片转换为图片并上传OSS
                if (ossUrl != null && !ossUrl.isEmpty()) {
                    AsyncUtil.execute(() -> {
                        try {
                            String firstImageOssUrl = convertFirstSlideToImage(ossUrl, pptId.toString());
                            Ppt updatePpt = new Ppt();
                            updatePpt.setId(pptId);
                            updatePpt.setImageUrl(firstImageOssUrl);
                            pptMapper.updateById(updatePpt);
                            log.info("PPT首图已上传OSS: {}", firstImageOssUrl);
                        } catch (Exception e) {
                            log.error("将PPT第一张幻灯片转换为图片失败", e);
                        }
                    });
                }
            } else {
                ppt.setStatus(PptStatusConstant.PPT_STATUS_FAILED);
            }

            pptMapper.updateById(ppt);
            log.info("超级智能体PPT结果保存成功, pptId: {}", pptId);
        } catch (Exception e) {
            log.error("保存超级智能体PPT结果异常", e);
            Ppt ppt = new Ppt();
            ppt.setId(pptId);
            ppt.setStatus(PptStatusConstant.PPT_STATUS_FAILED);
            pptMapper.updateById(ppt);
        }
    }

    /**
     * 将PPT第一张幻灯片转换为图片并上传OSS（复制自PptServiceImpl）
     */
    private String convertFirstSlideToImage(String pptUrl, String pptId) throws Exception {
        URL url = new URL(pptUrl);
        try (InputStream is = url.openStream();
             org.apache.poi.xslf.usermodel.XMLSlideShow ppt = new org.apache.poi.xslf.usermodel.XMLSlideShow(is)) {

            org.apache.poi.xslf.usermodel.XSLFSlide firstSlide = ppt.getSlides().get(0);

            java.awt.Dimension pageSize = ppt.getPageSize();
            int width = pageSize.width;
            int height = pageSize.height;

            java.awt.image.BufferedImage image = new java.awt.image.BufferedImage(width, height, java.awt.image.BufferedImage.TYPE_INT_RGB);
            java.awt.Graphics2D graphics = image.createGraphics();

            try {
                graphics.setPaint(java.awt.Color.WHITE);
                graphics.fill(new java.awt.Rectangle(0, 0, width, height));

                graphics.setRenderingHint(java.awt.RenderingHints.KEY_ANTIALIASING, java.awt.RenderingHints.VALUE_ANTIALIAS_ON);
                graphics.setRenderingHint(java.awt.RenderingHints.KEY_TEXT_ANTIALIASING, java.awt.RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
                graphics.setRenderingHint(java.awt.RenderingHints.KEY_RENDERING, java.awt.RenderingHints.VALUE_RENDER_QUALITY);
                graphics.setRenderingHint(java.awt.RenderingHints.KEY_FRACTIONALMETRICS, java.awt.RenderingHints.VALUE_FRACTIONALMETRICS_ON);

                firstSlide.draw(graphics);

                ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
                javax.imageio.ImageIO.write(image, "png", outputStream);
                byte[] imageBytes = outputStream.toByteArray();

                String fileName = "ppt/image/" + pptId + "_" + UUID.randomUUID().toString() + ".png";
                return aliOssUtil.upload(imageBytes, fileName);
            } finally {
                graphics.dispose();
            }
        }
    }

    /**
     * 保存超级智能体返回的思维导图结果
     */
    private void saveSuperAgentMindMapResult(Long mindMapId, JsonNode resourceData) {
        try {
            MindMap mindMap = mindMapMapper.selectById(mindMapId);
            if (mindMap == null || mindMap.getStatus() == MindMapConstant.MindMap_STATUS_GENERATED) return;

            JsonNode mindmapNode = resourceData.path("mindmap");
            if (mindmapNode.isMissingNode() || mindmapNode.isNull()) {
                mindMap.setStatus(MindMapConstant.MindMap_STATUS_FAILED);
                mindMapMapper.updateById(mindMap);
                return;
            }

            String resourceId = mindmapNode.path("resource_id").asText(null);
            String title = mindmapNode.path("name").asText(null);
            mindMap.setValue(mindmapNode.toString());
            mindMap.setResourceId(resourceId);
            if (title != null && !title.isEmpty()) {
                mindMap.setText(title);
            }
            mindMap.setStatus(MindMapConstant.MindMap_STATUS_GENERATED);
            mindMapMapper.updateById(mindMap);

            log.info("超级智能体思维导图结果保存成功, mindMapId: {}", mindMapId);
        } catch (Exception e) {
            log.error("保存超级智能体思维导图结果异常", e);
            MindMap mindMap = new MindMap();
            mindMap.setId(mindMapId);
            mindMap.setStatus(MindMapConstant.MindMap_STATUS_FAILED);
            mindMapMapper.updateById(mindMap);
        }
    }

    /**
     * 保存超级智能体返回的理论题结果
     */
    private void saveSuperAgentPaperResult(Integer paperId, JsonNode resourceData) {
        try {
            PaperPO paperPO = paperMapper.selectById(paperId);
            if (paperPO == null || paperPO.getStatus() == 2) return;

            JsonNode questionsNode = resourceData.path("questions");
            if (questionsNode.isMissingNode() || questionsNode.isNull()) {
                PaperPO updatePaper = new PaperPO();
                updatePaper.setId(paperId);
                updatePaper.setStatus(3);
                paperMapper.updateById(updatePaper);
                return;
            }

            String resourceId = questionsNode.path("resource_id").asText(null);
            String summary = resourceData.path("summary").asText(null);

            //单选题
            JsonNode singleNode = questionsNode.path("single_choice");
            if (singleNode.isArray()) {
                List<SingleChoicePO> singlePOList = new ArrayList<>();
                for (JsonNode item : singleNode) {
                    SingleChoicePO po = new SingleChoicePO();
                    po.setPaperId(paperId);
                    po.setQuestion(item.path("question").asText());
                    po.setAnswer(item.path("answer").asText());
                    JsonNode optNode = item.path("options");
                    if (optNode.isArray() && optNode.size() >= 4) {
                        po.setOptionA(optNode.get(0).asText());
                        po.setOptionB(optNode.get(1).asText());
                        po.setOptionC(optNode.get(2).asText());
                        po.setOptionD(optNode.get(3).asText());
                    }
                    singlePOList.add(po);
                }
                singleChoiceService.saveBatch(singlePOList);
            }

            //多选题
            JsonNode multiNode = questionsNode.path("multiple_choice");
            if (multiNode.isArray()) {
                List<MultipleChoicePO> multiPOList = new ArrayList<>();
                for (JsonNode item : multiNode) {
                    MultipleChoicePO po = new MultipleChoicePO();
                    po.setPaperId(paperId);
                    po.setQuestion(item.path("question").asText());
                    po.setAnswer(item.path("answer").asText());
                    JsonNode optNode = item.path("options");
                    if (optNode.isArray() && optNode.size() >= 4) {
                        po.setOptionA(optNode.get(0).asText());
                        po.setOptionB(optNode.get(1).asText());
                        po.setOptionC(optNode.get(2).asText());
                        po.setOptionD(optNode.get(3).asText());
                    }
                    multiPOList.add(po);
                }
                multipleChoiceService.saveBatch(multiPOList);
            }

            //判断题
            JsonNode judgeNode = questionsNode.path("judge");
            if (judgeNode.isArray()) {
                List<JudgePO> judgePOList = new ArrayList<>();
                for (JsonNode item : judgeNode) {
                    JudgePO po = new JudgePO();
                    po.setPaperId(paperId);
                    po.setQuestion(item.path("question").asText());
                    po.setAnswer(item.path("answer").asText());
                    judgePOList.add(po);
                }
                judgeService.saveBatch(judgePOList);
            }

            //填空题
            JsonNode blankNode = questionsNode.path("fill_blank");
            if (blankNode.isArray()) {
                List<FillBlankPO> blankPOList = new ArrayList<>();
                for (JsonNode item : blankNode) {
                    FillBlankPO po = new FillBlankPO();
                    po.setPaperId(paperId);
                    po.setQuestion(item.path("question").asText());
                    po.setAnswer(item.path("answer").asText());
                    blankPOList.add(po);
                }
                fillBlankService.saveBatch(blankPOList);
            }

            //简答题
            JsonNode shortNode = questionsNode.path("short_answer");
            if (shortNode.isArray()) {
                List<ShortAnswerPO> shortPOList = new ArrayList<>();
                for (JsonNode item : shortNode) {
                    ShortAnswerPO po = new ShortAnswerPO();
                    po.setPaperId(paperId);
                    po.setQuestion(item.path("question").asText());
                    po.setAnswer(item.path("answer").asText());
                    shortPOList.add(po);
                }
                shortAnswerService.saveBatch(shortPOList);
            }

            //全部题目入库成功，试卷改为成功
            PaperPO updatePaper = new PaperPO();
            updatePaper.setId(paperId);
            updatePaper.setResourceId(resourceId);
            if (summary != null && !summary.isEmpty()) {
                updatePaper.setPaperName(summary);
            }
            updatePaper.setStatus(2);
            paperMapper.updateById(updatePaper);

            log.info("超级智能体理论题结果保存成功, paperId: {}", paperId);
        } catch (Exception e) {
            log.error("保存超级智能体理论题结果异常", e);
            PaperPO updatePaper = new PaperPO();
            updatePaper.setId(paperId);
            updatePaper.setStatus(3);
            paperMapper.updateById(updatePaper);
        }
    }

    //工具方法: 判断是否为数字
    private static boolean isNumber(String str) {
        if (str == null || str.isEmpty()) return false;
        return str.matches("\\d+");
    }

    /**
     * 弹窗后的冲突解决（支持多种资源类型）
     * 0=PPT, 1=思维导图, 2=讲解文档/word, 3=拓展阅读, 4=编程题, 5=视频, 6=动画, 7=非编程题(理论题), 8=学习计划
     * @param userId 用户ID
     * @param conflictDTO 冲突解决请求
     */
    @Override
    public void handleConflict(Long userId, ConflictDTO conflictDTO) {
        log.info("处理弹窗冲突, userId: {}, conflictDTO: {}", userId, conflictDTO);

        Integer rsType = conflictDTO.getRsType();
        Boolean option = conflictDTO.getOption();
        Long resourceId = null;
        String createTime = null;
        if(isNumber(conflictDTO.getId())){
            //是数字
            resourceId = Long.parseLong(conflictDTO.getId());
        }else{
            //不是数字
            createTime = conflictDTO.getId();
        }

        log.info("前端传过来的option,{}", option);

        // 根据rsType判断资源类型，进行不同的冲突处理
        if (rsType == null) {
            log.warn("资源类型为空");
            return;
        }

        switch (rsType) {
            case 4:
                //编程题
                resolvePracticeConflict(resourceId, option);
                break;
            case 8:
                //学习计划
                resolveStudyPlanConflict(userId, createTime, option);
                break;
            default:
                log.warn("当前不支持该资源类型的冲突处理, rsType: {}", rsType);
                break;
        }
    }

    @Override
    public String getCreateTime(Integer userId, Integer rsType, Integer status) {
        Long chatId = chatMapper.getChatId(userId, rsType, status);
        if(chatId != null){
            return chatMapper.getCreateTime(chatId);
        }
        return "";
    }

    /**
     * 编程题冲突解决
     */
    private void resolvePracticeConflict(Long resourceId, Boolean option) {
        // 1. 根据id查询编程题记录
        Practice practice = practiceMapper.selectById(resourceId);
        if (practice == null) {
            log.warn("未找到编程题记录, id: {}", resourceId);
            return;
        }

        // 2. 清空 suggestion_warning 字段
        practice.setSuggestionWarning("1");
        practiceMapper.updateById(practice);
        if(practice.getSuggestionWarning().equals("1")){
            log.info("清空suggestion_warning成功, id: {}", resourceId);
        }else {
            log.warn("清空suggestion_warning失败, id: {}", resourceId);
            practice.setSuggestionWarning("1");
            practiceMapper.updateById(practice);
        }

        // 3. 构建发送给Python的请求参数
        String userIdStr = practice.getUserId().toString();
        boolean hasSseConnection = sseConnectionService.isConnected(userIdStr);

        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("user_id", userIdStr);
        requestBody.put("user_input", practice.getText());
        if(option){
            //简单题
            requestBody.put("confirmed", true);
            requestBody.put("override_suggestions", false);
            // 将text中的"困难"改为"简单"
            String originalText = practice.getText();
            if (originalText != null && originalText.contains("困难")) {
                String newText = originalText.replace("困难", "简单");
                practice.setText(newText);
                practiceMapper.updateById(practice);
                requestBody.put("user_input", newText);
            }
        }else {
            //困难题
            requestBody.put("confirmed", false);
            requestBody.put("override_suggestions", true);
        }

        // 4. 异步请求Python端，监听SSE流
        AsyncUtil.execute(() -> {
            try {
                pythonSseClient.consumePostSse("/chat", requestBody, jsonData -> {
                    // 如果有SSE连接，转发给前端
                    if (hasSseConnection) {
                        sseConnectionService.sendMessage(userIdStr, "practice_stream", jsonData);
                    }

                    // 监听 task_result 事件，保存到数据库
                    try {
                        JsonNode root = objectMapper.readTree(jsonData);
                        String eventType = root.path("type").asText("");
                        if ("task_result".equals(eventType)) {
                            JsonNode resultNode = root.path("result");
                            if (!resultNode.isMissingNode()) {
                                saveConflictPracticeResult(practice.getId(), resultNode);
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
    }

    /**
     * 学习计划冲突解决
     * 根据userId和createTime查询对话记录，获取上一条用户消息作为user_input
     */
    private void resolveStudyPlanConflict(Long userId, String createTime, Boolean option) {
        log.info("开始处理学习计划冲突, userId: {}, createTime: {}, option: {}", userId, createTime, option);

        // 1. 根据userId和createTime查询学习计划的对话记录
        com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<Chat> queryWrapper =
                new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<>();
        // createTime可能是完整时间戳如"2026-07-14 16:41:14.261"，取日期部分比较
        String datePart = createTime.contains(" ") ? createTime.split(" ")[0] : createTime;
        queryWrapper.eq(Chat::getUserId, userId)
                .eq(Chat::getRsType, 8)
                .apply("DATE_FORMAT(create_time,'%Y-%m-%d') = {0}", datePart)
                .orderByDesc(Chat::getId)
                .last("LIMIT 1");
        Chat studyPlanChat = chatMapper.selectOne(queryWrapper);
        log.info("查询学习计划对话记录结果: {}", studyPlanChat != null ? "找到, id=" + studyPlanChat.getId() : "未找到");

        if (studyPlanChat == null) {
            log.warn("未找到学习计划的对话记录, userId: {}, createTime: {}", userId, createTime);
            return;
        }

        // 2. 获取上一条对话记录（用户输入）
        Long prevId = studyPlanChat.getId() - 1;
        Chat userChat = chatMapper.selectById(prevId);
        log.info("查询用户原始对话记录结果: prevId={}, {}", prevId, userChat != null ? "找到" : "未找到");

        if (userChat == null) {
            log.warn("未找到用户的原始对话记录, id: {}", prevId);
            return;
        }

        String userInput = userChat.getContent();
        log.info("用户原始输入: {}", userInput);
        String userIdStr = userId.toString();
        boolean hasSseConnection = sseConnectionService.isConnected(userIdStr);

        // 3. 构建发送给Python的请求参数
        Map<String, Object> requestBody = new HashMap<>();
        Map<String, Object> extraParams = new HashMap<>();
        requestBody.put("user_id", userIdStr);
        requestBody.put("user_input", userInput);
        requestBody.put("task_type", "study_plan");
        requestBody.put("confirmed", true);
        requestBody.put("override_suggestions", false);
        if(option){
            //接收：针对薄弱点制定学习计划
            extraParams.put("ignore_weak_points", false);
            extraParams.put("focus_weak_points", true);
        }else {
            //拒绝：按照原输入正常生成
            extraParams.put("ignore_weak_points", true);
            extraParams.put("focus_weak_points", false);
        }
        requestBody.put("extra_params", extraParams);
        log.info("学习计划冲突请求参数: {}", requestBody);

        // 4. 异步请求Python端，监听SSE流
        log.info("开始异步调用Python SSE...");
        AsyncUtil.execute(() -> {
            try {
                pythonSseClient.consumePostSse("/chat", requestBody, jsonData -> {
                    // 如果有SSE连接，转发给前端
                    if (hasSseConnection) {
                        sseConnectionService.sendMessage(userIdStr, "study_plan_stream", jsonData);
                    }

                    // 监听 task_result 事件（学习计划无Java端存储表，仅转发SSE消息）
                    try {
                        JsonNode root = objectMapper.readTree(jsonData);
                        String eventType = root.path("type").asText("");
                        if ("task_result".equals(eventType)) {
                            log.info("学习计划冲突解决完成, userId: {}", userId);
                        }
                    } catch (Exception e) {
                        log.error("处理SSE事件失败", e);
                    }
                });
            } catch (Exception e) {
                log.error("SSE流式调用Python失败", e);
            }
        });
    }

    /**
     * 保存冲突解决后的编程题结果到数据库
     */
    private void saveConflictPracticeResult(Long practiceId, JsonNode resultNode) {
        try {
            Practice practice = practiceMapper.selectById(practiceId);
            if (practice == null || practice.getStatus() == 2) return;

            JsonNode problemNode = resultNode.path("practice");

            // 无论Python返回什么，都强制将 suggestion_warning 置为 "1"
            practice.setSuggestionWarning("1");

            // 检查是否有新的 suggestion_warning，但不覆盖，保持为 "1"

            // 从 practice 节点取 problem_id
            String problemId = problemNode.path("problem_id").asText(null);
            if (problemId == null || problemId.isEmpty()) {
                problemId = resultNode.path("resource_id").asText(null);
            }

            String title = problemNode.path("title").asText("");
            String difficulty = problemNode.path("difficulty").asText("");
            String description = problemNode.path("description").asText("");
            String inputFormat = problemNode.path("input_format").asText("");
            String outputFormat = problemNode.path("output_format").asText("");

            JsonNode hintsNode = problemNode.path("hints");
            JsonNode kpNode = problemNode.path("knowledge_points");

            practice.setTitle(title);
            practice.setDifficulty(difficulty);
            practice.setDescription(description);
            practice.setInputFormat(inputFormat);
            practice.setOutputFormat(outputFormat);
            practice.setProblemId(problemId);
            practice.setStatus(2);
            practice.setHints(objectMapper.convertValue(hintsNode, new com.fasterxml.jackson.core.type.TypeReference<List<String>>() {}));
            practice.setKnowledgePoints(objectMapper.convertValue(kpNode, new com.fasterxml.jackson.core.type.TypeReference<List<String>>() {}));
            // 不管 option 是什么，强制保留 suggestion_warning 为 "1"
            practice.setSuggestionWarning("1");
            practiceMapper.updateById(practice);

            log.info("冲突解决后的编程题结果保存成功, practiceId: {}", practiceId);

        } catch (Exception e) {
            log.error("保存冲突解决后的编程题结果异常", e);
            Practice practice = new Practice();
            practice.setId(practiceId);
            practice.setStatus(3);
            practiceMapper.updateById(practice);
        }
    }

}
