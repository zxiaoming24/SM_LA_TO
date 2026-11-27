package com.dhi.wha.server.Impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.dhi.wha.dto.ChatDTO;
import com.dhi.wha.dto.PaperDTO;
import com.dhi.wha.dto.QuestionSubmitDTO;
import com.dhi.wha.entity.*;
import com.dhi.wha.mapper.*;
import com.dhi.wha.result.Result;
import com.dhi.wha.server.*;
import com.dhi.wha.utils.AsyncUtil;
import com.dhi.wha.utils.PythonRestClient;
import com.dhi.wha.utils.PythonSseClient;
import com.dhi.wha.vo.ChatResourceVO;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import javax.annotation.Resource;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static java.util.List.of;

@Slf4j
@Service
public class PaperServiceImpl extends ServiceImpl<PaperMapper, PaperPO> implements PaperService {

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
    private PythonRestClient pythonRestClient;

    @Resource
    private PythonSseClient pythonSseClient;

    @Resource
    private SseConnectionService sseConnectionService;

    @Resource
    private ObjectMapper objectMapper;

    @Autowired
    private ShortAnswerService shortAnswerService;



    /**
     * 生成试卷
     * @param paperDTO
     * @return
     */
    @Override
    public Map<String, Object> generatePaper(PaperDTO paperDTO) {
        String userIdStr = paperDTO.getUserId().toString();
        boolean hasSseConnection = sseConnectionService.isConnected(userIdStr);

        // 1.先保存试卷主记录：状态=生成中1
        PaperPO paper = new PaperPO();
        paper.setUserId(paperDTO.getUserId().intValue());
        paper.setPaperName(paperDTO.getText());
        paper.setCreateTime(LocalDateTime.now());
        paper.setStatus(1);
        paperMapper.insert(paper);

        // 2.前端返回
        Map<String, Object> result = new HashMap<>();
        result.put("id", paper.getId());
        result.put("status", 1);
        result.put("msg", "试卷正在后台生成...");

        //3.异步：单独新开事务批量存所有题目，全成功改status=2，任一异常全回滚题目+改paper.status=3
        AsyncUtil.execute(() -> {
            // 异步方法开启独立事务
            saveQuestionWithTx(paper.getId(), paperDTO, userIdStr, hasSseConnection);
        });

        return result;
    }


    /**
     * 获取指定试卷
     * @param id 可以是Java端数字ID或Python端resourceId
     * @return
     */
    @Override
    public Map<String, Object> getPaperInfoById(String id) {
        Map<String, Object> dataMap = new HashMap<>();
        PaperPO paper = null;

        // 判断是否为数字
        if (isNumber(id)) {
            // 是数字类型，根据Java端ID查询
            Long num = Long.parseLong(id);
            paper = paperMapper.selectById(num);
        } else {
            // 不是数字，就是Python端的resourceId
            paper = paperMapper.getByResourceId(id);
        }

        if (paper == null) {
            throw new RuntimeException("试卷不存在");
        }

        Long paperId = Long.valueOf(paper.getId());

        // 试卷基础信息放入data
        dataMap.put("paperInfo", paper);

        // 各类题目查询
        LambdaQueryWrapper<SingleChoicePO> singleWrap = Wrappers.lambdaQuery();
        singleWrap.eq(SingleChoicePO::getPaperId, paperId);
        List<SingleChoicePO> singleList = singleChoiceService.list(singleWrap);

        LambdaQueryWrapper<MultipleChoicePO> multiWrap = Wrappers.lambdaQuery();
        multiWrap.eq(MultipleChoicePO::getPaperId, paperId);
        List<MultipleChoicePO> multiList = multipleChoiceService.list(multiWrap);

        LambdaQueryWrapper<JudgePO> judgeWrap = Wrappers.lambdaQuery();
        judgeWrap.eq(JudgePO::getPaperId, paperId);
        List<JudgePO> judgeList = judgeService.list(judgeWrap);

        LambdaQueryWrapper<FillBlankPO> blankWrap = Wrappers.lambdaQuery();
        blankWrap.eq(FillBlankPO::getPaperId, paperId);
        List<FillBlankPO> blankList = fillBlankService.list(blankWrap);

        LambdaQueryWrapper<ShortAnswerPO> shortWrap = Wrappers.lambdaQuery();
        shortWrap.eq(ShortAnswerPO::getPaperId, paperId);
        List<ShortAnswerPO> shortList = shortAnswerService.list(shortWrap);

        dataMap.put("single_choice", singleList);
        dataMap.put("multiple_choice", multiList);
        dataMap.put("judge", judgeList);
        dataMap.put("fill_blank", blankList);
        dataMap.put("short_answer", shortList);

        return dataMap;
    }

    /**
     * 删除指定试卷
     * @param id
     */
    @Override
    public void deletePaper(Integer id) {
        //1.删除五类题目
        LambdaQueryWrapper<SingleChoicePO> singleWrapper = new LambdaQueryWrapper<>();
        singleWrapper.eq(SingleChoicePO::getPaperId, id);
        singleChoiceService.remove(singleWrapper);

        LambdaQueryWrapper<MultipleChoicePO> multiWrapper = new LambdaQueryWrapper<>();
        multiWrapper.eq(MultipleChoicePO::getPaperId, id);
        multipleChoiceService.remove(multiWrapper);

        LambdaQueryWrapper<JudgePO> judgeWrapper = new LambdaQueryWrapper<>();
        judgeWrapper.eq(JudgePO::getPaperId, id);
        judgeService.remove(judgeWrapper);

        LambdaQueryWrapper<FillBlankPO> blankWrapper = new LambdaQueryWrapper<>();
        blankWrapper.eq(FillBlankPO::getPaperId, id);
        fillBlankService.remove(blankWrapper);

        LambdaQueryWrapper<ShortAnswerPO> shortWrapper = new LambdaQueryWrapper<>();
        shortWrapper.eq(ShortAnswerPO::getPaperId, id);
        shortAnswerService.remove(shortWrapper);

        //2.删除试卷主表
        paperMapper.deleteById(id);
    }

    @Override
    public List<PaperPO> getPaperById(Long userId) {
        return paperMapper.getPaperById(userId);
    }

    @Override
    public Long saveTheoryId(ChatDTO chatDTO) {
        String userIdStr = chatDTO.getUserId().toString();
        boolean hasSseConnection = sseConnectionService.isConnected(userIdStr);

        // 1.先保存试卷主记录：状态=生成中1
        PaperPO paper = new PaperPO();
        paper.setUserId(chatDTO.getUserId().intValue());
        paper.setSessionId(chatDTO.getSessionId());
        paper.setPaperName(chatDTO.getText());
        paper.setCreateTime(LocalDateTime.now());
        paper.setStatus(1);
        paperMapper.insert(paper);


        //3.异步：单独新开事务批量存所有题目，全成功改status=2，任一异常全回滚题目+改paper.status=3
        AsyncUtil.execute(() -> {
            // 异步方法开启独立事务
            saveQuestionWithTx(paper.getId(), convertChatToPaperDTO(chatDTO), userIdStr, hasSseConnection);
        });

        return paper.getId().longValue();
    }

    @Override
    public ChatResourceVO getPaperInfoByUserIdAndTaskId(Integer taskId) {
        return paperMapper.getPaperInfoByUserIdAndTaskId(taskId);
    }

    /**
     * 提交试卷
     * @param questionSubmitDTO
     * @return
     */
    @Override
    public Object submitPaper(QuestionSubmitDTO questionSubmitDTO) {
        Map<String, Object> pythonParam = new HashMap<>();
        Map<String, Object> questionParam = new HashMap<>();
        //题目参数
        questionParam.put("question", questionSubmitDTO.getQuestion().getQuestion());
        questionParam.put("options", questionSubmitDTO.getQuestion().getOptions());
        questionParam.put("answer", questionSubmitDTO.getQuestion().getAnswer());
        //用户参数
        pythonParam.put("user_id", questionSubmitDTO.getUserId());
        pythonParam.put("user_answer", questionSubmitDTO.getUserAnswer());
        pythonParam.put("question_type", questionSubmitDTO.getQuestionType());
        pythonParam.put("knowledge_points", questionSubmitDTO.getKnowledgePoints());
        pythonParam.put("question", questionParam);
        if(!"none".equals(questionSubmitDTO.getSessionId())) {
            pythonParam.put("session_id", questionSubmitDTO.getSessionId());
        }else {
            pythonParam.put("session_id", null);
        }
        return pythonRestClient.post("/theory/judge", pythonParam);
    }

    /**
     * 私有转换工具：把ChatDTO转为现有方法需要的PaperDTO
     * 适配原有 saveQuestionWithTx 入参
     */
    private PaperDTO convertChatToPaperDTO(ChatDTO chatDTO) {
        PaperDTO paperDTO = new PaperDTO();
        paperDTO.setUserId(Long.valueOf(chatDTO.getUserId()));
        paperDTO.setText(chatDTO.getText());
        // 按需补充你PaperDTO其他字段
        return paperDTO;
    }

    /**
     * 异步独立事务：所有题目要么全入库、要么全部回滚，同时修改试卷状态
     */
    @Transactional(rollbackFor = Exception.class)
    public void saveQuestionWithTx(Integer paperId, PaperDTO paperDTO, String userIdStr, boolean hasSseConnection) {
        try {
            // 调用Python SSE接口
            Map<String, Object> pythonParam = new HashMap<>();
            pythonParam.put("user_id", paperDTO.getUserId().toString());
            pythonParam.put("user_input", "帮我生成" + paperDTO.getText() + "的理论题");

            // 用于存储解析结果
            final JsonNode[] resultHolder = new JsonNode[1];

            // 消费SSE流
            pythonSseClient.consumePostSse("/chat", pythonParam, jsonData -> {
                // 如果有SSE连接，转发给前端
                if (hasSseConnection) {
                    sseConnectionService.sendMessage(userIdStr, "paper_stream", jsonData);
                }

                // 监听 task_result 事件
                try {
                    JsonNode root = objectMapper.readTree(jsonData);
                    String eventType = root.path("type").asText("");
                    if ("task_result".equals(eventType)) {
                        JsonNode resultNode = root.path("result");
                        if (!resultNode.isMissingNode()) {
                            resultHolder[0] = resultNode;
                        }
                    }
                } catch (Exception e) {
                    log.error("处理SSE事件失败", e);
                }
            });

            // 检查是否获取到结果
            JsonNode resultNode = resultHolder[0];
            if (resultNode == null) {
                PaperPO updatePaper = new PaperPO();
                updatePaper.setId(paperId);
                updatePaper.setStatus(3);
                paperMapper.updateById(updatePaper);
                return;
            }

            JsonNode questionNode;
            String resourceId;
            String summary = null;

            JsonNode resourcesNode = resultNode.path("resources");
            if (!resourcesNode.isMissingNode() && resourcesNode.isObject()) {
                JsonNode generateQuestionsNode = resourcesNode.path("generate_questions");
                if (!generateQuestionsNode.isMissingNode()) {
                    questionNode = generateQuestionsNode.path("questions");
                    resourceId = questionNode.path("resource_id").asText(null);
                    summary = generateQuestionsNode.path("summary").asText(null);
                } else {
                    questionNode = resultNode.path("question");
                    resourceId = resultNode.path("resource_id").asText(null);
                }
            } else {
                questionNode = resultNode.path("question");
                resourceId = resultNode.path("resource_id").asText(null);
            }

            if (questionNode.isMissingNode() || questionNode.isEmpty()) {
                JsonNode warningNode = resultNode.path("suggestion_warning");
                if (!warningNode.isMissingNode() && !warningNode.isNull()) {
                    PaperPO updatePaper = new PaperPO();
                    updatePaper.setId(paperId);
                    updatePaper.setSuggestionWarning(warningNode.asText());
                    updatePaper.setStatus(1);
                    paperMapper.updateById(updatePaper);
                } else {
                    PaperPO updatePaper = new PaperPO();
                    updatePaper.setId(paperId);
                    updatePaper.setStatus(3);
                    paperMapper.updateById(updatePaper);
                }
                return;
            }

            // 单选
            JsonNode singleNode = questionNode.path("single_choice");
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

            //多选
            JsonNode multiNode = questionNode.path("multiple_choice");
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

            //判断
            JsonNode judgeNode = questionNode.path("judge");
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

            //填空
            JsonNode blankNode = questionNode.path("fill_blank");
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

            //简答
            JsonNode shortNode = questionNode.path("short_answer");
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

            //全部题目入库成功，试卷改为成功2
            PaperPO updatePaper = new PaperPO();
            updatePaper.setId(paperId);
            updatePaper.setResourceId(resourceId);
            if (summary != null && !summary.isEmpty()) {
                updatePaper.setPaperName(summary);
            }
            updatePaper.setStatus(2);
            paperMapper.updateById(updatePaper);

        } catch (Exception e) {
            log.error("试卷生成异常", e);
            //当前@Transactional异常触发：所有题目自动回滚；仅修改试卷状态为失败3
            PaperPO updatePaper = new PaperPO();
            updatePaper.setId(paperId);
            updatePaper.setStatus(3);
            paperMapper.updateById(updatePaper);
            throw new RuntimeException("题目生成异常回滚", e);
        }
    }

    //工具方法: 判断是否为数字
    private static boolean isNumber(String str) {
        if (str == null || str.isEmpty()) return false;
        return str.matches("\\d+");
    }
}
