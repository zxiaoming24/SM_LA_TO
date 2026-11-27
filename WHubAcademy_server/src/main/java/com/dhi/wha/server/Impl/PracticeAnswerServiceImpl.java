package com.dhi.wha.server.Impl;

import com.alibaba.fastjson.JSON;
import com.alibaba.fastjson.JSONArray;
import com.alibaba.fastjson.JSONObject;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.dhi.wha.constant.MindMapConstant;
import com.dhi.wha.dto.CompareDTO;
import com.dhi.wha.dto.PracticeAnswerDTO;
import com.dhi.wha.entity.*;
import com.dhi.wha.mapper.PracticeAnswerMapper;
import com.dhi.wha.mapper.PracticeMapper;
import com.dhi.wha.server.ExampleService;
import com.dhi.wha.server.PracticeAnswerService;
import com.dhi.wha.utils.AsyncUtil;
import com.dhi.wha.utils.PythonRestClient;
import com.dhi.wha.vo.PracticeAnswerListVO;
import com.dhi.wha.vo.PracticeAnswerVO;
import com.dhi.wha.vo.PracticeVO;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.TransactionStatus;

import java.time.LocalDateTime;
import java.util.*;

import static java.util.List.of;

@Service
public class PracticeAnswerServiceImpl extends ServiceImpl<PracticeAnswerMapper, PracticeAnswer>
        implements PracticeAnswerService {

    @Autowired
    private PracticeMapper practiceMapper;

    @Autowired
    private PracticeAnswerMapper practiceAnswerMapper;

    @Autowired
    private PythonRestClient pythonRestClient;

    @Autowired
    private ExampleService exampleService;


    /**
     * 获取编程练习题的答案(代码评测加错题重练)
     * @param request
     * @return
     */
    @Override
    public Map<String, Object> getPracticeAnswer(PracticeAnswerDTO request) {
        //1.根据传入的练习题id获得对应的python端的练习题id
        String problemId = practiceMapper.getProblemId(request.getPracticeId());
        //获取对应的练习题数据
        Practice problemData = practiceMapper.getById(request.getPracticeId());

        //2.将一部分数据封装成practiceAnswer对象
        PracticeAnswer practiceAnswer = new PracticeAnswer();
        practiceAnswer.setPracticeId(request.getPracticeId());
        practiceAnswer.setUserId(request.getUserId());  //新增之后就会有了
        practiceAnswer.setAnswer(request.getAnswer());
        practiceAnswer.setStatus(1);
        practiceAnswer.setCreateTime(LocalDateTime.now());
        practiceAnswer.setLanguage(request.getLanguage());  //新增这行就会有语言了
        practiceAnswerMapper.insert(practiceAnswer);

        //3.封装前端返回的数据
        Map<String, Object> result = new HashMap<>();
        result.put("id", practiceAnswer.getId());
        result.put("status", 1);
        result.put("msg", "代码正在测评中...");

        if(request.getRecordId() == null) {
            //4.异步执行调用Python生成逻辑(为空就是代码测评)
            AsyncUtil.execute(() -> {
                try {
                    // 调用Python
                    Map<String, Object> pythonParam = new HashMap<>();
                    pythonParam.put("user_id", request.getUserId().toString());
                    pythonParam.put("code", request.getAnswer());
                    pythonParam.put("problem_id", problemId);
                    pythonParam.put("language", request.getLanguage());
                    if(problemData.getProblemId() != null){
                        pythonParam.put("session_id", problemData.getSessionId());
                    }



                    Object pythonRes = pythonRestClient.post("/practice/submit", pythonParam);

                    Map<String, Object> pythonMap = (Map<String, Object>) pythonRes;
                    Map<String, Object> answer = (Map<String, Object>) pythonMap.get("judge_result");


                    //提取字段
                    String verdict = (String) answer.get("verdict");

                    // 数字字段安全转换
                    Integer passedTests = convertToInt(answer.get("passed_tests"));
                    Integer totalTests = convertToInt(answer.get("total_tests"));
                    Integer score = convertToInt(answer.get("score"));
                    Integer submissionId = convertToInt(answer.get("submission_id"));

                    List<String> suggestion = (List<String>) answer.get("suggestions");
                    String encouragement = (String) answer.get("encouragement");


                    //5.更新数据库
                    practiceAnswer.setVerdict(verdict);
                    practiceAnswer.setScore(score);
                    practiceAnswer.setPassedTests(passedTests);
                    practiceAnswer.setTotalTests(totalTests);
                    practiceAnswer.setSuggestion(suggestion);
                    practiceAnswer.setEncouragement(encouragement);
                    practiceAnswer.setSubmissionId(submissionId);
                    practiceAnswer.setStatus(2);
                    if (score == 0) {
                        practiceAnswer.setVerdict("Compilation Error");
                    }
                    practiceAnswerMapper.updateById(practiceAnswer);

                } catch (Exception e) {
                    e.printStackTrace();
                    // 异常 → 只更新状态为失败
                    practiceAnswer.setStatus(3);
                    practiceAnswerMapper.updateById(practiceAnswer);
                }
            });
        }else {
            //4.异步执行调用Python生成逻辑(不为空就是错题重练)
            AsyncUtil.execute(() -> {
                try {
                    //封装参数problem_data
                    Map<String, Object> problemDataMap = new HashMap<>();
                    problemDataMap.put("problem_id", problemData.getProblemId());
                    problemDataMap.put("description", problemData.getDescription());
                    problemDataMap.put("knowledge_points", problemData.getKnowledgePoints());

                    Map<String, Object> pythonParam = new HashMap<>();
                    pythonParam.put("user_id", request.getUserId().toString());
                    pythonParam.put("user_code", request.getAnswer());
                    pythonParam.put("problem_data", problemDataMap);
                    pythonParam.put("language", request.getLanguage());
                    pythonParam.put("record_id", request.getRecordId());
                    if(problemData.getSessionId() != null){
                        pythonParam.put("session_id", problemData.getSessionId());
                    }
                    Object pythonRes = pythonRestClient.post("/practice/rejudge", pythonParam);

                    // 顶层判空
                    if (!(pythonRes instanceof Map)) {
                        practiceAnswer.setStatus(3);
                        practiceAnswerMapper.updateById(practiceAnswer);
                        return;
                    }

                    Map<String, Object> pythonMap = (Map<String, Object>) pythonRes;
                    Map<String, Object> answer = (Map<String, Object>) pythonMap.get("judge_result");

                    // ========== 独立处理 material_recommendations ==========
                    Question question1 = new Question();
                    int count = 0;
                    int newItem = 0;
                    int oldItem = 0;
                    List<String> oldNameList = new ArrayList<>();

                    try {
                        // 1. 取 material_recommendations
                        Object materialRecObj = pythonMap.get("material_recommendations");
                        if (materialRecObj instanceof Map) {
                            Map<String, Object> materialRecMap = (Map<String, Object>) materialRecObj;

                            // 2. 取 materials
                            Object materialsObj = materialRecMap.get("materials");
                            if (materialsObj instanceof Map) {
                                Map<String, Object> materialsMap = (Map<String, Object>) materialsObj;

                                // 3. 取 question 列表
                                Object questionListObj = materialsMap.get("question");
                                if (questionListObj instanceof List) {
                                    List<Object> questionList = (List<Object>) questionListObj;

                                    for (Object obj : questionList) {
                                        if (!(obj instanceof Map)) {
                                            continue;
                                        }
                                        Map<String, Object> questionItem = (Map<String, Object>) obj;

                                        // 获取 resource_id
                                        String resourceId = (String) questionItem.get("id");
                                        if (resourceId == null || resourceId.trim().isEmpty()) {
                                            continue;
                                        }

                                        // 判断是否为编程题（id以P_开头）
                                        boolean isProgrammingQuestion = resourceId.startsWith("P_");

                                        // 只有编程题才存入数据库
                                        if (isProgrammingQuestion) {
                                            Practice practice = practiceMapper.getByProblemId(resourceId);
                                            if (practice == null) {
                                                // 新增练习题
                                                practice = new Practice();
                                                practice.setProblemId(resourceId);
                                                practice.setUserId(request.getUserId());
                                                practice.setCreateTime(LocalDateTime.now());
                                                practice.setStatus(2);
                                                practice.setText("【错题重练】" + problemData.getText());

                                                // 处理难度 difficulty
                                                Integer difficulty = 0;
                                                Object diffObj = questionItem.get("difficulty");
                                                if (diffObj instanceof Integer) {
                                                    difficulty = (Integer) diffObj;
                                                }
                                                switch (difficulty) {
                                                    case 1:
                                                        practice.setDifficulty("简单");
                                                        break;
                                                    case 2:
                                                        practice.setDifficulty("中等");
                                                        break;
                                                    default:
                                                        practice.setDifficulty("困难");
                                                }

                                                practice.setInputFormat("无");
                                                practice.setOutputFormat("无");
                                                practice.setDescription((String) questionItem.get("content"));
                                                // ========== 处理 hints 数组 ==========
                                                List<String> hintsList = new ArrayList<>();
                                                Object hintsObj = questionItem.get("hints");
                                                if (hintsObj instanceof List<?>) {
                                                    List<?> tempList = (List<?>) hintsObj;
                                                    for (Object item : tempList) {
                                                        if (item instanceof String) {
                                                            hintsList.add((String) item);
                                                        }
                                                    }
                                                }
                                                practice.setHints(hintsList);

                                                // ========== 处理 knowledge_points（后端返回 逗号分隔字符串） ==========
                                                List<String> kpList = new ArrayList<>();
                                                String kpStr = (String) questionItem.get("knowledge_points");
                                                if (kpStr != null && !kpStr.isBlank()) {
                                                    // 按逗号分割为集合
                                                    String[] kpArr = kpStr.split(",");
                                                    kpList.addAll(Arrays.asList(kpArr));
                                                }
                                                practice.setKnowledgePoints(kpList);

                                                // ========== 处理 metadata（原生是 JSONObject，转为字符串解析） ==========
                                                Object metadataObj = questionItem.get("metadata");
                                                String metadata = "";
                                                if (metadataObj instanceof String) {
                                                    metadata = (String) metadataObj;
                                                } else if (metadataObj instanceof java.util.LinkedHashMap) {
                                                    try {
                                                        metadata = new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(metadataObj);
                                                    } catch (Exception e) {
                                                        metadata = "";
                                                    }
                                                }

                                                JSONObject jsonObj = null;
                                                try {
                                                    jsonObj = JSON.parseObject(metadata);
                                                } catch (Exception e) {
                                                    jsonObj = null;
                                                }

                                                if (jsonObj != null) {
                                                    String title = jsonObj.getString("title");
                                                    JSONArray examplesJson = jsonObj.getJSONArray("examples");

                                                    practice.setTitle(title);
                                                    practiceMapper.insert(practice);

                                                    List<Example> exampleList = new ArrayList<>();
                                                    // 遍历示例用例
                                                    if (examplesJson != null && examplesJson.size() > 0) {
                                                        for (int i = 0; i < examplesJson.size(); i++) {
                                                            JSONObject exJson = examplesJson.getJSONObject(i);
                                                            if (exJson == null) {
                                                                continue;
                                                            }
                                                            Example example = Example.builder()
                                                                    .practiceId(practice.getId())
                                                                    .input(exJson.getString("input"))
                                                                    .output(exJson.getString("output"))
                                                                    .explanation(exJson.getString("explanation"))
                                                                    .build();
                                                            exampleList.add(example);
                                                        }
                                                    }
                                                    // 批量保存用例
                                                    if (!exampleList.isEmpty()) {
                                                        exampleService.saveBatch(exampleList);
                                                    }
                                                    newItem++;
                                                } else {
                                                    // metadata解析失败，使用title字段
                                                    String title = (String) questionItem.get("title");
                                                    if (title != null && !title.isEmpty()) {
                                                        practice.setTitle(title);
                                                    } else {
                                                        practice.setTitle("编程练习");
                                                    }
                                                    practiceMapper.insert(practice);
                                                    newItem++;
                                                }
                                                count++;
                                            } else {
                                                // 题目已存在
                                                oldNameList.add(practice.getText());
                                                oldItem++;
                                                count++;
                                            }
                                        } else {
                                            // 不是编程题，只计数不存储
                                            String questionTitle = (String) questionItem.get("title");
                                            if (questionTitle != null && !questionTitle.isEmpty()) {
                                                oldNameList.add(questionTitle);
                                            } else {
                                                oldNameList.add("有非编程题推荐,请前往错题本");
                                            }
                                            oldItem++;
                                            count++;
                                        }
                                    }
                                }
                            }
                        }
                    } catch (Exception e) {
                        e.printStackTrace();
                        // material_recommendations 处理失败不影响评分结果
                    }

                    // ========== 评分结果赋值（不受 material_recommendations 影响） ==========
                    String verdict = answer != null ? (String) answer.get("verdict") : null;
                    Integer passedTests = answer != null ? (Integer) answer.get("passed_tests") : null;
                    Integer totalTests = answer != null ? (Integer) answer.get("total_tests") : null;
                    Integer score = answer != null ? (Integer) answer.get("score") : null;
                    Integer submissionId = answer != null ? (Integer) answer.get("submission_id") : null;
                    List<String> suggestion = answer != null ? (List<String>) answer.get("suggestions") : null;
                    String encouragement = answer != null ? (String) answer.get("encouragement") : null;

                    QuestionName name = new QuestionName();
                    name.setNewName("【错题重练】"+problemData.getText());
                    name.setOldName(oldNameList);
                    question1.setName(name);
                    question1.setCount(count);
                    question1.setNewItem(newItem);
                    question1.setOldItem(oldItem);

                    if(score > 60){
                        question1 = null;
                    }
                    practiceAnswer.setQuestion(question1);
                    practiceAnswer.setVerdict(verdict);
                    practiceAnswer.setScore(score);
                    practiceAnswer.setPassedTests(passedTests);
                    practiceAnswer.setTotalTests(totalTests);
                    practiceAnswer.setSubmissionId(submissionId);
                    practiceAnswer.setSuggestion(suggestion);
                    practiceAnswer.setEncouragement(encouragement);
                    practiceAnswer.setStatus(2);
                    if (score != null && score == 0) {
                        practiceAnswer.setVerdict("Compilation Error");
                    }
                    practiceAnswerMapper.updateById(practiceAnswer);

                } catch (Exception e) {
                    e.printStackTrace();
                    // 异常 → 只更新状态为失败
                    practiceAnswer.setStatus(3);
                    practiceAnswerMapper.updateById(practiceAnswer);
                }
            });
        }
        return result;
    }

    @Override
    public PracticeAnswerVO getPracticeAnswerById(Long id) {
        return practiceAnswerMapper.getPracticeAnswerById(id);
    }

    @Override
    public List<PracticeAnswerListVO> getPracticeAnswerList(Long practiceId, Long userId) {
        //1.根据practiceId查询对应的practiceAnswerList
        return practiceAnswerMapper.getPracticeAnswerList(practiceId, userId);
    }

    @Override
    public void deletePracticeAnswerById(Long id) {
        practiceAnswerMapper.deleteById(id);
    }

    /**
     * 比较分析两个人的编程题
     * @param compareDTO 比较请求参数
     * @return 比较结果数据
     */
    @Override
    public List<Object> comparePracticeAnswers(CompareDTO compareDTO) {
        // 1. 根据practiceId查询对应的problem_id
        String problemId = practiceMapper.getProblemId(compareDTO.getPracticeId());
        if (problemId == null || problemId.isEmpty()) {
            throw new RuntimeException("未找到对应的编程题");
        }

        // 2. 根据submissionAId获取A用户的提交代码信息
        Object submissionA = pythonRestClient.getWithPathParam(
                "/leaderboard/submission/{submission_id}/code",
                compareDTO.getSubmissionAId()
        );

        // 3. 根据submissionBId获取B用户的提交代码信息
        Object submissionB = pythonRestClient.getWithPathParam(
                "/leaderboard/submission/{submission_id}/code",
                compareDTO.getSubmissionBId()
        );

        // 4. 请求Python端/compare进行AI比较分析
        Map<String, Object> compareParams = new HashMap<>();
        compareParams.put("problem_id", problemId);
        compareParams.put("submission_a_id", compareDTO.getSubmissionAId());
        compareParams.put("submission_b_id", compareDTO.getSubmissionBId());
        Object compareResult = pythonRestClient.post("/compare", compareParams);

        // 5. 将所有数据封装返回
        List<Object> result = new ArrayList<>();
        result.add(submissionA);
        result.add(submissionB);
        result.add(compareResult);

        return result;
    }


    /**
     * 兼容String/Integer对象转Integer，空值返回null，非法数字返回null
     */
    private Integer convertToInt(Object obj) {
        if (obj == null) {
            return null;
        }
        // 本身就是Integer直接返回
        if (obj instanceof Integer) {
            return (Integer) obj;
        }
        try {
            // 字符串转数字
            String str = obj.toString().trim();
            if (str.isEmpty()) {
                return null;
            }
            return Integer.parseInt(str);
        } catch (NumberFormatException e) {
            // 字符串不是合法数字，返回null，可按需改成默认值0
            return null;
        }
    }
}
