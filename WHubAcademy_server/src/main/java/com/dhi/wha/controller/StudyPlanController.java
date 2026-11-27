package com.dhi.wha.controller;

import com.dhi.wha.constant.ClickRecord;
import com.dhi.wha.dto.AnswerFrontDTO;
import com.dhi.wha.dto.RegeneratePhaseDTO;
import com.dhi.wha.dto.StudyPlanChoiceDTO;
import com.dhi.wha.dto.StudyPlanDTO;
import com.dhi.wha.result.Result;
import com.dhi.wha.server.StudyPlanService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/pathPlan")
public class StudyPlanController {

    @Autowired
    private StudyPlanService studyPlanService;

    @Autowired
    private com.dhi.wha.utils.PythonRestClient pythonRestClient;

    /**
     * 获取学习计划列表
     * @param userId
     * @return
     */
    @GetMapping("/getPathPlan/{userId}")
    public Result<Object> getStudyPlanList(@PathVariable String userId){
        log.info("获取学习计划列表");
        return Result.success(studyPlanService.getStudyPlanList(userId));
    }

    /**
     * 获取指定的学习计划
     * @param userId
     * @param planId
     * @return
     */
    @ClickRecord(resourceType = "PATHPLAN", resourceIdParam = "")
    @GetMapping("/checkCreate/{userId}")
    public Result<Object> getPathPlan(@PathVariable String userId, String planId){
        log.info("获取指定的学习计划");
        return Result.success(studyPlanService.getPathPlan(userId, planId));
    }


    /**
     * 创建学习计划
     * @param studyPlanDTO
     * @return
     */
    @ClickRecord(resourceType = "PATHPLAN", resourceIdParam = "")
    @PostMapping("/createPathPlan")
    public Result<Object> createPathPlan(@RequestBody StudyPlanDTO studyPlanDTO){
        log.info("创建学习计划");
        return Result.success(studyPlanService.createPathPlan(studyPlanDTO));
    }


    /**
     * 删除学习计划
     * @param userId
     * @param planId
     * @return
     */
    @DeleteMapping("/deletePathPlan/{userId}/plan/{planId}")
    public Result<Object> deleteStudyPlan(
            @PathVariable String userId,
            @PathVariable String planId
    ){
        log.info("删除学习计划");
        return Result.success(studyPlanService.deleteStudyPlan(userId, planId));
    }

    /**
     * 获取指定路径的当前阶段
     * @param userId
     * @param planId
     * @return
     */
    @GetMapping("/currentPhase/{userId}")
    public Result<Object> getStudyPlanCurrentPhase(
            @PathVariable String userId,
            String planId
    ){
        log.info("获取学习计划当前阶段");
        return Result.success(studyPlanService.getStudyPlanCurrentPhase(userId, planId));
    }


    /**
     * 获取指定路径的指定阶段完成情况
     * @param userId
     * @param phaseIndex
     * @param planId
     * @return
     */
    @GetMapping("/completion/query/{userId}/{phaseIndex}/{planId}")
    public Result<Object> getStudyPlanCompletion(
            @PathVariable String userId,
            @PathVariable Integer phaseIndex,
            @PathVariable String planId
    ){
        log.info("获取学习计划完成度");
        return Result.success(studyPlanService.getStudyPlanCompletion(userId, phaseIndex, planId));
    }



    /**
     * 一键生成学习资源(这个之后需要加代码)
     * @param userId
     * @param phaseIndex
     * @param knowledgePoints
     * @return
     */
    @PostMapping("/OneClickGenerate/{userId}/{phaseIndex}")
    public Result<Object> oneClickGenerate(
            @PathVariable String userId,
            @PathVariable Integer phaseIndex,
            @RequestParam(value = "KonwledgePoints", required = true) String knowledgePoints
    ){
        log.info("一键生成学习资源");
        return Result.success(studyPlanService.oneClickGenerate(userId, phaseIndex, knowledgePoints));
    }


    /**
     * 检查续期计划状态
     * @param userId
     * @return
     */
    @GetMapping("/checkPathPlan/{userId}/{planId}")
    public Result<Object> checkStatus(
            @PathVariable String userId,
            @PathVariable String planId
    ){
        log.info("检查续期计划状态");
        return Result.success(studyPlanService.checkStatus(userId,planId));
    }


    /**
     * 接收续期计划
     * @param userId
     * @return
     */
    @PostMapping("/receiveContinuation/{userId}/{planId}")
    public Result<Object> receiveContinuation(
            @PathVariable String userId,
            @PathVariable String planId
    ){
        log.info("接收续期计划");
        return Result.success(studyPlanService.receiveContinuation(userId, planId));
    }


    /**
     * 拒绝续期计划建议
     * @param userId
     * @return
     */
    @PostMapping("/rejectRenewalSuggestion/{userId}/{planId}")
    public Result<Object> rejectRenewalSuggestion(
            @PathVariable String userId,
            @PathVariable String planId
    ){
        log.info("拒绝续期计划建议");
        return Result.success(studyPlanService.rejectRenewalSuggestion(userId, planId));
    }

    /**
     * 获取用户考试选择
     * @param userId
     * @param phaseIndex
     * @param
     * @return
     */
    @PostMapping("/exam/choice/{userId}/{phaseIndex}/{planId}")
    public Result<Object> getUserExamChoice(
            @PathVariable String userId,
            @PathVariable Integer phaseIndex,
            @PathVariable String planId
    ){
        log.info("获取用户考试选择");
        return Result.success(studyPlanService.getUserExamChoice(userId, phaseIndex,planId));
    }


    /**
     * 获取考试题目
     * @param userId
     * @param phaseIndex
     * @return
     */
    @GetMapping("/getExamQuestions/{userId}/{phaseIndex}")
    public Result<Object> getExamQuestions(
            @PathVariable String userId,
            @PathVariable Integer phaseIndex
    ){
        log.info("获取考试题目");
        return Result.success(studyPlanService.getExamQuestions(userId, phaseIndex));
    }


    /**
     * 提交答案
     * @param frontDTO
     * @param userId
     * @param phaseIndex
     * @return
     */
    @PostMapping("/submitAnswers/{userId}/{phaseIndex}")
    public Result<Object> submitAnswer(
            @RequestBody AnswerFrontDTO frontDTO,
            @PathVariable String userId,
            @PathVariable Integer phaseIndex
    ) {
        log.info("前端提交答案原始数据");
        try {
            Object resp = studyPlanService.submitAnswerToPython(frontDTO,userId,phaseIndex);
            return Result.success(resp);
        } catch (Exception e) {
            log.error("提交答案批改异常", e);
            return Result.error("批改服务调用失败");
        }
    }

    /**
     * 复习提醒
     * @param userId
     * @return
     */
    @GetMapping("/reviewReminder/{userId}")
    public Result<Object> getReviewReminder(@PathVariable String userId){
        log.info("复习提醒, userId: {}", userId);
        return Result.success(studyPlanService.getReviewReminder(userId));
    }

    /**
     * 近7天复习提醒
     * @param userId
     * @return
     */
    @GetMapping("/reviewReminder/sevenDays/{userId}")
    public Result<Object> getSevenDaysReviewReminder(@PathVariable String userId){
        log.info("近7天复习提醒, userId: {}", userId);
        return Result.success(studyPlanService.getSevenDaysReviewReminder(userId));
    }

    /**
     * 复习提醒总计
     * @param userId
     * @return
     */
    @GetMapping("/reviewReminder/allCount/{userId}")
    public Result<Object> getAllCountReviewReminder(@PathVariable String userId){
        log.info("复习提醒总计, userId: {}", userId);
        return Result.success(studyPlanService.getAllCountReviewReminder(userId));
    }

    /**
     * 获取学习计划版本树
     * @param userId
     * @param planId
     * @return
     */
    @GetMapping("/getVersionTree/{userId}/{planId}")
    public Result<Object> getVersionTree(
            @PathVariable String userId,
            @PathVariable String planId
    ){
        log.info("获取学习计划版本树, userId: {}, planId: {}", userId, planId);
        return Result.success(studyPlanService.getVersionTree(userId, planId));
    }

    /**
     * 切换版本树的当前执行中版本
     * @param userId
     * @param planId
     * @return
     */
    @GetMapping("/switchVersionTree/{userId}/{planId}")
    public Result<Object> switchVersionTree(
            @PathVariable String userId,
            @PathVariable String planId
    ){
        log.info("切换版本树当前执行中版本, userId: {}, planId: {}", userId, planId);
        return Result.success(studyPlanService.switchVersionTree(userId, planId));
    }

    /**
     * 重新生成某一阶段的计划
     * @param dto
     * @param userId
     * @return
     */
    @PostMapping("/LocalRegeneration/{userId}")
    public Result<Object> regeneratePhase(
            @RequestBody RegeneratePhaseDTO dto,
            @PathVariable String userId
    ){
        log.info("重新生成阶段计划, userId: {}", userId);
        return Result.success(studyPlanService.regeneratePhase(dto, userId));
    }

    /**
     * 接受阶段评估，触发下一阶段计划生成
     * @param userId
     * @param phaseIndex
     * @return
     */
    @PostMapping("/assessment/phase-apply/{userId}/{phaseIndex}")
    public Result<Object> phaseApply(
            @PathVariable String userId,
            @PathVariable Integer phaseIndex
    ){
        log.info("接受阶段评估, userId: {}, phaseIndex: {}", userId, phaseIndex);
        Object pythonResponse = pythonRestClient.postWithPathAndQueryNoBody(
                "/assessment/phase-apply/{userId}/{phaseIndex}", userId, phaseIndex);
        return Result.success(pythonResponse);
    }

    /**
     * 确认通知
     * @param userId
     * @param phaseIndex
     * @return
     */
    @PostMapping("/{userId}/notification/ack")
    public Result<Object> ackNotification(
            @PathVariable String userId,
            @RequestParam(value = "phase_index") Integer phaseIndex
    ){
        log.info("确认通知, userId: {}, phaseIndex: {}", userId, phaseIndex);
        Object pythonResponse = pythonRestClient.postWithPathAndQueryNoBody(
                "/study_plan/{userId}/notification/ack?phase_index={phaseIndex}", userId, phaseIndex);
        return Result.success(pythonResponse);
    }

    /**
     * 获取阶段通知（用于轮询评估报告是否生成完成）
     * @param userId
     * @return
     */
    @GetMapping("/{userId}/notification")
    public Result<Object> getPhaseNotification(@PathVariable String userId){
        log.info("获取阶段通知, userId: {}", userId);
        Object pythonResponse = pythonRestClient.getWithPathParam("/study_plan/{userId}/notification", userId);
        return Result.success(pythonResponse);
    }

}
