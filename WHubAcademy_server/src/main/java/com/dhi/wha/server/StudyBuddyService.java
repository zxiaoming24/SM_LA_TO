package com.dhi.wha.server;

import com.dhi.wha.dto.StudyBuddyAcceptDTO;
import com.dhi.wha.dto.StudyBuddyUserDTO;
import com.dhi.wha.dto.SubmitPairProgrammingCodeDTO;
import com.dhi.wha.dto.UpdateCodeDTO;

import java.util.Map;

public interface StudyBuddyService {
    /**
     * 获取指定用户所有学习buddy信息
     * @param userId
     * @return
     */
    Object searchStudyBuddy(String userId);

    /**
     * 邀请学习buddy
     * @param studyBuddyUserDTO
     * @return
     */
    Object inviteStudyBuddy(StudyBuddyUserDTO studyBuddyUserDTO);

    /**
     * 获取指定用户所有学习buddy信息
     * @param userId
     * @return
     */
    Object getStudyBuddyList(String userId);

    /**
     * 获取指定用户所有学习buddy信息
     * @param userId
     * @return
     */
    Object PendingInvitationsList(String userId);

    /**
     * 接受学习buddy邀请
     * @param studyBuddyAcceptDTO
     * @return
     */
    Object acceptInvitation(StudyBuddyAcceptDTO studyBuddyAcceptDTO);

    /**
     * 获取其他用户分享的资源
     * @param userId
     * @return
     */
    Object getOtherShareResources(String userId);

    /**
     * 分享资源给学伴/社区
     * @param request 分享请求参数
     * @return 分享结果
     */
    Object shareResources(Map<String, Object> request);


}
