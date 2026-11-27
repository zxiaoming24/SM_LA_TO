package com.dhi.wha.controller;

import com.dhi.wha.dto.*;
import com.dhi.wha.result.Result;
import com.dhi.wha.server.InviteStudyTogetherService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@Slf4j
@RestController
@RequestMapping("/ColearningRecords")
public class InviteStudyTogetherController {

    @Autowired
    private InviteStudyTogetherService inviteStudyTogetherService;


    /**
     * 获取学习记录列表（历史共学记录的）
     * @param userId 用户ID
     * @return 学习记录列表
     */
    @GetMapping("/getRecordsList/{userId}")
    public Result<Object> getRecordsList(
            @PathVariable String userId
    ){
        log.info("获取学习记录列表");
        return Result.success(inviteStudyTogetherService.getRecordsList(userId));
    }


    /**
     * 获取待处理的共学邀请
     * @return 待处理的共学邀请
     */
    @GetMapping("/getInvitation/{userId}")
    public Result<Object> getInvitation(
            @PathVariable String userId
    ){
        log.info("获取待处理的共学邀请");
        return Result.success(inviteStudyTogetherService.getInvitation(userId));
    }


    /**
     * 接收或者拒绝邀请
     * @param acceptDeclineInvitationDTO
     * @return
     */
    @PostMapping("/AcceptInvitation")
    public Result<Object> acceptInvitation(
            @RequestBody AcceptDeclineInvitationDTO acceptDeclineInvitationDTO
            ){
        log.info("接收或者拒绝邀请");
        return Result.success(inviteStudyTogetherService.acceptInvitation(acceptDeclineInvitationDTO));
    }

    /**
     * 删除共学邀请
     * @param deleteInvitationDTO
     * @return
     */
    @PostMapping("/DeleteMessage")
    public Result<Object> deleteCoInvitation(
            @RequestBody DeleteInvitationDTO deleteInvitationDTO
            ){
        log.info("删除共学邀请");
        return Result.success(inviteStudyTogetherService.deleteCoInvitation(deleteInvitationDTO));
    }

    /**
     * 获取自己发送出去的邀请（含状态）
     * @param userId 用户ID
     * @return 发送出去的邀请列表
     */
    @GetMapping("/getMySentInvitations/{userId}")
    public Result<Object> getMySentInvitations(
            @PathVariable String userId
    ){
        log.info("获取自己发送出去的邀请, userId: {}", userId);
        return Result.success(inviteStudyTogetherService.getMySentInvitations(userId));
    }

    /**
     * 发送消息
     * @param sendMessageDTO 消息参数
     * @return 发送结果
     */
    @PostMapping("/SendMessage")
    public Result<Object> sendMessage(
            @RequestBody SendMessageDTO sendMessageDTO
    ){
        log.info("发送消息, invitationId: {}, senderId: {}", sendMessageDTO.getInvitationId(), sendMessageDTO.getSenderId());
        return Result.success(inviteStudyTogetherService.sendMessage(sendMessageDTO));
    }

    /**
     * 发送共学邀请
     * @param sendInvitationDTO 邀请参数
     * @return 发送结果
     */
    @PostMapping("/SendInvitation")
    public Result<Object> sendInvitation(
            @RequestBody SendInvitationDTO sendInvitationDTO
    ){
        log.info("发送共学邀请, inviterId: {}, inviteeId: {}, resourceType: {}, resourceId: {}", 
                sendInvitationDTO.getInviterId(), sendInvitationDTO.getInviteeId(), 
                sendInvitationDTO.getResourceType(), sendInvitationDTO.getResourceId());
        return Result.success(inviteStudyTogetherService.sendInvitation(sendInvitationDTO));
    }

    /**
     * 获取共学通知
     * @param userId 用户ID
     * @return 共学通知列表
     */
    @GetMapping("/getCoStudyNotifications/{userId}")
    public Result<Object> getCoStudyNotifications(
            @PathVariable String userId
    ){
        log.info("获取共学通知, userId: {}", userId);
        return Result.success(inviteStudyTogetherService.getCoStudyNotifications(userId));
    }

    /**
     * 获取共学详情
     * @param inviteId 邀请ID
     * @return 共学详情
     */
    @GetMapping("/GetDetails/{inviteId}")
    public Result<Object> getCoStudyDetails(@PathVariable String inviteId){
        log.info("获取共学详情, inviteId: {}", inviteId);
        return Result.success(inviteStudyTogetherService.getCoStudyDetails(inviteId));
    }

    /**
     * 获取共学会话消息列表
     * @param invitationId 邀请ID
     * @return 消息列表
     */
    @GetMapping("/GetMessage/{invitationId}")
    public Result<Object> getCoStudyMessages(@PathVariable String invitationId){
        log.info("获取共学会话消息列表, invitationId: {}", invitationId);
        return Result.success(inviteStudyTogetherService.getCoStudyMessages(invitationId));
    }

    /**
     * 对比两个人之间的成绩
     * @param problemId 题目ID
     * @param userIdA 用户A的ID
     * @param userIdB 用户B的ID
     * @return 成绩对比结果
     */
    @GetMapping("/CompareScores/{problemId}/{userId_a}/{userId_b}")
    public Result<Object> compareScores(
            @PathVariable String problemId,
            @PathVariable("userId_a") String userIdA,
            @PathVariable("userId_b") String userIdB){
        log.info("对比两个人之间的成绩, problemId: {}, userIdA: {}, userIdB: {}", problemId, userIdA, userIdB);
        return Result.success(inviteStudyTogetherService.compareScores(problemId, userIdA, userIdB));
    }

    /**
     * 获取结对编程会话
     * @param invitationId 邀请ID
     * @return 结对编程会话列表
     */
    @GetMapping("/getPairProgrammingSessions/{invitationId}")
    public Result<Object> getPairProgrammingSessions(@PathVariable String invitationId){
        log.info("获取结对编程会话, invitationId: {}", invitationId);
        return Result.success(inviteStudyTogetherService.getPairProgrammingSessions(invitationId));
    }

    /**
     * 更新结对编程代码
     * @param updateCodeDTO 更新代码请求
     * @return 更新结果
     */
    @PostMapping("/updateCode")
    public Result<Object> updateCode(@RequestBody UpdateCodeDTO updateCodeDTO){
        log.info("更新结对编程代码, invitationId: {}, userId: {}", updateCodeDTO.getInvitationId(), updateCodeDTO.getUserId());
        return Result.success(inviteStudyTogetherService.updateCode(updateCodeDTO));
    }

    /**
     * 提交结对编程代码
     * @param submitDTO 提交代码请求
     * @return 提交结果
     */
    @PostMapping("/submitPairProgrammingCode")
    public Result<Object> submitPairProgrammingCode(@RequestBody SubmitPairProgrammingCodeDTO submitDTO){
        log.info("提交结对编程代码, invitationId: {}, submitterId: {}", submitDTO.getInvitationId(), submitDTO.getSubmitterId());
        return Result.success(inviteStudyTogetherService.submitPairProgrammingCode(submitDTO));
    }


}
