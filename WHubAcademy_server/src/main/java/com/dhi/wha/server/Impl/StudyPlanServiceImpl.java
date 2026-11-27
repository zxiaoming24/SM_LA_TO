package com.dhi.wha.server.Impl;

import com.alibaba.fastjson.JSON;
import com.dhi.wha.dto.AnswerFrontDTO;
import com.dhi.wha.dto.RegeneratePhaseDTO;
import com.dhi.wha.dto.StudyPlanDTO;
import com.dhi.wha.entity.ExtensionReading;
import com.dhi.wha.entity.MindMap;
import com.dhi.wha.entity.Practice;
import com.dhi.wha.entity.PracticeAnswer;
import com.dhi.wha.entity.Ppt;
import com.dhi.wha.entity.Video;
import com.dhi.wha.entity.Word;
import com.dhi.wha.mapper.WordMapper;
import com.dhi.wha.mapper.MindMapMapper;
import com.dhi.wha.mapper.PracticeMapper;
import com.dhi.wha.mapper.PracticeAnswerMapper;
import com.dhi.wha.mapper.PptMapper;
import com.dhi.wha.mapper.VideoMapper;
import com.dhi.wha.mapper.ExtensionReadingMapper;
import com.dhi.wha.server.StudyPlanService;
import com.dhi.wha.utils.AsyncUtil;
import com.dhi.wha.utils.PythonRestClient;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import com.dhi.wha.utils.AliOssUtil;
import org.apache.poi.xslf.usermodel.XMLSlideShow;
import org.apache.poi.xslf.usermodel.XSLFSlide;

import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.URL;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
@Slf4j
public class StudyPlanServiceImpl implements StudyPlanService {

    @Autowired
    private PythonRestClient pythonRestClient;

    @Autowired
    private WordMapper wordMapper;

    @Autowired
    private MindMapMapper mindMapMapper;

    @Autowired
    private PracticeMapper practiceMapper;

    @Autowired
    private PracticeAnswerMapper practiceAnswerMapper;

    @Autowired
    private VideoMapper videoMapper;

    @Autowired
    private ExtensionReadingMapper extensionReadingMapper;

    @Autowired
    private PptMapper pptMapper;

    @Autowired
    private AliOssUtil aliOssUtil;

    private static final ObjectMapper SNAKE_CASE_MAPPER;
    static {
        SNAKE_CASE_MAPPER = new ObjectMapper();
        SNAKE_CASE_MAPPER.setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE);
    }

    /**
     * 获取学习计划列表
     * @param userId
     * @return
     */
    @Override
    public Object getStudyPlanList(String userId) {
        return pythonRestClient.getWithPathParam("/study_plans/{user_id}", userId);
    }

    /**
     * 获取学习计划
     * @param userId
     * @param pathId
     * @return
     */
    @Override
    public Object getPathPlan(String userId, String pathId) {
        //1.先将当前计划置为活跃状态
        Map<String, Object> body = new HashMap<>();
        body.put("plan_id", pathId);
        pythonRestClient.postWithPathParam("/study_plan/{user_id}/switch-plan",body,userId);
        return pythonRestClient.getWithPathAndQueryParam("/study_plan/{user_id}?plan_id={pathId}", userId ,pathId);
    }

    /**
     * 创建学习计划
     * @param studyPlanDTO
     * @return
     */
    @Override
    public Object createPathPlan(StudyPlanDTO studyPlanDTO) {
        Map<String, Object> body = new HashMap<>();
        body.put("user_id", studyPlanDTO.getUserId());
        body.put("user_input", studyPlanDTO.getText());
        body.put("ignore_weak_points", true);
        body.put("focus_weak_points", false);
        body.put("enable_tts", false);
        return pythonRestClient.post("/study_plan/generate", body);
    }

    /**
     * 删除学习计划
     * @param userId
     * @param planId
     * @return
     */
    @Override
    public Object deleteStudyPlan(String userId, String planId) {
        return pythonRestClient.deleteWithPathParam("/study_plan/{user_id}/plan/{plan_id}",userId, planId);
    }

    /**
     * 获取学习计划当前阶段
     * @param userId
     * @param pathId
     * @return
     */
    @Override
    public Object getStudyPlanCurrentPhase(String userId, String pathId) {
        return pythonRestClient.getWithPathAndQueryParam("/study_plan/{user_id}/summary?plan_id={pathId}", userId ,pathId);
    }

    /**
     * 获取学习计划完成度
     * @param userId
     * @param phaseIndex
     * @param planId
     * @return
     */
    public Object getStudyPlanCompletion(String userId, Integer phaseIndex, String planId) {
        Map<String, Object> body = new HashMap<>();
        body.put("plan_id", planId);
        body.put("phase_index", phaseIndex);   // ← 加这一行
        pythonRestClient.postWithPathParam("/study_plan/{user_id}/switch-plan",body,userId);
        return pythonRestClient.getWithPathParam("/study_plan/{user_id}/phase/{phase_index}/progress", userId, phaseIndex);
    }

    /**
     * 一键生成学习资源(还需要添加代码)
     * @param userId
     * @param phaseIndex
     * @param knowledgePoints
     * @return
     */
    @Override
    public Object oneClickGenerate(String userId, Integer phaseIndex, String knowledgePoints) {
        try {
            Object pythonRes = pythonRestClient.postWithPathAndQueryNoBody(
                    "/study_plan/{user_id}/phase/{phase_index}/generate/{resource_type}?knowledge_point={knowledgePoints}&entry={entry}",
                    userId, phaseIndex, "full_knowledge_set", knowledgePoints, "plan");

            if (pythonRes == null) {
                Map<String, Object> map = new HashMap<>();
                map.put("points", new ArrayList<>());
                return map;
            }

            Map<String, Object> resultMap = (Map<String, Object>) pythonRes;
            Map<String, Object> generatedResources = (Map<String, Object>) resultMap.get("generated_resources");
//            log.info("generatedResources keys: {}", generatedResources != null ? generatedResources.keySet() : "null");
//            log.info("generatedResources: {}", generatedResources);

            List<List<Integer>> points = new ArrayList<>();
            Long userIdLong = Long.valueOf(userId);

            if (generatedResources != null) {
                Map<String, Object> docData = (Map<String, Object>) generatedResources.get("doc");
                if (docData != null && !docData.isEmpty()) {
                    Map<String, Object> document = (Map<String, Object>) docData.get("document");
                    if (document != null) {
                        String ossUrl = (String) document.get("oss_url");
                        Word existingWord = wordMapper.getByOssUrl(ossUrl);
                        if (existingWord == null) {
                            Word word = new Word();
                            word.setUserId(userIdLong);
                            word.setText((String) document.get("doc_title"));
                            word.setStatus(2);
                            word.setCreateTime(LocalDateTime.now());
                            word.setOssUrl(ossUrl);
                            word.setResourceId((String) docData.get("_content_id"));
                            word.setLongText((String) document.get("doc_content"));
                            wordMapper.insert(word);
                            points.add(List.of(2, word.getId().intValue()));
                        } else {
                            points.add(List.of(2, existingWord.getId().intValue()));
                        }
                    }
                }

                Map<String, Object> mindmapData = (Map<String, Object>) generatedResources.get("mindmap");
                if (mindmapData != null && !mindmapData.isEmpty()) {
                    Map<String, Object> mindmapContent = (Map<String, Object>) mindmapData.get("mindmap");
                    if (mindmapContent != null) {
                        String mindmapText = (String) mindmapContent.get("name");
                        String resourceId = (String) mindmapData.get("_content_id");
                        MindMap existingMindMap = mindMapMapper.getByResourceId(resourceId);
                        if (existingMindMap == null) {
                            MindMap mindMap = new MindMap();
                            mindMap.setUserId(userIdLong);
                            mindMap.setText(mindmapText);
                            mindMap.setResourceId(resourceId);
                            mindMap.setStatus(2);
                            mindMap.setCreateTime(LocalDateTime.now());
                            mindMap.setValue(JSON.toJSONString(mindmapContent));
                            mindMapMapper.insert(mindMap);
                            points.add(List.of(1, mindMap.getId().intValue()));
                        } else {
                            points.add(List.of(1, existingMindMap.getId().intValue()));
                        }
                    }
                }

                Map<String, Object> practiceData = (Map<String, Object>) generatedResources.get("practice");
                log.info("practiceData: {}", practiceData);
                if (practiceData != null && !practiceData.isEmpty()) {
                    // 处理 practice 中的 problem 对象
                    Map<String, Object> problem = (Map<String, Object>) practiceData.get("problem");
                    if (problem != null && !problem.isEmpty()) {
                        String problemId = (String) problem.get("problem_id");
                        log.info("practice problemId: {}", problemId);
                        Practice existing = practiceMapper.getByProblemId(problemId);
                        if (existing != null) {
                            log.info("practice exists, id: {}", existing.getId());
                            points.add(List.of(4, existing.getId().intValue()));
                        } else {
                            Practice practice = Practice.builder()
                                    .userId(userIdLong)
                                    .text((String) problem.get("title"))
                                    .title((String) problem.get("title"))
                                    .description((String) problem.get("description"))
                                    .difficulty(String.valueOf(problem.get("difficulty")))
                                    .inputFormat((String) problem.get("input_format"))
                                    .outputFormat((String) problem.get("output_format"))
                                    .hints((List<String>) problem.get("hints"))
                                    .knowledgePoints((List<String>) problem.get("knowledge_points"))
                                    .problemId(problemId)
                                    .status(2)
                                    .createTime(LocalDateTime.now())
                                    .build();
                            practiceMapper.insert(practice);
                            log.info("practice inserted, id: {}", practice.getId());
                            points.add(List.of(4, practice.getId().intValue()));
                        }
                    }

                    // 处理 recommendations 列表
                    List<Map<String, Object>> recommendations = (List<Map<String, Object>>) practiceData.get("recommendations");
                    log.info("practice recommendations: {}", recommendations);
                    if (recommendations != null && !recommendations.isEmpty()) {
                        Long firstPracticeId = null;
                        for (Map<String, Object> rec : recommendations) {
                            String problemId = (String) rec.get("problem_id");
                            log.info("practice recommendation problemId: {}", problemId);
                            Practice existing = practiceMapper.getByProblemId(problemId);
                            if (existing != null) {
                                log.info("practice recommendation exists, id: {}", existing.getId());
                                if (firstPracticeId == null) {
                                    firstPracticeId = existing.getId();
                                }
                                continue;
                            }
                            Practice practice = Practice.builder()
                                    .userId(userIdLong)
                                    .text((String) rec.get("title"))
                                    .title((String) rec.get("title"))
                                    .description((String) rec.get("description"))
                                    .difficulty(String.valueOf(rec.get("difficulty")))
                                    .knowledgePoints((List<String>) rec.get("knowledge_points"))
                                    .problemId(problemId)
                                    .status(2)
                                    .createTime(LocalDateTime.now())
                                    .build();
                            practiceMapper.insert(practice);
                            log.info("practice recommendation inserted, id: {}", practice.getId());
                            if (firstPracticeId == null) {
                                firstPracticeId = practice.getId();
                            }
                        }
                        if (firstPracticeId != null) {
                            points.add(List.of(4, firstPracticeId.intValue()));
                        }
                    }
                }

                Map<String, Object> videoData = (Map<String, Object>) generatedResources.get("video");
                log.info("videoData: {}", videoData);
                if (videoData != null && !videoData.isEmpty()) {
                    List<Map<String, Object>> videoList = (List<Map<String, Object>>) videoData.get("videos");
                    log.info("video list: {}", videoList);
                    if (videoList != null && !videoList.isEmpty()) {
                        String batchId = UUID.randomUUID().toString().replace("-", "");
                        Long firstVideoId = null;
                        for (Map<String, Object> videoMap : videoList) {
                            String videoUrl = (String) videoMap.get("url");
                            log.info("video url: {}", videoUrl);
                            Video existingVideo = videoMapper.getByUrl(videoUrl);
                            if (existingVideo != null) {
                                log.info("video exists, id: {}", existingVideo.getId());
                                if (firstVideoId == null) {
                                    firstVideoId = existingVideo.getId();
                                }
                                continue;
                            }
                            Video video = new Video();
                            video.setUserId(userIdLong);
                            video.setText((String) videoMap.get("title"));
                            video.setBatchId(batchId);
                            video.setStatus(2);
                            video.setCreateTime(LocalDateTime.now());
                            video.setTitle((String) videoMap.get("title"));
                            video.setUrl(videoUrl);
                            video.setThumbnail((String) videoMap.get("thumbnail"));
                            video.setDuration((String) videoMap.get("duration"));
                            video.setAuthor((String) videoMap.get("author"));
                            video.setPlayCount((String) videoMap.get("play_count"));
                            video.setDescription((String) videoMap.get("description"));
                            videoMapper.insert(video);
                            log.info("video inserted, id: {}", video.getId());
                            if (firstVideoId == null) {
                                firstVideoId = video.getId();
                            }
                        }
                        if (firstVideoId != null) {
                            points.add(List.of(5, firstVideoId.intValue()));
                        }
                    }
                }

                Map<String, Object> extensionData = (Map<String, Object>) generatedResources.get("extension");
                if (extensionData != null && !extensionData.isEmpty()) {
                    List<Map<String, Object>> recommendations = (List<Map<String, Object>>) extensionData.get("recommendations");
                    if (recommendations != null && !recommendations.isEmpty()) {
                        String firstTitle = (String) recommendations.get(0).get("title");
                        ExtensionReading existingExt = extensionReadingMapper.getByTitle(firstTitle);
                        if (existingExt == null) {
                            for (Map<String, Object> rec : recommendations) {
                                ExtensionReading ext = ExtensionReading.builder()
                                        .userId(userIdLong)
                                        .text((String) rec.get("title"))
                                        .title((String) rec.get("title"))
                                        .background((String) rec.get("description"))
                                        .status(2)
                                        .createTime(LocalDateTime.now())
                                        .build();
                                extensionReadingMapper.insert(ext);
                            }
                            ExtensionReading firstExtension = extensionReadingMapper.getByTitle(firstTitle);
                            if (firstExtension != null) {
                                points.add(List.of(3, firstExtension.getId().intValue()));
                            }
                        } else {
                            points.add(List.of(3, existingExt.getId().intValue()));
                        }
                    }
                }

                // 处理PPT资源
                Map<String, Object> pptData = (Map<String, Object>) generatedResources.get("ppt");
                if (pptData != null && !pptData.isEmpty()) {
                    Map<String, Object> pptContent = (Map<String, Object>) pptData.get("ppt");
                    if (pptContent != null) {
                        String resourceId = (String) pptData.get("_content_id");
                        String topic = (String) pptContent.get("topic");
                        int pages = (Integer) pptContent.get("pages");
                        // oss_url在外层pptData中，且值两端带有反引号，需要去除
                        String ossUrl = (String) pptData.get("oss_url");
                        if (ossUrl != null) {
                            ossUrl = ossUrl.replaceAll("`", "").trim();
                        }
                        
                        Ppt existingPpt = pptMapper.getPptByResourceId(resourceId);
                        if (existingPpt == null) {
                            Ppt ppt = new Ppt();
                            ppt.setUserId(userIdLong);
                            ppt.setPptTitle(topic);
                            ppt.setResourceId(resourceId);
                            ppt.setPageCount(pages);
                            ppt.setOssUrl(ossUrl);
                            ppt.setStatus(2);
                            ppt.setCreatedAt(String.valueOf(LocalDateTime.now()));
                            pptMapper.insert(ppt);
                            final Long pptId = ppt.getId();
                            final String finalOssUrl = ossUrl;
                            points.add(List.of(0, pptId.intValue()));
                            
                            // 异步将PPT第一张幻灯片转换为图片并上传OSS
                            if (finalOssUrl != null && !finalOssUrl.isEmpty()) {
                                AsyncUtil.execute(() -> {
                                    try {
                                        String firstImageOssUrl = convertFirstSlideToImage(finalOssUrl, pptId.toString());
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
                            points.add(List.of(0, existingPpt.getId().intValue()));
                        }
                    }
                }
            }

            Map<String, Object> map = new HashMap<>();
            map.put("points", points);
            return map;
        } catch (Exception e) {
            log.error("OneClickGenerate error", e);
            Map<String, Object> map = new HashMap<>();
            map.put("points", new ArrayList<>());
            return map;
        }
    }

    /**
     * 检查续期计划状态
     * @param userId
     * @return
     */
    @Override
    public Object checkStatus(String userId, String pathId) {
        Map<String, Object> body = new HashMap<>();
        body.put("plan_id", pathId);
        pythonRestClient.postWithPathParam("/study_plan/{user_id}/switch-plan",body, userId);
        return pythonRestClient.getWithPathParam("/study_plan/{user_id}/continuation", userId);
    }

    /**
     * 接收续期建议
     * @param userId
     * @return
     */
    @Override
    public Object receiveContinuation(String userId, String pathId) {
        Map<String, Object> body = new HashMap<>();
        body.put("plan_id", pathId);
        pythonRestClient.postWithPathParam("/study_plan/{user_id}/switch-plan",body, userId);
        Object result = pythonRestClient.postWithPathAndQueryNoBody("/study_plan/{user_id}/receive-continuation", userId);
        pythonRestClient.postWithPathAndQueryNoBody("/study_plan/{user_id}/accept-continuation", userId);
        return result;
    }

    /**
     * 拒绝续期计划
     * @param userId
     * @return
     */
    @Override
    public Object rejectRenewalSuggestion(String userId, String pathId) {
        //切换为活跃计划
        Map<String, Object> body = new HashMap<>();
        body.put("plan_id", pathId);
        pythonRestClient.postWithPathParam("/study_plan/{user_id}/switch-plan",body, userId);
        return pythonRestClient.postWithPathAndQueryNoBody("/study_plan/{user_id}/reject-continuation", userId);
    }

    /**
     * 获取用户考试选择
     * @param userId
     * @param phaseIndex
     * @param
     * @return
     */
    @Override
    public Object getUserExamChoice(String userId, Integer phaseIndex, String pathId) {
        try {
            //切换为活跃计划
            Map<String, Object> body = new HashMap<>();
            body.put("plan_id", pathId);
            pythonRestClient.postWithPathParam("/study_plan/{user_id}/switch-plan",body, userId);
            Map<String, Object> body2 = new HashMap<>();
            body2.put("take_exam", true);
            Object result = pythonRestClient.postWithPathParam("/study_plan/{user_id}/phase/{phase_index}/exam/choice", body2, userId, phaseIndex);
            log.info("获取用户考试选择成功, result: {}", result);

            // 保存编程题到数据库
            if (result != null) {
                Map<String, Object> resultMap = (Map<String, Object>) result;
                Map<String, Object> examData = (Map<String, Object>) resultMap.get("exam_data");
                if (examData != null) {
                    List<Map<String, Object>> programmingQuestions = (List<Map<String, Object>>) examData.get("programming_questions");
                    log.info("programmingQuestions size: {}", programmingQuestions != null ? programmingQuestions.size() : 0);

                    if (programmingQuestions != null && !programmingQuestions.isEmpty()) {
                        Long userIdLong = Long.valueOf(userId);
                        for (Map<String, Object> question : programmingQuestions) {
                            String problemId = (String) question.get("problem_id");
                            log.info("保存编程题, problemId: {}", problemId);

                            Practice existing = practiceMapper.getByProblemId(problemId);
                            if (existing != null) {
                                log.info("编程题已存在, 跳过, problemId: {}", problemId);
                                continue;
                            }

                            Practice practice = Practice.builder()
                                    .userId(userIdLong)
                                    .text((String) question.get("title"))
                                    .title((String) question.get("title"))
                                    .description((String) question.get("description"))
                                    .difficulty((String) question.get("difficulty"))
                                    .inputFormat((String) question.get("input_format"))
                                    .outputFormat((String) question.get("output_format"))
                                    .hints((List<String>) question.get("hints"))
                                    .knowledgePoints((List<String>) question.get("knowledge_points"))
                                    .problemId(problemId)
                                    .status(2)
                                    .createTime(LocalDateTime.now())
                                    .build();
                            practiceMapper.insert(practice);
                            log.info("编程题插入成功, problemId: {}, practiceId: {}", problemId, practice.getId());
                        }
                    }
                }
            }

            return result;
        } catch (Exception e) {
            log.error("获取用户考试选择失败", e);
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("success", false);
            errorResult.put("message", "获取考试选择失败");
            return errorResult;
        }
    }

    /**
     * 获取考试题目
     * @param userId
     * @param phaseIndex
     * @return
     */
    @Override
    public Object getExamQuestions(String userId, Integer phaseIndex) {
        try {
            Object pythonRes = pythonRestClient.getWithPathParam("/study_plan/{user_id}/phase/{phase_index}/exam", userId, phaseIndex);
            log.info("获取考试题目成功, userId: {}, phaseIndex: {}", userId, phaseIndex);

            Map<String, Object> resultMap = (Map<String, Object>) pythonRes;
            Map<String, Object> data = (Map<String, Object>) resultMap.get("data");
            log.info("data: {}", data);

            if (data != null) {
                Map<String, Object> examData = (Map<String, Object>) data.get("exam_data");
                log.info("examData: {}", examData);

                if (examData != null) {
                    List<Map<String, Object>> programmingQuestions = (List<Map<String, Object>>) examData.get("programming_questions");
                    log.info("programmingQuestions: {}, size: {}", programmingQuestions, programmingQuestions != null ? programmingQuestions.size() : 0);

                    if (programmingQuestions != null && !programmingQuestions.isEmpty()) {
                        Long userIdLong = Long.valueOf(userId);
                        for (Map<String, Object> question : programmingQuestions) {
                            String problemId = (String) question.get("problem_id");
                            log.info("处理编程题, problemId: {}", problemId);

                            Practice existing = practiceMapper.getByProblemId(problemId);
                            if (existing != null) {
                                log.info("编程题已存在, 跳过, problemId: {}", problemId);
                                continue;
                            }
                            Practice practice = Practice.builder()
                                    .userId(userIdLong)
                                    .text((String) question.get("title"))
                                    .title((String) question.get("title"))
                                    .description((String) question.get("description"))
                                    .difficulty((String) question.get("difficulty"))
                                    .inputFormat((String) question.get("input_format"))
                                    .outputFormat((String) question.get("output_format"))
                                    .hints((List<String>) question.get("hints"))
                                    .knowledgePoints((List<String>) question.get("knowledge_points"))
                                    .problemId(problemId)
                                    .status(2)
                                    .createTime(LocalDateTime.now())
                                    .build();
                            practiceMapper.insert(practice);
                            log.info("编程题插入成功, problemId: {}, practiceId: {}", problemId, practice.getId());
                        }
                    }
                }
            }

            return pythonRes;
        } catch (Exception e) {
            log.error("获取考试题目失败", e);
            return null;
        }
    }

    /**
     * 提交答案给Python
     * @param
     * @param userId
     * @param
     * @return
     */
    @Override
    public Object getReviewReminder(String userId) {
        log.info("复习提醒, userId: {}", userId);
        return pythonRestClient.getWithPathParam("/study_plan/{user_id}/review-reminder", userId);
    }

    @Override
    public Object getSevenDaysReviewReminder(String userId) {
        log.info("近7天复习提醒, userId: {}", userId);
        return pythonRestClient.getWithPathAndQueryParam("/review/session/recent-completed/{user_id}?days={days}", userId, 7);
    }

    @Override
    public Object getAllCountReviewReminder(String userId) {
        log.info("复习提醒总计, userId: {}", userId);
        return pythonRestClient.getWithPathParam("/knowledge-mastery/all/{user_id}", userId);
    }

    @Override
    public Object getVersionTree(String userId, String planId) {
        log.info("获取学习计划版本树, userId: {}, planId: {}", userId, planId);
        return pythonRestClient.getWithPathAndQueryParam("/study_plan/{user_id}/version-tree?plan_id={planId}", userId, planId);
    }

    @Override
    public Object switchVersionTree(String userId, String planId) {
        log.info("切换版本树当前执行中版本, userId: {}, planId: {}", userId, planId);
        Map<String, Object> body = new HashMap<>();
        body.put("plan_id", planId);
        return pythonRestClient.postWithPathParam("/study_plan/{user_id}/switch-version", body, userId);
    }

    @Override
    public Object regeneratePhase(RegeneratePhaseDTO dto, String userId) {
        log.info("重新生成阶段计划, userId: {}, phaseIndex: {}, planId: {}", userId, dto.getPhase_index(), dto.getPlan_id());
        Map<String, Object> body = new HashMap<>();
        body.put("phase_index", dto.getPhase_index());
        body.put("plan_id", dto.getPlan_id());
        return pythonRestClient.postWithPathParam("/study_plan/{user_id}/regenerate-phase", body, userId);
    }

    @Override
    public Object submitAnswerToPython(AnswerFrontDTO frontDTO, String userId, Integer phaseIndex) throws Exception{
        // 0. 先获取当前阶段的编程题列表，将编程题答案存入practice_answer表
        List<String> codeList = frontDTO.getProgramm();
        if (codeList != null && !codeList.isEmpty()) {
            try {
                // 获取当前阶段的考试题目
                Object examRes = pythonRestClient.getWithPathParam("/study_plan/{user_id}/phase/{phase_index}/exam", userId, phaseIndex);
                if (examRes != null) {
                    Map<String, Object> resultMap = (Map<String, Object>) examRes;
                    Map<String, Object> data = (Map<String, Object>) resultMap.get("data");
                    if (data != null) {
                        Map<String, Object> examData = (Map<String, Object>) data.get("exam_data");
                        if (examData != null) {
                            List<Map<String, Object>> programmingQuestions = (List<Map<String, Object>>) examData.get("programming_questions");
                            log.info("获取编程题列表用于记录答案, size: {}", programmingQuestions != null ? programmingQuestions.size() : 0);

                            if (programmingQuestions != null && !programmingQuestions.isEmpty()) {
                                Long userIdLong = Long.valueOf(userId);
                                // 按顺序匹配编程题和代码
                                for (int i = 0; i < Math.min(codeList.size(), programmingQuestions.size()); i++) {
                                    String code = codeList.get(i);
                                    Map<String, Object> question = programmingQuestions.get(i);
                                    String problemId = (String) question.get("problem_id");

                                    // 查找对应的Practice记录
                                    Practice practice = practiceMapper.getByProblemId(problemId);
                                    if (practice != null) {
                                        // 创建PracticeAnswer记录
                                        PracticeAnswer practiceAnswer = new PracticeAnswer();
                                        practiceAnswer.setPracticeId(practice.getId());
                                        practiceAnswer.setAnswer(code);
                                        practiceAnswer.setStatus(1); // 待评测
                                        practiceAnswer.setCreateTime(LocalDateTime.now());
                                        practiceAnswerMapper.insert(practiceAnswer);
                                        log.info("编程题答案记录成功, practiceId: {}, answerId: {}", practice.getId(), practiceAnswer.getId());
                                    } else {
                                        log.warn("未找到对应的Practice记录, problemId: {}", problemId);
                                    }
                                }
                            }
                        }
                    }
                }
            } catch (Exception e) {
                log.error("记录编程题答案失败", e);
                // 不影响主流程，继续提交答案给Python
            }
        }

        // 1. 数组转Map key=programming_0 / theory_0
        Map<String, String> answersMap = new HashMap<>();
        if (codeList != null) {
            for (int i = 0; i < codeList.size(); i++) {
                answersMap.put("programming_" + i, codeList.get(i));
            }
        }
        List<String> theoryList = frontDTO.getTheory();
        if (theoryList != null) {
            for (int i = 0; i < theoryList.size(); i++) {
                answersMap.put("theory_" + i, theoryList.get(i));
            }
        }

        // 2. 组装顶层 { "answers": {} }
        Map<String, Object> sendBody = new HashMap<>();
        sendBody.put("answers", answersMap);

        // 3. 转下划线JSON字符串
        String snakeJson = SNAKE_CASE_MAPPER.writeValueAsString(sendBody);
        log.info("发送至Python的请求体");

        // 4. 调用工具发送
        String pythonPath = "/study_plan/{user_id}/phase/{phase_index}/exam/submit";
        return pythonRestClient.postWithPathParam(pythonPath, snakeJson, userId, phaseIndex);
    }

    /**
     * 将PPT第一张幻灯片转换为图片并上传OSS
     * @param pptUrl PPT文件的OSS链接
     * @param pptId PPT任务ID
     * @return 图片的OSS链接
     */
    private String convertFirstSlideToImage(String pptUrl, String pptId) throws Exception {
        URL url = new URL(pptUrl);
        try (InputStream is = url.openStream();
             XMLSlideShow ppt = new XMLSlideShow(is)) {

            XSLFSlide firstSlide = ppt.getSlides().get(0);

            Dimension pageSize = ppt.getPageSize();
            int width = pageSize.width;
            int height = pageSize.height;

            BufferedImage image = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
            Graphics2D graphics = image.createGraphics();

            try {
                graphics.setPaint(Color.WHITE);
                graphics.fill(new Rectangle(0, 0, width, height));

                graphics.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
                graphics.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
                graphics.setRenderingHint(RenderingHints.KEY_RENDERING, RenderingHints.VALUE_RENDER_QUALITY);
                graphics.setRenderingHint(RenderingHints.KEY_FRACTIONALMETRICS, RenderingHints.VALUE_FRACTIONALMETRICS_ON);

                firstSlide.draw(graphics);

                ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
                ImageIO.write(image, "png", outputStream);
                byte[] imageBytes = outputStream.toByteArray();

                String fileName = "ppt/image/" + pptId + "_" + UUID.randomUUID().toString() + ".png";
                return aliOssUtil.upload(imageBytes, fileName);
            } finally {
                graphics.dispose();
            }
        }
    }
}
