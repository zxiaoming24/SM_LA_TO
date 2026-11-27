package com.dhi.wha.server;

import com.dhi.wha.dto.LearningAssessmentDTO;
import com.dhi.wha.dto.LearningAssessmentRejectDTO;
import com.dhi.wha.dto.LocalGenerationEvaluationDTO;

import java.util.Map;

public interface LearningAssessmentService {
    /**
     * 获取学习评估
     * @param userId
     * @return
     */
    Object getLearningAssessment(String userId);

    /**
     * 生成学习评估
     * @param userId
     * @return
     */
    Object generationLearningAssessment(String userId);

    /**
     * 采纳建议
     * @param userId
     * @param learningAssessmentDTO
     * @return
     */
    Object adoptSuggestions(String userId, LearningAssessmentDTO learningAssessmentDTO);

    /**
     * 获取建议
     * @param userId
     * @return
     */
    Object getSuggestions(String userId);

    /**
     * 拒绝/撤销采纳建议
     * @param userId
     * @return
     */
    Object rejectSuggestions(String userId, LearningAssessmentRejectDTO learningAssessmentRejectDTO);

    /**
     * 局部生成评估
     * @param userId
     * @param dto
     * @return
     */
    Object localGenerationEvaluation(String userId, LocalGenerationEvaluationDTO dto);

    /**
     * 获取评估报告通知
     * @param userId
     * @return
     */
    Object getAssessmentNotifications(String userId);

    /**
     * 标记评估报告通知为已读
     * @param userId
     * @param body
     * @return
     */
    Object markNotificationAsRead(String userId, Map<String, Object> body);
}
