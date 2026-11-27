package com.dhi.wha.server.Impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.dhi.wha.dto.ChatDTO;
import com.dhi.wha.dto.VideoDTO;
import com.dhi.wha.dto.VideoQuizDTO;
import com.dhi.wha.entity.Video;
import com.dhi.wha.entity.*;
import com.dhi.wha.mapper.VideoMapper;
import com.dhi.wha.mapper.PaperMapper;

import com.dhi.wha.server.SseConnectionService;
import com.dhi.wha.server.*;
import com.dhi.wha.server.VideoService;
import com.dhi.wha.utils.AsyncUtil;
import com.dhi.wha.utils.PythonRestClient;
import com.dhi.wha.utils.PythonSseClient;
import com.dhi.wha.vo.ChatResourceVO;
import com.dhi.wha.vo.VideoVO;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import javax.annotation.Resource;
import java.time.LocalDateTime;
import java.util.*;

import static java.util.List.of;

@Slf4j
@Service
public class VideoServiceImpl extends ServiceImpl<VideoMapper, Video> implements VideoService {

    @Autowired
    private VideoMapper videoMapper;

    @Autowired
    private PythonRestClient pythonRestClient;

    @Resource
    private PythonSseClient pythonSseClient;

    @Resource
    private SseConnectionService sseConnectionService;

    @Resource
    private ObjectMapper objectMapper;

    @Resource
    private TransactionTemplate transactionTemplate;

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


    @Override
    public List<Video> listByUserId(Long userId) {
        LambdaQueryWrapper<Video> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Video::getUserId, userId)
                .orderByDesc(Video::getCreateTime);
        return list(wrapper);
    }

    /**
     * 获取视频列表
     *
     * @param videoDTO
     * @return
     */
    @Override
    public Map<String, Object> getVideoByText(VideoDTO videoDTO) {
        String userIdStr = videoDTO.getUserId().toString();
        boolean hasSseConnection = sseConnectionService.isConnected(userIdStr);
        Long userId = videoDTO.getUserId();
        String userInput = videoDTO.getText();

        // ========== 1. 生成全局唯一批次ID（本次搜索唯一标识） ==========
        String batchId = UUID.randomUUID().toString().replace("-", "");

        // 2. 初始化一条任务记录（标记该批次搜索状态）
        Video taskRecord = new Video();
        taskRecord.setUserId(userId);
        taskRecord.setText(userInput);
        taskRecord.setBatchId(batchId);
        taskRecord.setStatus(1); // 1=搜索中
        taskRecord.setCreateTime(LocalDateTime.now());
        videoMapper.insert(taskRecord);

        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("user_id", userIdStr);
        requestBody.put("user_input", "帮我搜索" + userInput + "的视频");

        if (hasSseConnection) {
            // ========== SSE 连接已建立：通过 SSE 流式返回 + 存库 ==========
            AsyncUtil.execute(() -> {
                try {
                    pythonSseClient.consumePostSse("/chat", requestBody, jsonData -> {
                        // 1. 通过 SSE 连接转发给前端
                        sseConnectionService.sendMessage(userIdStr, "video_stream", jsonData);

                        // 2. 监听 task_result 事件，保存到数据库
                        try {
                            JsonNode root = objectMapper.readTree(jsonData);
                            String eventType = root.path("type").asText("");
                            if ("task_result".equals(eventType)) {
                                JsonNode resultNode = root.path("result");
                                if (!resultNode.isMissingNode()) {
                                    saveVideoResultFromJson(taskRecord.getId(), userId, userInput, batchId, resultNode);
                                }
                            }
                        } catch (Exception e) {
                            log.error("处理SSE事件失败", e);
                        }
                    });
                } catch (Exception e) {
                    log.error("SSE流式调用Python失败", e);
                    taskRecord.setStatus(3);
                    videoMapper.updateById(taskRecord);
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
                                    saveVideoResultFromJson(taskRecord.getId(), userId, userInput, batchId, resultNode);
                                }
                            }
                        } catch (Exception e) {
                            log.error("处理SSE事件失败", e);
                        }
                    });
                } catch (Exception e) {
                    log.error("SSE流式调用Python失败", e);
                    taskRecord.setStatus(3);
                    videoMapper.updateById(taskRecord);
                }
            });
        }

        // ========== 4. 立即返回批次ID给前端，用于轮询 ==========
        Map<String, Object> result = new HashMap<>();
        result.put("batchId", batchId);
        result.put("status", 1);
        result.put("msg", "视频正在搜索中，请稍后查询");
        return result;
    }

    /**
     * 轮询视频列表
     *
     * @param batchId
     * @return
     */
    @Override
    public List<Video> pollVideoByBatchId(String batchId) {

        LambdaQueryWrapper<Video> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Video::getBatchId, batchId)
                .eq(Video::getStatus, 2)
                .isNotNull(Video::getTitle)
                .orderByAsc(Video::getCreateTime);
        List<Video> videoList = list(wrapper);

        if (videoList.isEmpty()) {
            LambdaQueryWrapper<Video> taskWrapper = new LambdaQueryWrapper<>();
            taskWrapper.eq(Video::getBatchId, batchId)
                    .isNull(Video::getTitle);
            List<Video> taskRecords = list(taskWrapper);
            if (!taskRecords.isEmpty()) {
                Video taskRecord = taskRecords.get(0);
                if (taskRecord.getSuggestionWarning() != null && !"null".equals(taskRecord.getSuggestionWarning())) {
                    Video warningVideo = new Video();
                    warningVideo.setId(taskRecord.getId());
                    warningVideo.setStatus(taskRecord.getStatus());
                    warningVideo.setSuggestionWarning(taskRecord.getSuggestionWarning());
                    videoList.add(warningVideo);
                }
            }
        }

        return videoList;
    }

    /**
     * 获取视频列表
     *
     * @param userId
     * @return
     */
    @Override
    public List<VideoVO> getListByUserId(Long userId) {
        //1. 根据userId查询视频列表
        return videoMapper.getListByUserId(userId);
    }

    /**
     * 保存视频
     *
     * @param chatDTO
     * @return
     */
    @Override
    public String saveVideo(ChatDTO chatDTO) {
        String userIdStr = chatDTO.getUserId().toString();
        boolean hasSseConnection = sseConnectionService.isConnected(userIdStr);
        Long userId = chatDTO.getUserId();
        String userInput = chatDTO.getText();

        // ========== 1. 生成全局唯一批次ID（本次搜索唯一标识） ==========
        String batchId = UUID.randomUUID().toString().replace("-", "");

        // 2. 初始化一条任务记录（标记该批次搜索状态）
        Video taskRecord = new Video();
        taskRecord.setUserId(userId);
        taskRecord.setText(userInput);
        taskRecord.setBatchId(batchId);
        taskRecord.setStatus(1); // 1=搜索中
        taskRecord.setCreateTime(LocalDateTime.now());
        videoMapper.insert(taskRecord);

        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("user_id", userIdStr);
        requestBody.put("user_input", userInput);

        if (hasSseConnection) {
            // ========== SSE 连接已建立：通过 SSE 流式返回 + 存库 ==========
            AsyncUtil.execute(() -> {
                try {
                    pythonSseClient.consumePostSse("/chat", requestBody, jsonData -> {
                        // 1. 通过 SSE 连接转发给前端
                        sseConnectionService.sendMessage(userIdStr, "video_stream", jsonData);

                        // 2. 监听 task_result 事件，保存到数据库
                        try {
                            JsonNode root = objectMapper.readTree(jsonData);
                            String eventType = root.path("type").asText("");
                            if ("task_result".equals(eventType)) {
                                JsonNode resultNode = root.path("result");
                                if (!resultNode.isMissingNode()) {
                                    saveVideoResultFromJson(taskRecord.getId(), userId, userInput, batchId, resultNode);
                                }
                            }
                        } catch (Exception e) {
                            log.error("处理SSE事件失败", e);
                        }
                    });
                } catch (Exception e) {
                    log.error("SSE流式调用Python失败", e);
                    taskRecord.setStatus(3);
                    videoMapper.updateById(taskRecord);
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
                                    saveVideoResultFromJson(taskRecord.getId(), userId, userInput, batchId, resultNode);
                                }
                            }
                        } catch (Exception e) {
                            log.error("处理SSE事件失败", e);
                        }
                    });
                } catch (Exception e) {
                    log.error("SSE流式调用Python失败", e);
                    taskRecord.setStatus(3);
                    videoMapper.updateById(taskRecord);
                }
            });
        }

        return taskRecord.getBatchId();
    }

    /**
     * 删除批次任务
     *
     * @param batchId
     */
    @Override
    public void deleteByBatchId(String batchId) {
        videoMapper.delete(new LambdaQueryWrapper<Video>().eq(Video::getBatchId, batchId));
    }

    /**
     * 获取视频信息
     *
     * @param bvid
     * @param page
     * @return
     */
    @Override
    public Object getVideoInfo(String bvid, Integer page) {
        return pythonRestClient.getWithQueryParam("/api/play-info?bvid={bvid}&page={page}", bvid, page);
    }

    @Override
    public ChatResourceVO getVideoInfoById(String taskId) {
        return videoMapper.getVideoInfoById(taskId);
    }

    @Override
    public Video getByResourceId(String resourceId) {
        return videoMapper.getByResourceId(resourceId);
    }

    /**
     * 将 Python 返回的 result JSON 存入数据库
     */
    private void saveVideoResultFromJson(Long taskRecordId, Long userId, String userInput, String batchId, JsonNode resultNode) {
        try {
            JsonNode videoArrayNode;

            JsonNode resourcesNode = resultNode.path("resources");
            if (!resourcesNode.isMissingNode() && resourcesNode.isObject()) {
                JsonNode searchVideoNode = resourcesNode.path("search_video");
                if (!searchVideoNode.isMissingNode()) {
                    videoArrayNode = searchVideoNode.path("videos");
                } else {
                    videoArrayNode = resultNode.path("video");
                }
            } else {
                videoArrayNode = resultNode.path("video");
            }

            if (videoArrayNode.isMissingNode() || videoArrayNode.isEmpty() || !videoArrayNode.isArray()) {
                JsonNode warningNode = resultNode.path("suggestion_warning");
                if (!warningNode.isMissingNode() && !warningNode.isNull()) {
                    Video taskRecord = new Video();
                    taskRecord.setId(taskRecordId);
                    taskRecord.setSuggestionWarning(warningNode.asText());
                    taskRecord.setStatus(1);
                    videoMapper.updateById(taskRecord);
                } else {
                    Video taskRecord = new Video();
                    taskRecord.setId(taskRecordId);
                    taskRecord.setSuggestionWarning("");
                    taskRecord.setStatus(1);
                    videoMapper.updateById(taskRecord);
                }
                return;
            }

            String resourceId = resultNode.path("resource_id").asText(null);

            // 批量插入视频记录（事务保证原子性）
            Boolean success = transactionTemplate.execute(status -> {
                try {
                    for (JsonNode videoNode : videoArrayNode) {
                        Video video = new Video();
                        video.setUserId(userId);
                        video.setText(userInput);
                        video.setBatchId(batchId);
                        video.setTitle(videoNode.path("title").asText(null));
                        video.setUrl(videoNode.path("url").asText(null));
                        video.setThumbnail(videoNode.path("thumbnail").asText(null));
                        video.setDuration(videoNode.path("duration").asText(null));
                        video.setAuthor(videoNode.path("author").asText(null));
                        video.setPlayCount(videoNode.path("play_count").asText(null));
                        video.setDescription(videoNode.path("description").asText(null));
                        video.setResourceId(resourceId);
                        video.setStatus(2); // 2=成功
                        video.setCreateTime(LocalDateTime.now());
                        videoMapper.insert(video);
                    }

                    // 任务记录更新为完成
                    Video taskRecord = new Video();
                    taskRecord.setId(taskRecordId);
                    taskRecord.setStatus(2);
                    videoMapper.updateById(taskRecord);
                    return true;
                } catch (Exception e) {
                    status.setRollbackOnly();
                    throw e;
                }
            });

            if (!Boolean.TRUE.equals(success)) {
                Video taskRecord = new Video();
                taskRecord.setId(taskRecordId);
                taskRecord.setStatus(3);
                videoMapper.updateById(taskRecord);
            }

        } catch (Exception e) {
            log.error("保存视频结果异常", e);
            Video taskRecord = new Video();
            taskRecord.setId(taskRecordId);
            taskRecord.setStatus(3);
            videoMapper.updateById(taskRecord);
        }
    }

    /**
     * 获取视频综述
     * @param params 请求参数（包含bvid和page）
     * @return 视频综述数据
     */
    @Override
    public Object getSummary(Map<String, Object> params) {
        log.info("获取视频综述, params: {}", params);
        return pythonRestClient.post("/api/video-summary", params);
    }

    /**
     * 获取视频思维导图
     * @param params 请求参数（包含bvid和page）
     * @return 视频思维导图数据
     */
    @Override
    public Object getMindmap(Map<String, Object> params) {
        log.info("获取视频思维导图, params: {}", params);
        return pythonRestClient.post("/api/video-mindmap", params);
    }

    /**
     * 视频观看完成后生成小测试
     * @param videoQuizDTO 视频小测试请求参数
     * @return 测试题数据
     */
    @Override
    public Object postVideoQuiz(VideoQuizDTO videoQuizDTO) {
        log.info("视频观看完成后生成小测试, videoQuizDTO: {}", videoQuizDTO);

        Map<String, Object> pythonParam = new HashMap<>();
        pythonParam.put("user_id", videoQuizDTO.getUser_id());
        pythonParam.put("video_title", videoQuizDTO.getVideo_title());
        pythonParam.put("bvid", videoQuizDTO.getBvid());

        Object pythonResponse = pythonRestClient.post("/video/trigger-quiz", pythonParam);

        Map<String, Object> pythonMap = (Map<String, Object>) pythonResponse;
        Map<String, Object> questionMap = (Map<String, Object>) pythonMap.get("question");

        Long userId = Long.parseLong(videoQuizDTO.getUser_id().replace("user_", ""));

        PaperPO paper = new PaperPO();
        paper.setUserId(userId.intValue());
        // 提取集数放到前面，如 "标题 P1" -> "P1 - 标题"
        String videoTitle = videoQuizDTO.getVideo_title();
        java.util.regex.Matcher matcher = java.util.regex.Pattern.compile("^(.*?)\\s+(P\\d+)$").matcher(videoTitle);
        if (matcher.matches()) {
            paper.setPaperName(matcher.group(2) + " - " + matcher.group(1).trim());
        } else {
            paper.setPaperName(videoTitle);
        }
        paper.setCreateTime(LocalDateTime.now());
        paper.setStatus(1);
        paperMapper.insert(paper);

        Integer paperId = paper.getId();

        try {
            Map<String, Object> questions = (Map<String, Object>) questionMap.get("questions");

            if (questions != null && questions.containsKey("single_choice")) {
                List<Map<String, Object>> singleChoiceList = (List<Map<String, Object>>) questions.get("single_choice");
                if (singleChoiceList != null && !singleChoiceList.isEmpty()) {
                    List<SingleChoicePO> singlePOList = new ArrayList<>();
                    for (Map<String, Object> item : singleChoiceList) {
                        SingleChoicePO po = new SingleChoicePO();
                        po.setPaperId(paperId);
                        po.setQuestion((String) item.get("question"));
                        po.setAnswer((String) item.get("answer"));
                        List<String> options = (List<String>) item.get("options");
                        if (options != null && options.size() >= 4) {
                            po.setOptionA(options.get(0));
                            po.setOptionB(options.get(1));
                            po.setOptionC(options.get(2));
                            po.setOptionD(options.get(3));
                        }
                        singlePOList.add(po);
                    }
                    singleChoiceService.saveBatch(singlePOList);
                }
            }

            if (questions != null && questions.containsKey("multiple_choice")) {
                List<Map<String, Object>> multipleChoiceList = (List<Map<String, Object>>) questions.get("multiple_choice");
                if (multipleChoiceList != null && !multipleChoiceList.isEmpty()) {
                    List<MultipleChoicePO> multiPOList = new ArrayList<>();
                    for (Map<String, Object> item : multipleChoiceList) {
                        MultipleChoicePO po = new MultipleChoicePO();
                        po.setPaperId(paperId);
                        po.setQuestion((String) item.get("question"));
                        po.setAnswer((String) item.get("answer"));
                        List<String> options = (List<String>) item.get("options");
                        if (options != null && options.size() >= 4) {
                            po.setOptionA(options.get(0));
                            po.setOptionB(options.get(1));
                            po.setOptionC(options.get(2));
                            po.setOptionD(options.get(3));
                        }
                        multiPOList.add(po);
                    }
                    multipleChoiceService.saveBatch(multiPOList);
                }
            }

            if (questions != null && questions.containsKey("judge")) {
                List<Map<String, Object>> judgeList = (List<Map<String, Object>>) questions.get("judge");
                if (judgeList != null && !judgeList.isEmpty()) {
                    List<JudgePO> judgePOList = new ArrayList<>();
                    for (Map<String, Object> item : judgeList) {
                        JudgePO po = new JudgePO();
                        po.setPaperId(paperId);
                        po.setQuestion((String) item.get("question"));
                        po.setAnswer((String) item.get("answer"));
                        judgePOList.add(po);
                    }
                    judgeService.saveBatch(judgePOList);
                }
            }

            if (questions != null && questions.containsKey("fill_blank")) {
                List<Map<String, Object>> fillBlankList = (List<Map<String, Object>>) questions.get("fill_blank");
                if (fillBlankList != null && !fillBlankList.isEmpty()) {
                    List<FillBlankPO> blankPOList = new ArrayList<>();
                    for (Map<String, Object> item : fillBlankList) {
                        FillBlankPO po = new FillBlankPO();
                        po.setPaperId(paperId);
                        po.setQuestion((String) item.get("question"));
                        po.setAnswer((String) item.get("answer"));
                        blankPOList.add(po);
                    }
                    fillBlankService.saveBatch(blankPOList);
                }
            }

            if (questions != null && questions.containsKey("short_answer")) {
                List<Map<String, Object>> shortAnswerList = (List<Map<String, Object>>) questions.get("short_answer");
                if (shortAnswerList != null && !shortAnswerList.isEmpty()) {
                    List<ShortAnswerPO> shortPOList = new ArrayList<>();
                    for (Map<String, Object> item : shortAnswerList) {
                        ShortAnswerPO po = new ShortAnswerPO();
                        po.setPaperId(paperId);
                        po.setQuestion((String) item.get("question"));
                        po.setAnswer((String) item.get("answer"));
                        shortPOList.add(po);
                    }
                    shortAnswerService.saveBatch(shortPOList);
                }
            }

            PaperPO updatePaper = new PaperPO();
            updatePaper.setId(paperId);
            updatePaper.setStatus(2);
            paperMapper.updateById(updatePaper);

        } catch (Exception e) {
            log.error("保存视频小测试题目异常", e);
            PaperPO updatePaper = new PaperPO();
            updatePaper.setId(paperId);
            updatePaper.setStatus(3);
            paperMapper.updateById(updatePaper);
        }

        Map<String, Object> result = new HashMap<>();
        result.put("paperId", paperId);
        return result;
    }
}
