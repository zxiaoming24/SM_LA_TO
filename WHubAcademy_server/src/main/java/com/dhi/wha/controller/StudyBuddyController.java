package com.dhi.wha.controller;

import com.dhi.wha.constant.ClickRecord;
import com.dhi.wha.dto.StudyBuddyAcceptDTO;
import com.dhi.wha.dto.StudyBuddyUserDTO;
import com.dhi.wha.dto.SubmitPairProgrammingCodeDTO;
import com.dhi.wha.dto.UpdateCodeDTO;
import com.dhi.wha.result.Result;
import com.dhi.wha.server.StudyBuddyService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/StudyBuddy")
public class StudyBuddyController {


    @Autowired
    private StudyBuddyService studyBuddyService;

    /**
     * 搜索学伴
     * @param userId
     * @return
     */
    @ClickRecord(resourceType = "PARTNERS", resourceIdParam = "")
    @GetMapping("/Search/{userId}")
    public Result<Object> searchStudyBuddy(@PathVariable String userId){
        log.info("搜索学伴");
        Object data = studyBuddyService.searchStudyBuddy(userId);
        if (data == null) {
            return Result.error("未找到相关学伴信息");
        }
        return Result.success(data);
    }


    /**
     * 邀请学伴
     * @param studyBuddyUserDTO
     * @return
     */
    @ClickRecord(resourceType = "PARTNERS", resourceIdParam = "")
    @PostMapping("/Invite")
    public Result<Object> inviteStudyBuddy(
            @RequestBody StudyBuddyUserDTO studyBuddyUserDTO){
        log.info("邀请学伴");
        return Result.success(studyBuddyService.inviteStudyBuddy(studyBuddyUserDTO));
    }


    /**
     * 获取学伴列表
     * @param userId
     * @return
     */
    @GetMapping("/getStudyBuddyList/{userId}")
    public Result<Object> getStudyBuddyList(@PathVariable String userId){
        log.info("获取学伴列表");
        return Result.success(studyBuddyService.getStudyBuddyList(userId));
    }

    /**
     * 获取待处理的邀请列表
     * @param userId
     * @return
     */
    @GetMapping("/PendingInvitations/{userId}")
    public Result<Object> PendingInvitationsList(@PathVariable String userId){
        log.info("获取待处理的邀请列表");
        return Result.success(studyBuddyService.PendingInvitationsList(userId));
    }

    /**
     * 接受或拒绝邀请
     * @param studyBuddyAcceptDTO
     * @return
     */
    @PostMapping("/Accept")
    public Result<Object> acceptInvitation(
            @RequestBody StudyBuddyAcceptDTO studyBuddyAcceptDTO){
        log.info("接受邀请");
        return Result.success(studyBuddyService.acceptInvitation(studyBuddyAcceptDTO));
    }


    /**
     * 获取其他人分享的资源
     * @param userId
     * @return
     */
    @GetMapping("/getOtherShareResources/{userId}")
    public Result<Object> getOtherShareResources(@PathVariable String userId){
        log.info("获取其他人分享的资源");
        return Result.success(studyBuddyService.getOtherShareResources(userId));
    }

    /**
     * 分享资源给学伴/社区
     * @param request 分享请求参数
     * @return 分享结果
     */
    @PostMapping("/shareResources")
    public Result<Object> shareResources(@RequestBody Map<String, Object> request) {
        try
        {
            log.info("分享资源给学伴/社区, request: {}", request);
            Object result = studyBuddyService.shareResources(request);
            return Result.success(result);
        }catch (Exception e){
            log.error("分享资源失败", e);
            return Result.error("分享资源失败");
        }
    }


}
