package com.dhi.wha.server.Impl;

import com.dhi.wha.dto.*;
import com.dhi.wha.entity.Ppt;
import com.dhi.wha.mapper.*;
import com.dhi.wha.server.InviteStudyTogetherService;
import com.dhi.wha.utils.PythonRestClient;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;

@Slf4j
@Service
public class InviteStudyTogetherServiceImpl implements InviteStudyTogetherService {

    @Autowired
    private PythonRestClient pythonRestClient;

    @Autowired
    private PracticeMapper practiceMapper;

    @Autowired
    private WordMapper wordMapper;

    @Autowired
    private VideoMapper videoMapper;

    @Autowired
    private ExtensionReadingMapper extensionReadingMapper;

    @Autowired
    private MindMapMapper mindMapMapper;

    @Autowired
    private PaperMapper paperMapper;

    @Autowired
    private AnimationMapper animationMapper;

    @Autowired
    private PptMapper pptMapper;

    @Override
    public Object getRecordsList(String userId) {
        return pythonRestClient.getWithPathParam("/companion/co-study/sessions/{user_id}", userId);
    }

    @Override
    public Object getInvitation(String userId) {
        return pythonRestClient.getWithPathParam("/companion/co-study/invites/{user_id}", userId);
    }

    @Override
    public Object acceptInvitation(AcceptDeclineInvitationDTO acceptDeclineInvitationDTO) {
        Map<String, Object> pythonParam = new HashMap<>();
        pythonParam.put("invite_id", acceptDeclineInvitationDTO.getInviteId());
        pythonParam.put("accept", acceptDeclineInvitationDTO.getAccept());
        return pythonRestClient.post("/companion/co-study/respond", pythonParam);
    }

    @Override
    public Object deleteCoInvitation(DeleteInvitationDTO deleteInvitationDTO) {
        Map<String, Object> pythonParam = new HashMap<>();
        pythonParam.put("invitation_id", deleteInvitationDTO.getInvitationId());
        pythonParam.put("user_id", deleteInvitationDTO.getUserId());
        return pythonRestClient.post("/companion/co-study/delete", pythonParam);
    }

    @Override
    public Object getMySentInvitations(String userId) {
        return pythonRestClient.getWithPathParam("/companion/co-study/sent/{user_id}", userId);
    }

    @Override
    public Object sendMessage(SendMessageDTO sendMessageDTO) {
        Map<String, Object> pythonParam = new HashMap<>();
        pythonParam.put("invitation_id", sendMessageDTO.getInvitationId());
        pythonParam.put("sender_id", sendMessageDTO.getSenderId());
        pythonParam.put("content", sendMessageDTO.getContent());
        return pythonRestClient.post("/companion/co-study/message", pythonParam);
    }

    @Override
    public Object sendInvitation(SendInvitationDTO sendInvitationDTO) {
        String inviterId = sendInvitationDTO.getInviterId();
        String inviteeId = sendInvitationDTO.getInviteeId();
        String resourceType = sendInvitationDTO.getResourceType();
        String mode = sendInvitationDTO.getMode();
        Integer resourceId = sendInvitationDTO.getResourceId();

        if (inviterId == null || inviteeId == null || resourceType == null || resourceId == null || mode == null) {
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("success", false);
            errorResult.put("message", "参数不完整");
            return errorResult;
        }

        String pythonResourceId = null;
        String pythonResourceType = resourceType;
        String title = null;

        try {
            switch (resourceType) {
                case "extension":
                    pythonResourceId = extensionReadingMapper.getResourceIdById(resourceId.longValue());
                    title = extensionReadingMapper.selectById(resourceId.longValue()).getTitle();
                    break;
                case "practice":
                    pythonResourceId = practiceMapper.getProblemId(resourceId.longValue());
                    title = practiceMapper.selectById(resourceId.longValue()).getTitle();
                    break;
                case "question":
                    pythonResourceId = paperMapper.getResourceIdById(resourceId.longValue());
                    title = paperMapper.selectById(resourceId.longValue()).getPaperName();
                    break;
                case "document":
                    pythonResourceId = wordMapper.getResourceIdById(resourceId);
                    title = wordMapper.selectById(resourceId).getText();
                    pythonResourceType = "doc";
                    break;
                case "animation":
                    pythonResourceId = animationMapper.getResourceIdById(resourceId.longValue());
                    title = animationMapper.selectById(resourceId.longValue()).getText();
                    break;
                case "video":
                    pythonResourceId = videoMapper.getResourceIdById(resourceId.longValue());
                    title = videoMapper.selectById(resourceId.longValue()).getTitle();
                    break;
                case "ppt":
                    pythonResourceId = pptMapper.getResourceIdById(resourceId.longValue());
                    Ppt ppt = pptMapper.selectById(resourceId.longValue());
                    if (ppt != null) {
                        title = ppt.getTaskId(); // PPT标题放在taskId字段中
                    }
                    break;
                case "mindmap":
                    pythonResourceId = mindMapMapper.getResourceIdById(resourceId.longValue());
                    title = mindMapMapper.selectById(resourceId.longValue()).getText();
                    break;
                default:
                    Map<String, Object> errorResult = new HashMap<>();
                    errorResult.put("success", false);
                    errorResult.put("message", "暂不支持该资源类型");
                    return errorResult;
            }
        } catch (Exception e) {
            log.error("查询资源信息失败", e);
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("success", false);
            errorResult.put("message", "查询资源信息失败");
            return errorResult;
        }

        if (pythonResourceId == null) {
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("success", false);
            errorResult.put("message", "资源不存在");
            return errorResult;
        }

        if (title == null || title.isEmpty()) {
            title = "未命名资源";
        }

        try {
            Map<String, Object> body = new HashMap<>();
            body.put("inviter_id", inviterId);
            body.put("invitee_id", inviteeId);
            body.put("mode", mode);
            body.put("resource_type", pythonResourceType);
            body.put("resource_id", pythonResourceId);
            body.put("title", title);

            Object pythonRes = pythonRestClient.post("/companion/co-study/invite", body);
            return pythonRes;
        } catch (Exception e) {
            log.error("调用Python端共学邀请接口失败", e);
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("success", false);
            errorResult.put("message", "发送邀请失败");
            return errorResult;
        }
    }

    @Override
    public Object getCoStudyNotifications(String userId) {
        return pythonRestClient.getWithPathParam("/companion/co-study/notifications/{user_id}", userId);
    }

    @Override
    public Object getCoStudyDetails(String inviteId) {
        return pythonRestClient.getWithPathParam("/companion/co-study/invitation/{invite_id}", inviteId);
    }

    @Override
    public Object getCoStudyMessages(String invitationId) {
        return pythonRestClient.getWithPathParam("/companion/co-study/messages/{invitation_id}", invitationId);
    }

    @Override
    public Object compareScores(String problemId, String userIdA, String userIdB) {
        return pythonRestClient.getWithPathParam("/companion/compare/{problem_id}/{user_id_a}/{user_id_b}",
                problemId, userIdA, userIdB);
    }

    @Override
    public Object getPairProgrammingSessions(String invitationId) {
        return pythonRestClient.getWithPathParam("/companion/pair/session/{invitation_id}", invitationId);
    }

    @Override
    public Object updateCode(UpdateCodeDTO updateCodeDTO) {
        Map<String, Object> body = new HashMap<>();
        body.put("invitation_id", updateCodeDTO.getInvitationId());
        body.put("user_id", updateCodeDTO.getUserId());
        body.put("code_content", updateCodeDTO.getCodeContent());
        body.put("language", updateCodeDTO.getLanguage());
        return pythonRestClient.post("/companion/pair/code", body);
    }

    @Override
    public Object submitPairProgrammingCode(SubmitPairProgrammingCodeDTO submitDTO) {
        Map<String, Object> body = new HashMap<>();
        body.put("invitation_id", submitDTO.getInvitationId());
        body.put("submitter_id", submitDTO.getSubmitterId());
        body.put("language", submitDTO.getLanguage());
        return pythonRestClient.post("/companion/pair/submit", body);
    }
}