package com.dhi.wha.controller;


import com.dhi.wha.constant.ClickRecord;
import com.dhi.wha.dto.LearningAssessmentDTO;
import com.dhi.wha.dto.LearningAssessmentRejectDTO;
import com.dhi.wha.dto.LocalGenerationEvaluationDTO;
import com.dhi.wha.result.Result;
import com.dhi.wha.server.LearningAssessmentService;

import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@Slf4j
@RestController
@RequestMapping("/LearningAssessment")
public class LearningAssessmentController {

    @Autowired
    private LearningAssessmentService learningAssessmentService;

    /**
     * 获取最新的学习评估
     * @param userId
     * @return
     */
    @ClickRecord(resourceType = "EVALUATE", resourceIdParam = "")
    @GetMapping("/getAssessment/{userId}")
    public Result<Object> getLearningAssessment(@PathVariable String userId){
        log.info("获取最新的学习评估");
        return Result.success(learningAssessmentService.getLearningAssessment(userId));
    }


    /**
     * 生成学习评估
     * @param userId
     * @return
     */
    @ClickRecord(resourceType = "EVALUATE", resourceIdParam = "")
    @PostMapping("/GenerationAssessment/{userId}")
    public Result<Object> generationLearningAssessment(@PathVariable String userId){
        log.info("生成学习评估");
        try {
            return Result.success(learningAssessmentService.generationLearningAssessment(userId));
        } catch (Exception e) {
            log.error("生成学习评估失败", e);
            return Result.error("生成学习评估失败");
        }
    }


    /**
     * 采纳建议
     * @param userId
     * @return
     */
    @PostMapping("/AdoptSuggestions/{userId}")
    public Result<Object> adoptSuggestions
    (@PathVariable String userId,
     @RequestBody LearningAssessmentDTO learningAssessmentDTO
    ){
        log.info("采纳建议");
        return Result.success(learningAssessmentService.adoptSuggestions(userId, learningAssessmentDTO));
    }



    /**
     * 获取建议
     * @param userId
     * @return
     */
    @GetMapping("/getSuggestions/{userId}")
    public Result<Object> getSuggestions(@PathVariable String userId){
        log.info("获取建议");
        return Result.success(learningAssessmentService.getSuggestions(userId));
    }


    /**
     * 拒绝/撤销采纳建议
     * @param userId
     * @return
     */
    @PostMapping("/rejectSuggestions/{userId}")
    public Result<Object> rejectSuggestions(
            @PathVariable String userId,
            @RequestBody LearningAssessmentRejectDTO learningAssessmentRejectDTO
    ){
        log.info("拒绝/撤销采纳建议");
        return Result.success(learningAssessmentService.rejectSuggestions(userId,learningAssessmentRejectDTO));
    }

    /**
     * 局部生成评估
     * @param userId
     * @param dto
     * @return
     */
    @PostMapping("/LocalGenerationEvaluation/{userId}")
    public Result<Object> localGenerationEvaluation(
            @PathVariable String userId,
            @RequestBody LocalGenerationEvaluationDTO dto
    ){
        try {
            log.info("局部生成评估, userId: {}, dto: {}", userId, dto);
            return Result.success(learningAssessmentService.localGenerationEvaluation(userId, dto));
        } catch (Exception e) {
            log.error("局部生成评估失败", e);
            return Result.error("局部生成评估失败");
        }
    }

    /**
     * 获取评估报告通知
     * @param userId
     * @return
     */
    @GetMapping("/notifications/{userId}")
    public Result<Object> getAssessmentNotifications(@PathVariable String userId){
        log.info("获取评估报告通知, userId: {}", userId);
        return Result.success(learningAssessmentService.getAssessmentNotifications(userId));
    }

    /**
     * 标记评估报告通知为已读
     * @param userId
     * @param body
     * @return
     */
    @PostMapping("/notifications/{userId}/read")
    public Result<Object> markNotificationAsRead(
            @PathVariable String userId,
            @RequestBody Map<String, Object> body
    ){
        log.info("标记评估报告通知为已读, userId: {}, body: {}", userId, body);
        return Result.success(learningAssessmentService.markNotificationAsRead(userId, body));
    }
}
