package com.dhi.wha.server;

import com.dhi.wha.dto.*;

public interface InviteStudyTogetherService {
    /**
     * 获取指定用户所有邀请记录
     * @param userId
     * @return
     */
    Object getRecordsList(String userId);


    /**
     * 获取待处理的共学邀请
     * @param userId
     * @return
     */
    Object getInvitation(String userId);

    /**
     * 接收或者拒绝邀请
     * @param acceptDeclineInvitationDTO
     * @return
     */
    Object acceptInvitation(AcceptDeclineInvitationDTO acceptDeclineInvitationDTO);

    /**
     * 删除共学邀请
     * @param deleteInvitationDTO
     * @return
     */
    Object deleteCoInvitation(DeleteInvitationDTO deleteInvitationDTO);

    /**
     * 获取自己发送出去的邀请（含状态）
     * @param userId 用户ID
     * @return 发送出去的邀请列表
     */
    Object getMySentInvitations(String userId);

    /**
     * 发送消息
     * @param sendMessageDTO 消息参数
     * @return 发送结果
     */
    Object sendMessage(SendMessageDTO sendMessageDTO);

    /**
     * 发送共学邀请
     * @param sendInvitationDTO 邀请参数
     * @return 发送结果
     */
    Object sendInvitation(SendInvitationDTO sendInvitationDTO);

    /**
     * 获取共学通知
     * @param userId 用户ID
     * @return 共学通知列表
     */
    Object getCoStudyNotifications(String userId);

    /**
     * 获取共学详情
     * @param inviteId 邀请ID
     * @return 共学详情
     */
    Object getCoStudyDetails(String inviteId);

    /**
     * 获取共学会话消息列表
     * @param invitationId 邀请ID
     * @return 消息列表
     */
    Object getCoStudyMessages(String invitationId);

    /**
     * 对比两个人之间的成绩
     * @param problemId 题目ID
     * @param userIdA 用户A的ID
     * @param userIdB 用户B的ID
     * @return 成绩对比结果
     */
    Object compareScores(String problemId, String userIdA, String userIdB);

    /**
     * 获取结对编程会话
     * @param invitationId 邀请ID
     * @return 结对编程会话列表
     */
    Object getPairProgrammingSessions(String invitationId);

    /**
     * 更新结对编程代码
     * @param updateCodeDTO 更新代码请求
     * @return 更新结果
     */
    Object updateCode(UpdateCodeDTO updateCodeDTO);

    /**
     * 提交结对编程代码
     * @param submitDTO 提交代码请求
     * @return 提交结果
     */
    Object submitPairProgrammingCode(SubmitPairProgrammingCodeDTO submitDTO);

}
