package com.dhi.wha.server;

import com.dhi.wha.dto.AnswerFrontDTO;
import com.dhi.wha.dto.RegeneratePhaseDTO;
import com.dhi.wha.dto.StudyPlanChoiceDTO;
import com.dhi.wha.dto.StudyPlanDTO;

public interface StudyPlanService {
    /**
     * 获取学习计划列表
     * @param userId
     * @return
     */
    Object getStudyPlanList(String userId);

    /**
     * 获取指定路径下的学习计划列表
     * @param userId
     * @param pathId
     * @return
     */
    Object getPathPlan(String userId, String pathId);

    /**
     * 创建学习计划
     * @param studyPlanDTO
     * @return
     */
    Object createPathPlan(StudyPlanDTO studyPlanDTO);

    /**
     * 删除学习计划
     * @param userId
     * @param planId
     * @return
     */
    Object deleteStudyPlan(String userId, String planId);

    /**
     * 获取指定路径的当前阶段
     * @param userId
     * @param pathId
     * @return
     */
    Object getStudyPlanCurrentPhase(String userId, String pathId);

    /**
     * 获取指定路径的指定阶段完成情况
     * @param userId
     * @param phaseIndex
     * @param planId
     * @return
     */
    Object getStudyPlanCompletion(String userId, Integer phaseIndex, String planId);

    /**
     * 一键生成
     * @param userId
     * @param phaseIndex
     * @param knowledgePoint
     * @return
     */
    Object oneClickGenerate(String userId, Integer phaseIndex, String knowledgePoint);

    /**
     * 检查学习计划状态
     * @param userId
     * @return
     */
    Object checkStatus(String userId, String pathId);

    /**
     * 接收续期计划
     * @param userId
     * @return
     */
    Object receiveContinuation(String userId, String pathId);

    /**
     * 拒绝续期计划
     * @param userId
     * @return
     */
    Object rejectRenewalSuggestion(String userId,String pathId);

    /**
     * 获取用户考试选择
     * @param userId
     * @param phaseIndex
     * @param
     * @return
     */
    Object getUserExamChoice(String userId, Integer phaseIndex, String pathId);

    /**
     * 获取考试问题
     * @param userId
     * @param phaseIndex
     * @return
     */
    Object getExamQuestions(String userId, Integer phaseIndex);


    /**
     * 提交答案
     * @param frontDTO
     * @param userId
     * @param phaseIndex
     * @return
     */
    Object submitAnswerToPython(AnswerFrontDTO frontDTO, String userId, Integer phaseIndex) throws Exception;

    /**
     * 复习提醒
     * @param userId
     * @return
     */
    Object getReviewReminder(String userId);

    /**
     * 近7天复习提醒
     * @param userId
     * @return
     */
    Object getSevenDaysReviewReminder(String userId);

    /**
     * 复习提醒总计
     * @param userId
     * @return
     */
    Object getAllCountReviewReminder(String userId);

    /**
     * 获取学习计划版本树
     * @param userId
     * @param planId
     * @return
     */
    Object getVersionTree(String userId, String planId);

    /**
     * 切换版本树的当前执行中版本
     * @param userId
     * @param planId
     * @return
     */
    Object switchVersionTree(String userId, String planId);

    /**
     * 重新生成某一阶段的计划
     * @param dto
     * @param userId
     * @return
     */
    Object regeneratePhase(RegeneratePhaseDTO dto, String userId);
}
