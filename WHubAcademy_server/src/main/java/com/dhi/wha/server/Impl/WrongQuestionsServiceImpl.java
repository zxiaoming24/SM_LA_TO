package com.dhi.wha.server.Impl;

import com.dhi.wha.entity.Practice;
import com.dhi.wha.mapper.PracticeMapper;
import com.dhi.wha.server.WrongQuestionsService;
import com.dhi.wha.utils.PythonRestClient;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
public class WrongQuestionsServiceImpl implements WrongQuestionsService {

    @Autowired
    private PythonRestClient pythonRestClient;

    @Autowired
    private PracticeMapper practiceMapper;


    /**
     * 获取错题列表
     * @param page
     * @param pageSize
     * @param questionType
     * @param userId
     * @return
     */
    @Override
    public Object getWrongQuestionsList(Integer page, Integer pageSize, Integer questionType, Long userId) {
        //1.判断题目类型，从而传递对应的字符串
        String questionTypeStr = "";
        switch (questionType){
            case 0:
                //获取所有
                questionTypeStr = "";
                return pythonRestClient.getWithPathAndQueryParam("/wrong-answers/{user_id}?page={page}&page_size={pageSize}&question_type={question_type}", userId.toString(), page, pageSize, questionTypeStr);
            case 1:
                //获取编程题
                questionTypeStr = "programming";
                return pythonRestClient.getWithPathAndQueryParam("/wrong-answers/{user_id}?page={page}&page_size={pageSize}&question_type={question_type}", userId.toString(), page, pageSize, questionTypeStr);
            case 2:
                //获取单选题
                questionTypeStr = "single_choice";
                return pythonRestClient.getWithPathAndQueryParam("/wrong-answers/{user_id}?page={page}&page_size={pageSize}&question_type={question_type}", userId.toString(), page, pageSize, questionTypeStr);
            case 3:
                //获取多选题
                questionTypeStr = "multiple_choice";
                return pythonRestClient.getWithPathAndQueryParam("/wrong-answers/{user_id}?page={page}&page_size={pageSize}&question_type={question_type}", userId.toString(), page, pageSize, questionTypeStr);
            case 4:
                //获取判断题
                questionTypeStr = "judge";
                return pythonRestClient.getWithPathAndQueryParam("/wrong-answers/{user_id}?page={page}&page_size={pageSize}&question_type={question_type}", userId.toString(), page, pageSize, questionTypeStr);
            case 5:
                //获取填空题
                questionTypeStr = "fill_blank";
                return pythonRestClient.getWithPathAndQueryParam("/wrong-answers/{user_id}?page={page}&page_size={pageSize}&question_type={question_type}", userId.toString(), page, pageSize, questionTypeStr);
            case 6:
                //获取简答题
                questionTypeStr = "short_answer";
                return pythonRestClient.getWithPathAndQueryParam("/wrong-answers/{user_id}?page={page}&page_size={pageSize}&question_type={question_type}", userId.toString(), page, pageSize, questionTypeStr);
            default:
                return "参数错误";
        }
    }

    /**
     * 获取错题统计
     * @param userId
     * @return
     */
    @Override
    public Object getWrongQuestionsStats(Long userId) {
        return pythonRestClient.getWithPathParam("/wrong-answers/{user_id}/stats", userId.toString());
    }

    /**
     * 获取已掌握的错题列表
     * @param page
     * @param pageSize
     * @param userId
     * @return
     */
    @Override
    public Object getMasteredWrongQuestionsList(Integer page, Integer pageSize, Long userId) {
        return pythonRestClient.getWithPathAndQueryParam("/wrong-answers/{user_id}/mastered?page={page}&page_size={pageSize}", userId.toString(), page, pageSize);
    }

    /**
     * 删除用户指定错题记录
     * @param userId
     * @param recordId
     * @return
     */
    @Override
    public Object deleteByUserIdAndRecordId(Long userId, String recordId) {
        return pythonRestClient.deleteWithPathParam("/wrong-answers/{record_id}/{user_id}", recordId, userId.toString());
    }

    /**
     * 获取错题的推荐材料
     * @param recordId
     * @param userId
     * @return
     */
    @Override
    public Object getMasteredList(String recordId, String userId) {
        try {
            Object pythonRes = pythonRestClient.getWithPathAndQueryParam("/wrong-answers/{record_id}/recommend/{user_id}", recordId, userId.toString());
            log.info("Python返回的推荐材料: {}", pythonRes);

            if (pythonRes == null) {
                return pythonRes;
            }

            Map<String, Object> resultMap = (Map<String, Object>) pythonRes;
            Map<String, Object> materials = (Map<String, Object>) resultMap.get("materials");

            if (materials != null) {
                List<Map<String, Object>> questions = (List<Map<String, Object>>) materials.get("question");
                log.info("questions size: {}", questions != null ? questions.size() : 0);

                if (questions != null && !questions.isEmpty()) {
                    Long userIdLong = userId != null ? Long.valueOf(userId) : 1L;

                    for (Map<String, Object> question : questions) {
                        String subTopic = (String) question.get("sub_topic");
                        String id = (String) question.get("id");
                        String title = (String) question.get("title");

                        if (id != null && id.startsWith("P_")) {
                            String problemId = id;
                            log.info("保存编程题, problemId: {}, title: {}", problemId, title);

                            Practice existing = practiceMapper.getByProblemId(problemId);
                            if (existing != null) {
                                log.info("编程题已存在, 跳过, problemId: {}", problemId);
                                continue;
                            }

                            String metadataTitle = null;
                            Object metadataObj = question.get("metadata");
                            if (metadataObj instanceof Map) {
                                metadataTitle = (String) ((Map<String, Object>) metadataObj).get("title");
                            }

                            String finalTitle = title != null && !title.isEmpty() ? title : 
                                (metadataTitle != null && !metadataTitle.isEmpty() ? metadataTitle : "编程练习");

                            Integer difficultyInt = 0;
                            Object diffObj = question.get("difficulty");
                            if (diffObj instanceof Integer) {
                                difficultyInt = (Integer) diffObj;
                            }
                            String difficulty;
                            switch (difficultyInt) {
                                case 1:
                                    difficulty = "简单";
                                    break;
                                case 2:
                                    difficulty = "中等";
                                    break;
                                default:
                                    difficulty = "困难";
                            }

                            List<String> hintsList = new ArrayList<>();
                            Object hintsObj = question.get("hints");
                            if (hintsObj instanceof List<?>) {
                                for (Object item : (List<?>) hintsObj) {
                                    if (item instanceof String) {
                                        hintsList.add((String) item);
                                    }
                                }
                            }

                            List<String> kpList = new ArrayList<>();
                            String kpStr = (String) question.get("knowledge_points");
                            if (kpStr != null && !kpStr.isBlank()) {
                                String[] kpArr = kpStr.split(",");
                                for (String kp : kpArr) {
                                    kpList.add(kp.trim());
                                }
                            }

                            Practice practice = Practice.builder()
                                    .userId(userIdLong)
                                    .text(finalTitle)
                                    .title(finalTitle)
                                    .description((String) question.get("content"))
                                    .difficulty(difficulty)
                                    .inputFormat("无")
                                    .outputFormat("无")
                                    .hints(hintsList)
                                    .knowledgePoints(kpList)
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

            return resultMap;
        } catch (Exception e) {
            log.error("获取推荐材料失败", e);
            return pythonRestClient.getWithPathAndQueryParam("/wrong-answers/{record_id}/recommend/{user_id}", recordId, userId.toString());
        }
    }

    /**
     * 获取易错题列表
     * @param userId 用户id
     * @return 易错题列表
     */
    @Override
    public Object getFrequentlyWrongList(Long userId,Integer page,Integer pageSize) {
        return pythonRestClient.getWithPathAndQueryParam("/wrong-answers/{user_id}/frequently-wrong?page={page}&page_size={pageSize}", userId.toString(),page,pageSize);
    }

    /**
     * 获取易错题统计
     * @param userId 用户id
     * @return 易错题统计
     */
    @Override
    public Object getFrequentlyWrongStats(Long userId) {
        return pythonRestClient.getWithPathParam("/wrong-answers/{user_id}/frequently-wrong/stats", userId.toString());
    }

    /**
     * AI生成推荐材料
     * @param requestMap 包含 user_id, record_id, knowledge_points, resource_types, difficulty
     * @return 推荐材料结果
     */
    @Override
    public Object llmGenerateRecommendedResources(Map<String, Object> requestMap) {
        try {
            Object pythonRes = pythonRestClient.post("/wrong-answers/llm-generate", requestMap);
            log.info("Python返回的推荐材料: {}", pythonRes);

            if (pythonRes == null) {
                Map<String, Object> result = new HashMap<>();
                result.put("success", false);
                result.put("materials", new HashMap<>());
                return result;
            }

            Map<String, Object> resultMap = (Map<String, Object>) pythonRes;
            Map<String, Object> materials = (Map<String, Object>) resultMap.get("materials");

            if (materials != null) {
                List<Map<String, Object>> questions = (List<Map<String, Object>>) materials.get("question");
                log.info("questions size: {}", questions != null ? questions.size() : 0);

                if (questions != null && !questions.isEmpty()) {
                    String userId = (String) requestMap.get("user_id");
                    Long userIdLong = userId != null ? Long.valueOf(userId) : 1L;

                    for (Map<String, Object> question : questions) {
                        String subTopic = (String) question.get("sub_topic");
                        String id = (String) question.get("id");
                        String title = (String) question.get("title");

                        if ("programming".equals(subTopic) || (id != null && !id.isEmpty() && !id.startsWith("P_") == false)) {
                            String problemId = id;
                            if (problemId == null || problemId.isEmpty()) {
                                problemId = (String) question.get("metadata") != null ? 
                                    (String) ((Map<String, Object>) question.get("metadata")).get("title") : 
                                    title;
                            }
                            log.info("保存编程题, problemId: {}, title: {}", problemId, title);

                            Practice existing = practiceMapper.getByProblemId(problemId);
                            if (existing != null) {
                                log.info("编程题已存在, 跳过, problemId: {}", problemId);
                                continue;
                            }

                            Practice practice = Practice.builder()
                                    .userId(userIdLong)
                                    .text(title != null && !title.isEmpty() ? title : "编程练习")
                                    .title(title != null && !title.isEmpty() ? title : "编程练习")
                                    .description((String) question.get("content"))
                                    .difficulty(String.valueOf(question.get("difficulty")))
                                    .hints((List<String>) question.get("hints"))
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

            return resultMap;
        } catch (Exception e) {
            log.error("AI生成推荐材料失败", e);
            Map<String, Object> result = new HashMap<>();
            result.put("success", false);
            result.put("materials", new HashMap<>());
            return result;
        }
    }
}
