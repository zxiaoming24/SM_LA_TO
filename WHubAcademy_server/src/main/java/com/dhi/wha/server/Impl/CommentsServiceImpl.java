package com.dhi.wha.server.Impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.dhi.wha.dto.CommentDTO;
import com.dhi.wha.dto.CommentPostDTO;
import com.dhi.wha.dto.PostAssistantDTO;
import com.dhi.wha.dto.PostAssistantSubmitDTO;
import com.dhi.wha.entity.*;
import com.dhi.wha.mapper.*;
import com.dhi.wha.server.CommentsService;
import com.dhi.wha.utils.PythonRestClient;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
public class CommentsServiceImpl implements CommentsService {

    @Autowired
    private PythonRestClient pythonRestClient;

    @Autowired
    private ExtensionReadingMapper extensionReadingMapper;

    @Autowired
    private PracticeMapper practiceMapper;

    @Autowired
    private PaperMapper paperMapper;

    @Autowired
    private WordMapper wordMapper;

    @Autowired
    private AnimationMapper animationMapper;

    @Autowired
    private VideoMapper videoMapper;

    @Autowired
    private MindMapMapper mindMapMapper;

    @Autowired
    private SingleChoiceMapper singleChoiceMapper;

    @Autowired
    private MultipleChoiceMapper multipleChoiceMapper;

    @Autowired
    private JudgeMapper judgeMapper;

    @Autowired
    private FillBlankMapper fillBlankMapper;

    @Autowired
    private ShortAnswerMapper shortAnswerMapper;

    @Autowired
    private PptMapper pptMapper;


    private static final Map<Integer, String> ZONE_MAP = new HashMap<Integer, String>() {{
        put(1, "learning");
        put(2, "life");
        put(3, "resource");
        put(4, "feedback");
    }};


    /**
     * 获取评论列表
     * @param page
     * @param pageSize
     * @param zone
     * @return
     */
    @Override
    public Object getCommentsList(Integer page, Integer pageSize, Integer zone) {
        try {
            if (zone == 0) {
                return pythonRestClient.getWithQueryParam(
                        "/community/posts?page={page}&page_size={pageSize}", page, pageSize);
            }
            String zoneName = ZONE_MAP.get(zone);
            if (zoneName == null) {
                return "zone参数错误";
            }
            return pythonRestClient.getWithQueryParam(
                    "/community/posts?page={page}&page_size={pageSize}&zone={zone}", page, pageSize, zoneName);
        } catch (Exception e) {
            return "获取失败";
        }
    }

    /**
     * 获取指定评论
     * @param postId
     * @return
     */
    @Override
    public Object getCommentsById(String postId) {
        try{
            return pythonRestClient.getWithPathParam("/community/post/{post_id}", postId);
        }
        catch (Exception e){
            return "获取失败";
        }
    }

    /**
     * 回复帖子
     * @param commentDTO
     * @return
     */
    @Override
    public Object replyPost(CommentDTO commentDTO) {
        try{
            Map<String, Object> pythonParam = new HashMap<>();
            pythonParam.put("user_id", commentDTO.getUserId());
            pythonParam.put("post_id", commentDTO.getPostId());
            pythonParam.put("content", commentDTO.getContent() + "\n" + commentDTO.getUrl());
            pythonParam.put("parent_reply_id", commentDTO.getParentReplyId());
            return pythonRestClient.post("/community/reply", pythonParam);
        }
        catch (Exception e){
            return "回复失败";
        }
    }

    /**
     * 删除回复（注意，这里的用户id我是写死了的）
     * @param userId
     * @param replyId
     * @return
     */
    @Override
    public Object deleteReply(String userId, String replyId) {
        try{
            return pythonRestClient.deleteWithPathParam("/community/reply/{reply_id}/{user_id}", replyId, userId);
        }
        catch (Exception e){
            return "删除失败";
        }
    }

    /**
     * 删除帖子（注意，这里的用户id我是写死了的）
     * @param postId
     * @param userId
     * @return
     */
    @Override
    public Object deletePost(String postId, String userId) {
        try{
            return pythonRestClient.deleteWithPathParam("/community/post/{post_id}/{user_id}", postId, userId);
        }
        catch (Exception e){
            return "删除失败";
        }
    }

    /**
     * 提交帖子
     * @param param
     * @return
     */
    @Override
    public Object submitPost(CommentPostDTO param) {
        String zoneName = "";
        switch (param.getZone()) {
            case 1:
                zoneName = "learning";
                break;
            case 2:
                zoneName = "life";
                break;
            case 3:
                zoneName = "resource";
                break;
            case 4:
                zoneName = "feedback";
                break;
        }
        try{
            Map<String, Object> pythonParam = new HashMap<>();
            pythonParam.put("user_id", param.getUserId());
            pythonParam.put("title", param.getTitle());
            //将内容后面加上链接
            pythonParam.put("content", param.getContent() + "\n\n" + param.getUrl());
            pythonParam.put("zone", zoneName);
            pythonParam.put("tags", param.getTags());
            return pythonRestClient.post("/community/post", pythonParam);
        }
        catch (Exception e){
            return "提交失败";
        }
    }

    /**
     * AI生成帖子内容(发帖助手)
     * @param postAssistantDTO
     * @return
     */
    @Override
    public Object postAssistant(PostAssistantDTO postAssistantDTO) {
        String userId = postAssistantDTO.getUserId();
        String resourceType = postAssistantDTO.getResourceType();
        Integer resourceId = postAssistantDTO.getResourceId();

        if (userId == null || resourceType == null || resourceId == null) {
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("success", false);
            errorResult.put("message", "参数不完整");
            return errorResult;
        }

        String resourceTitle = null;
        String resourceContent = null;

        try {
            switch (resourceType) {
                case "extension":
                    ExtensionReading extensionReading = extensionReadingMapper.selectById(resourceId);
                    if (extensionReading != null) {
                        resourceTitle = extensionReading.getText();
                        resourceContent = extensionReading.getBackground();
                    }
                    break;
                case "practice":
                    Practice practice = practiceMapper.selectById(resourceId.longValue());
                    if (practice != null) {
                        resourceTitle = practice.getText();
                        resourceContent = practice.getDescription();
                    }
                    break;
                case "question":
                    PaperPO paper = paperMapper.selectById(resourceId);
                    if (paper != null) {
                        resourceTitle = paper.getPaperName();
                        StringBuilder contentBuilder = new StringBuilder();

                        LambdaQueryWrapper<SingleChoicePO> singleWrap = Wrappers.lambdaQuery();
                        singleWrap.eq(SingleChoicePO::getPaperId, resourceId);
                        List<SingleChoicePO> singleList = singleChoiceMapper.selectList(singleWrap);
                        for (SingleChoicePO sc : singleList) {
                            contentBuilder.append("单选：").append(sc.getQuestion()).append("\n");
                        }

                        LambdaQueryWrapper<MultipleChoicePO> multiWrap = Wrappers.lambdaQuery();
                        multiWrap.eq(MultipleChoicePO::getPaperId, resourceId);
                        List<MultipleChoicePO> multiList = multipleChoiceMapper.selectList(multiWrap);
                        for (MultipleChoicePO mc : multiList) {
                            contentBuilder.append("多选：").append(mc.getQuestion()).append("\n");
                        }

                        LambdaQueryWrapper<JudgePO> judgeWrap = Wrappers.lambdaQuery();
                        judgeWrap.eq(JudgePO::getPaperId, resourceId);
                        List<JudgePO> judgeList = judgeMapper.selectList(judgeWrap);
                        for (JudgePO j : judgeList) {
                            contentBuilder.append("判断：").append(j.getQuestion()).append("\n");
                        }

                        LambdaQueryWrapper<FillBlankPO> blankWrap = Wrappers.lambdaQuery();
                        blankWrap.eq(FillBlankPO::getPaperId, resourceId);
                        List<FillBlankPO> blankList = fillBlankMapper.selectList(blankWrap);
                        for (FillBlankPO fb : blankList) {
                            contentBuilder.append("填空：").append(fb.getQuestion()).append("\n");
                        }

                        LambdaQueryWrapper<ShortAnswerPO> shortWrap = Wrappers.lambdaQuery();
                        shortWrap.eq(ShortAnswerPO::getPaperId, resourceId);
                        List<ShortAnswerPO> shortList = shortAnswerMapper.selectList(shortWrap);
                        for (ShortAnswerPO sa : shortList) {
                            contentBuilder.append("简答：").append(sa.getQuestion()).append("\n");
                        }

                        resourceContent = contentBuilder.toString();
                    }
                    break;
                case "document":
                    Word word = wordMapper.selectById(resourceId);
                    if (word != null) {
                        resourceTitle = word.getText();
                        resourceContent = word.getLongText();
                    }
                    break;
                case "animation":
                    Animation animation = animationMapper.selectById(resourceId.longValue());
                    if (animation != null) {
                        resourceTitle = animation.getText();
                        resourceContent = animation.getHtml();
                    }
                    break;
                case "video":
                    Video video = videoMapper.selectById(resourceId.longValue());
                    if (video != null) {
                        resourceTitle = video.getText();
                        resourceContent = video.getUrl();
                    }
                    break;
                case "ppt":
                    Ppt ppt = pptMapper.selectById(resourceId.longValue());
                    if (ppt != null) {
                        resourceTitle = ppt.getPptTitle();
                        resourceContent = ppt.getOssUrl(); // 使用OSS链接作为内容
                    }
                    break;
                case "mindmap":
                    MindMap mindMap = mindMapMapper.selectById(resourceId);
                    if (mindMap != null) {
                        resourceTitle = mindMap.getText();
                        resourceContent = mindMap.getValue();
                    }
                    break;
                default:
                    Map<String, Object> typeError = new HashMap<>();
                    typeError.put("success", false);
                    typeError.put("message", "暂不支持该资源类型");
                    return typeError;
            }
        } catch (Exception e) {
            log.error("查询资源内容失败", e);
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("success", false);
            errorResult.put("message", "查询资源内容失败");
            return errorResult;
        }

        if (resourceTitle == null || resourceContent == null) {
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("success", false);
            errorResult.put("message", "资源不存在");
            return errorResult;
        }

        try {
            Map<String, Object> pythonParam = new HashMap<>();
            pythonParam.put("user_id", userId);
            pythonParam.put("resource_type", resourceType);
            pythonParam.put("resource_title", resourceTitle);
            pythonParam.put("resource_content", resourceContent);

            return pythonRestClient.post("/community/post/preview", pythonParam);
        } catch (Exception e) {
            log.error("调用Python端发帖助手接口失败", e);
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("success", false);
            errorResult.put("message", "生成帖子内容失败");
            return errorResult;
        }
    }

    /**
     * 发帖助手(将用户修改好的帖子发布到社区)
     * @param postAssistantSubmitDTO
     * @return
     */
    @Override
    public Object submitPostAssistant(PostAssistantSubmitDTO postAssistantSubmitDTO) {
        try {
            return pythonRestClient.post("/community/post/publish", postAssistantSubmitDTO);
        } catch (Exception e) {
            log.error("调用Python端发帖助手发布接口失败", e);
            Map<String, Object> errorResult = new HashMap<>();
            errorResult.put("success", false);
            errorResult.put("message", "发布帖子失败");
            return errorResult;
        }
    }
}
