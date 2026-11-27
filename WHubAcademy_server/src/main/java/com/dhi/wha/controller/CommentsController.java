package com.dhi.wha.controller;

import com.dhi.wha.constant.ClickRecord;
import com.dhi.wha.dto.CommentDTO;
import com.dhi.wha.dto.CommentPostDTO;
import com.dhi.wha.dto.PostAssistantDTO;
import com.dhi.wha.dto.PostAssistantSubmitDTO;
import com.dhi.wha.result.Result;
import com.dhi.wha.server.CommentsService;
import com.dhi.wha.server.LoginService;
import com.dhi.wha.vo.UserCommentVO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/comment")
public class CommentsController {

    @Autowired
    private CommentsService commentsService;

    @Autowired
    private LoginService userService;


    /**
     * 获取评论列表
     * 前端调用：/comment/getPostsList/{page}/{pageSize}/{zone}
     */
    @GetMapping("/getPostsList/{page}/{pageSize}/{zone}")
    public Result<Object> getCommentsList
            (@PathVariable Integer page,
             @PathVariable Integer pageSize,
             @PathVariable Integer zone){
        log.info("获取评论列表");
        return Result.success(commentsService.getCommentsList(page, pageSize, zone));
    }


    /**
     * 获取帖子详情
     * 前端调用：/comment/getPost/{postId}
     */
    @ClickRecord(resourceType = "POST", resourceIdParam = "")
    @GetMapping("/getPost/{postId}")
    public Result<Object> getCommentsById(@PathVariable String postId){
        log.info("获取帖子详情");
        return Result.success(commentsService.getCommentsById(postId));
    }


    /**
     * 获取用户列表
     * 前端调用：/comment/user/list
     */
    @PostMapping("/getNameData")
    public Result getUserList(@RequestBody Map<String, List<String>> param){
        //前端入参 {userIdList:[2,3,4,5]}
        List<String> userIdList = param.get("userIdList");
        List<UserCommentVO> userList = userService.getUserByUserIdList(userIdList);
        return Result.success(userList);
    }

    /**
     * 回复帖子
     * 前端调用：/comment/replyPost
     */
    @ClickRecord(resourceType = "POST", resourceIdParam = "")
    @PostMapping("/replyPost")
    public Result<Object> replyPost(@RequestBody CommentDTO commentDTO){
        log.info("回复帖子");
        return Result.success(commentsService.replyPost(commentDTO));
    }


    /**
     * 删除回复
     * 前端调用：/comment/deleteReply/{userId}/{replyId}
     */
    @DeleteMapping("/deleteReply/{userId}/{replyId}")
    public Result<Object> deleteReply
            (@PathVariable String userId, @PathVariable String replyId)
    {
        log.info("删除回复");
        return Result.success(commentsService.deleteReply(userId,replyId));
    }


    /**
     * 删除帖子
     * 前端调用：/comment/deletePost/{postId}/{userId}
     */
    @DeleteMapping("/deletePost/{userId}/{postId}")
    public Result<Object> deletePost
            (@PathVariable String postId, @PathVariable String userId)
    {
        log.info("删除帖子");
        return Result.success(commentsService.deletePost(postId, userId));
    }

    /**
     * 提交帖子
     * 前端调用：/comment/submitPost
     */
    @ClickRecord(resourceType = "POST", resourceIdParam = "")
    @PostMapping("/submitPost")
    public Result<Object> submitPost(@RequestBody CommentPostDTO param){
        log.info("提交帖子");
        return Result.success(commentsService.submitPost(param));
    }

    /**
     * AI生成帖子内容(发帖助手)
     * 前端调用：/comment/postAssistant
     */
    @PostMapping("/postAssistant")
    public Result<Object> postAssistant(@RequestBody PostAssistantDTO postAssistantDTO){
        log.info("AI生成帖子内容(发帖助手)");
        return Result.success(commentsService.postAssistant(postAssistantDTO));
    }

    /**
     * 发帖助手(将用户修改好的帖子发布到社区)
     * 前端调用：/comment/postAssistant/submitPost
     */
    @ClickRecord(resourceType = "POST", resourceIdParam = "")
    @PostMapping("/postAssistant/submitPost")
    public Result<Object> submitPostAssistant(@RequestBody PostAssistantSubmitDTO postAssistantSubmitDTO){
        log.info("发帖助手(将用户修改好的帖子发布到社区)");
        return Result.success(commentsService.submitPostAssistant(postAssistantSubmitDTO));
    }
}
