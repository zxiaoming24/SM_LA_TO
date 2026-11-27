package com.dhi.wha.server.Impl;

import com.dhi.wha.dto.StudyBuddyAcceptDTO;
import com.dhi.wha.dto.StudyBuddyUserDTO;
import com.dhi.wha.dto.SubmitPairProgrammingCodeDTO;
import com.dhi.wha.dto.UpdateCodeDTO;
import com.dhi.wha.mapper.PracticeMapper;
import com.dhi.wha.mapper.VideoMapper;
import com.dhi.wha.mapper.WordMapper;
import com.dhi.wha.mapper.ExtensionReadingMapper;
import com.dhi.wha.mapper.MindMapMapper;
import com.dhi.wha.mapper.PaperMapper;
import com.dhi.wha.mapper.AnimationMapper;
import com.dhi.wha.mapper.PptMapper;
import com.dhi.wha.server.StudyBuddyService;
import com.dhi.wha.utils.PythonRestClient;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;

@Slf4j
@Service
public class StudyBuddyServiceImpl implements StudyBuddyService {

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
    public Object searchStudyBuddy(String userId) {
        return pythonRestClient.getWithPathParam("/companion/match/{user_id}", userId);
    }

    @Override
    public Object inviteStudyBuddy(StudyBuddyUserDTO studyBuddyUserDTO) {
        Map<String, Object> pythonParam = new HashMap<>();
        pythonParam.put("from_user", studyBuddyUserDTO.getFromUser());
        pythonParam.put("to_user", studyBuddyUserDTO.getToUser());
        return pythonRestClient.post("/companion/invite", pythonParam);
    }

    @Override
    public Object getStudyBuddyList(String userId) {
        return pythonRestClient.getWithPathParam("/companion/list/{user_id}", userId);
    }

    @Override
    public Object PendingInvitationsList(String userId) {
        return pythonRestClient.getWithPathParam("/companion/pending/{user_id}", userId);
    }

    @Override
    public Object acceptInvitation(StudyBuddyAcceptDTO studyBuddyAcceptDTO) {
        Map<String, Object> pythonParam = new HashMap<>();
        pythonParam.put("user_id", studyBuddyAcceptDTO.getUserId());
        pythonParam.put("companion_id", studyBuddyAcceptDTO.getCompanionId());
        pythonParam.put("accept", studyBuddyAcceptDTO.getAccept());
        return pythonRestClient.post("/companion/respond", pythonParam);
    }

    @Override
    public Object getOtherShareResources(String userId) {
        return pythonRestClient.getWithPathParam("/companion/shared/to-me/{user_id}", userId);
    }

    @Override
    public Object shareResources(Map<String, Object> request) {
        // sharer_id 数字转Integer
        Integer sharerId = null;
        Object sharerIdObj = request.get("sharer_id");
        if (sharerIdObj != null) {
            sharerId = Integer.parseInt(sharerIdObj.toString());
        }

        // receiver_id 统一转字符串，不管源头是数字还是字符串
        String receiverId = null;
        Object receiverIdObj = request.get("receiver_id");
        if (receiverIdObj != null) {
            receiverId = receiverIdObj.toString();
        }

        String resourceType = null;
        Object typeObj = request.get("resource_type");
        if (typeObj != null) {
            resourceType = typeObj.toString();
        }

        // resource_id 数字转Integer
        Integer resourceId = null;
        Object resIdObj = request.get("resource_id");
        if (resIdObj != null) {
            resourceId = Integer.parseInt(resIdObj.toString());
        }

        if (sharerId == null || receiverId == null || resourceType == null || resourceId == null) {
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("success", false);
            errorResult.put("message", "参数不完整");
            return errorResult;
        }

        String pythonResourceId = null;
        String pythonResourceType = resourceType;

        try {
            if ("practice".equals(resourceType)) {
                pythonResourceId = practiceMapper.getProblemId(resourceId.longValue());
            } else if ("document".equals(resourceType)) {
                pythonResourceId = wordMapper.getResourceIdById(resourceId);
                pythonResourceType = "doc";
            } else if ("video".equals(resourceType)) {
                pythonResourceId = videoMapper.getResourceIdById(resourceId.longValue());
            } else if ("extension".equals(resourceType)) {
                pythonResourceId = extensionReadingMapper.getResourceIdById(resourceId.longValue());
            } else if ("mindmap".equals(resourceType)) {
                pythonResourceId = mindMapMapper.getResourceIdById(resourceId.longValue());
            } else if ("question".equals(resourceType)) {
                pythonResourceId = paperMapper.getResourceIdById(resourceId.longValue());
            } else if ("animation".equals(resourceType)) {
                pythonResourceId = animationMapper.getResourceIdById(resourceId.longValue());
            } else if ("ppt".equals(resourceType)) {
                pythonResourceId = pptMapper.getResourceIdById(resourceId.longValue());
            } else {
                Map<String, Object> errorResult = new HashMap<>();
                errorResult.put("success", false);
                errorResult.put("message", "暂不支持该资源类型");
                return errorResult;
            }
        } catch (Exception e) {
            log.error("查询资源ID失败", e);
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("success", false);
            errorResult.put("message", "查询资源ID失败");
            return errorResult;
        }

        if (pythonResourceId == null) {
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("success", false);
            errorResult.put("message", "资源不存在");
            return errorResult;
        }

        try {
            Map<String, Object> body = new HashMap<>();
            body.put("sharer_id", sharerId.toString());
            body.put("receiver_id", receiverId);
            body.put("resource_type", pythonResourceType);
            body.put("resource_id", pythonResourceId);

            Object pythonRes = pythonRestClient.post("/companion/share", body);
            return pythonRes;
        } catch (Exception e) {
            log.error("调用Python端分享接口失败", e);
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("success", false);
            errorResult.put("message", "分享失败");
            return errorResult;
        }
    }
}