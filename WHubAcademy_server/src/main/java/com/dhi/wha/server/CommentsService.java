package com.dhi.wha.server;

import com.dhi.wha.dto.CommentDTO;
import com.dhi.wha.dto.CommentPostDTO;
import com.dhi.wha.dto.PostAssistantDTO;
import com.dhi.wha.dto.PostAssistantSubmitDTO;

public interface CommentsService {
    /**
     * 获取评论列表
     * @param page
     * @param pageSize
     * @param zone
     * @return
     */
    Object getCommentsList(Integer page, Integer pageSize, Integer zone);

    /**
     * 获取指定评论
     * @param postId
     * @return
     */
    Object getCommentsById(String postId);

    /**
     * 回复评论
     * @param commentDTO
     * @return
     */
    Object replyPost(CommentDTO commentDTO);

    /**
     * 删除回复
     * @param userId
     * @param replyId
     * @return
     */
    Object deleteReply(String userId, String replyId);

    /**
     * 删除帖子
     * @param postId
     * @param userId
     * @return
     */
    Object deletePost(String postId, String userId);

    /**
     * 提交帖子
     * @param param
     * @return
     */
    Object submitPost(CommentPostDTO param);

    /**
     * AI生成帖子内容(发帖助手)
     * @param postAssistantDTO
     * @return
     */
    Object postAssistant(PostAssistantDTO postAssistantDTO);

    /**
     * 发帖助手(将用户修改好的帖子发布到社区)
     * @param postAssistantSubmitDTO
     * @return
     */
    Object submitPostAssistant(PostAssistantSubmitDTO postAssistantSubmitDTO);
}
