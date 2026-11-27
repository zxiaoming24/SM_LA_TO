package com.dhi.wha.business;

import com.dhi.wha.dto.ChatDTO;
import com.dhi.wha.dto.ExtensionReadingDTO;
import com.dhi.wha.server.*;
import com.dhi.wha.utils.AsyncUtil;
import com.dhi.wha.utils.PythonRestClient;
import com.dhi.wha.utils.PythonSseClient;
import com.dhi.wha.vo.ChatResourceVO;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import javax.annotation.Resource;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Component
@Slf4j
public class ResourceDispatcher {

    @Resource
    private ObjectMapper objectMapper;

    @Autowired
    private SseConnectionService sseConnectionService;

    @Autowired
    private PythonSseClient pythonSseClient;

    @Autowired
    private ChatService chatService;

    @Autowired
    private PythonRestClient pythonRestClient;

    @Resource
    private MindMapService mindMapService;

    @Resource
    private PptService pptService;

    @Resource
    private WordService wordService;

    @Resource
    private ExtensionReadingService extensionReadingService;

    @Resource
    private PracticeService practiceService;

    @Resource
    private VideoService videoService;

    @Resource
    private AnimationService animationService;

    @Resource
    private PaperService paperService;

    private Object studyPlanGenerating = null;


    public Map<String,Object> doCreateResource(Integer rsType, ChatDTO chatDTO){
        Map<String,Object> resource = new HashMap<>();
        resource.put("status",1);
        switch (rsType) {
            case 0:
                resource.put("msg","PPT生成中...");
                Long pptId = pptService.savePpt(chatDTO);
                resource.put("taskId",pptId);
                break;
            case 1:
                resource.put("msg","思维导图生成中...");
                Long mindMapId = mindMapService.saveMindMap(chatDTO);
                resource.put("taskId",mindMapId);
                break;
            case 2:
                resource.put("msg","讲解文档生成中...");
                Long wordId = wordService.saveWord(chatDTO);
                resource.put("taskId",wordId);
                break;
            case 3:
                resource.put("msg","拓展阅读材料生成中...");
                Long ExtensionReadingId = extensionReadingService.saveExtension(chatDTO);
                resource.put("taskId",ExtensionReadingId);
                break;
            case 4:
                resource.put("msg","编程题生成中...");
                Long practiceId = practiceService.savePractice(chatDTO);
                resource.put("taskId",practiceId);
                break;
            case 5:
                resource.put("msg","视频资源生成中...");
                String videoId = videoService.saveVideo(chatDTO);
                resource.put("taskId",videoId);
                break;
            case 6:
                resource.put("msg","动画资源生成中...");
                Long animationId = animationService.saveAnimation(chatDTO);
                resource.put("taskId",animationId);
                break;
            case 7:
                resource.put("msg","理论题生成中...");
                Long theoryId = paperService.saveTheoryId(chatDTO);
                resource.put("taskId",theoryId);
                break;
            case 8:
                resource.put("msg","学习计划生成中...");
                Object studyPlan = pythonRestClient.getWithPathParam("/study_plans/{user_id}", chatDTO.getUserId());
                Map<String, Object> dataMap = (Map<String, Object>) studyPlan;
                Integer count = (Integer) dataMap.get("count");
                resource.put("taskId",count);
                try {
                    AsyncUtil.execute(() -> {
                        Map<String, Object> requestBody = new HashMap<>();
                        requestBody.put("user_id", chatDTO.getUserId().toString());
                        requestBody.put("user_input", chatDTO.getText());
                        requestBody.put("enable_tts",false);
                        boolean hasSseConnection = sseConnectionService.isConnected(chatDTO.getUserId().toString());
                        try {
                            pythonSseClient.consumePostSse("/chat", requestBody, jsonData -> {
                                // 如果有SSE连接，转发给前端
                                if (hasSseConnection) {
                                    sseConnectionService.sendMessage(chatDTO.getUserId().toString(), "study_plan_stream", jsonData);
                                }

                                // 监听 task_result 事件（学习计划无Java端存储表，仅转发SSE消息）
                                try {
                                    JsonNode root = objectMapper.readTree(jsonData);
                                    String eventType = root.path("type").asText("");
                                    if ("task_result".equals(eventType)) {
                                        JsonNode resultNode = root.path("result");
                                        if (!resultNode.isMissingNode()) {
                                            studyPlanGenerating = objectMapper.convertValue(resultNode, Map.class);
                                        }
                                    }
                                } catch (Exception e) {
                                    log.error("处理SSE事件失败", e);
                                }
                            });
                        } catch (Exception e) {
                            log.error("SSE流式调用Python失败", e);
                        }
                    });
                }catch (Exception e){
                    log.info("异常: {e}", e);
                }
                break;
            default:
                resource.put("msg","资源生成错误");
        }
        return resource;
    }

    public ChatResourceVO getResourceId(String taskId, Integer rsType, Integer userId) {
        //1.判断是什么类型的资源
        switch (rsType) {
            case 0:
                //1.PPT,根据用户id和taskId查询
                return pptService.getPptInfoById(Integer.parseInt(taskId));
            case 1:
                //2.思维导图,根据用户id和taskId查询
                return mindMapService.getMindMapInfoById(Integer.parseInt(taskId));
            case 2:
                //3.讲解文档,根据用户id和taskId查询
                return wordService.getWordInfoById(Integer.parseInt(taskId));
            case 3:
                //4.拓展阅读材料,根据用户id和taskId查询
                return extensionReadingService.getExtensionInfoById(Integer.parseInt(taskId));
            case 4:
                //5.编程题,根据用户id和taskId查询
                return practiceService.getPracticeInfoById(Integer.parseInt(taskId));
            case 5:
                //6.视频资源,根据用户id和taskId查询
                return videoService.getVideoInfoById(taskId);
            case 6:
                //7.动画资源,根据用户id和taskId查询
                return animationService.getAnimationInfoById(Integer.parseInt(taskId));
            case 7:
                //8.理论题,根据用户id和taskId查询
                return paperService.getPaperInfoByUserIdAndTaskId(Integer.parseInt(taskId));
            case 8:
                //9.学习计划
                Object studyPlan = pythonRestClient.getWithPathParam("/study_plans/{user_id}", userId);
                Map<String, Object> dataMap = (Map<String, Object>) studyPlan;
                Integer count = (Integer) dataMap.get("count");
                ChatResourceVO chatResourceVO = new ChatResourceVO();
                if(count > Integer.parseInt(taskId)){
                    //如果满足条件，则返回状态为2
                    chatResourceVO.setStatus(2);
                    //从计划列表中找到最新的学习计划（按created_at排序取最新的）
                    List<Map<String, Object>> plans = (List<Map<String, Object>>) dataMap.get("plans");
                    String latestPlanId = null;
                    if (plans != null && !plans.isEmpty()) {
                        String latestCreatedAt = "";
                        for (Map<String, Object> plan : plans) {
                            String createdAt = (String) plan.get("created_at");
                            if (createdAt != null && createdAt.compareTo(latestCreatedAt) > 0) {
                                latestCreatedAt = createdAt;
                                latestPlanId = (String) plan.get("plan_id");
                            }
                        }
                    }
                    //使用最新计划的plan_id切换学习计划
                    if (latestPlanId != null) {
                        Map<String, Object> body = new HashMap<>();
                        body.put("plan_id", latestPlanId);
                        pythonRestClient.postWithPathParam("/study_plan/{user_id}/switch-plan",body,userId);
                    }
                }else{
                    //如果不满足条件，则返回状态为1
                    if(studyPlanGenerating != null) {
                        Map<String, Object> studyPlanGenerate = (Map<String, Object>) studyPlanGenerating;
                        List<Map<String, Object>> weakPointsInfo = (List<Map<String, Object>>) studyPlanGenerate.get("weak_points_info");
                        if (weakPointsInfo != null && !weakPointsInfo.isEmpty()) {
                            StringBuilder warningBuilder = new StringBuilder();
                            warningBuilder.append("检测到您的学习薄弱环节\n");
                            for (Map<String, Object> weakPoint : weakPointsInfo) {
                                String point = (String) weakPoint.get("point");
                                if (point != null) {
                                    warningBuilder.append(point).append("\n");
                                }
                            }
                            warningBuilder.append("您希望针对薄弱点制定学习计划吗\n");
                            warningBuilder.append("还是按照原输入正常生成\n");
                            chatResourceVO.setSuggestionWarning(warningBuilder.toString());
                        }
                        studyPlanGenerating = null;
                    }
                    chatResourceVO.setStatus(1);
                }
                String createTime = chatService.getCreateTime(userId,rsType,1);
                chatResourceVO.setCreateTime(createTime);
                return chatResourceVO;
            default:
                System.out.println("资源类型错误");
                return null;
        }
    }
}
