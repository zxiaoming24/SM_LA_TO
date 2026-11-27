package com.dhi.wha.server.Impl;

import com.dhi.wha.dto.LearningAssessmentDTO;
import com.dhi.wha.dto.LearningAssessmentRejectDTO;
import com.dhi.wha.dto.LocalGenerationEvaluationDTO;
import com.dhi.wha.server.LearningAssessmentService;
import com.dhi.wha.utils.PythonRestClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;

@Service
public class LearningAssessmentServiceImpl implements LearningAssessmentService {

    @Autowired
    private PythonRestClient pythonRestClient;

    /**
     * 获取学习评估结果
     * @param userId
     * @return
     */
    @Override
    public Object getLearningAssessment(String userId) {
        return pythonRestClient.getWithPathParam("/assessment/latest/{user_id}", userId);
    }

    /**
     * 生成学习评估结果
     * @param userId
     * @return
     */
    @Override
    public Object generationLearningAssessment(String userId) {
        return pythonRestClient.postWithPathAndQueryNoBody("/assessment/generate/{user_id}", userId);
    }

    /**
     * 采纳建议
     * @param userId
     * @param learningAssessmentDTO
     * @return
     */
    @Override
    public Object adoptSuggestions(String userId, LearningAssessmentDTO learningAssessmentDTO) {
        Map<String, Object> body = new HashMap<>();
        body.put("suggestion_type", learningAssessmentDTO.getSuggestionType());
        body.put("content", learningAssessmentDTO.getContent());
        body.put("weight", learningAssessmentDTO.getWeight());
        return pythonRestClient.postWithPathParam("/assessment/adopt/{user_id}", body, userId);
    }

    /**
     * 获取建议
     * @param userId
     * @return
     */
    @Override
    public Object getSuggestions(String userId) {
        return pythonRestClient.getWithPathParam("/assessment/adopted/{user_id}", userId);
    }

    /**
     * 拒绝/撤销采纳建议
     * @param userId
     * @return
     */
    @Override
    public Object rejectSuggestions(String userId, LearningAssessmentRejectDTO learningAssessmentRejectDTO) {
        Map<String, Object> body = new HashMap<>();
        body.put("suggestion_type", learningAssessmentRejectDTO.getSuggestionType());
        body.put("content", learningAssessmentRejectDTO.getContent());
        return pythonRestClient.postWithPathParam("/assessment/reject/{user_id}", body, userId);
    }

    @Override
    public Object localGenerationEvaluation(String userId, LocalGenerationEvaluationDTO dto) {
        Map<String, Object> body = new HashMap<>();
        body.put("assessment_id", dto.getAssessmentId());
        body.put("part_type", dto.getPartType());
        if (dto.getPartIndex() != null) {
            body.put("part_index", dto.getPartIndex());
        }
        return pythonRestClient.postWithPathParam("/assessment/regenerate/{user_id}", body, userId);
    }

    @Override
    public Object getAssessmentNotifications(String userId) {
        return pythonRestClient.getWithPathParam("/assessment/notifications/{user_id}", userId);
    }

    @Override
    public Object markNotificationAsRead(String userId, Map<String, Object> body) {
        return pythonRestClient.postWithPathParam("/assessment/notifications/{user_id}/read", body, userId);
    }

}
