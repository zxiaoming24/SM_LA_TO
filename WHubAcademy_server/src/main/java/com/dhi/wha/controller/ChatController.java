package com.dhi.wha.controller;

import com.dhi.wha.constant.ClickRecord;
import com.dhi.wha.dto.ChatContextDTO;
import com.dhi.wha.dto.ChatDTO;
import com.dhi.wha.dto.ChatQueryDTO;
import com.dhi.wha.dto.ConflictDTO;
import com.dhi.wha.entity.Chat;
import com.dhi.wha.mapper.ChatMapper;
import com.dhi.wha.result.Result;
import com.dhi.wha.server.ChatService;
import com.dhi.wha.vo.PlanVO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/aiAnswer")
public class ChatController {

    @Autowired
    private ChatService chatService;


    /**
     * 获取AI的答案
     * @param chatDTO
     * @return
     */
    @ClickRecord(resourceType = "AI_ANSWER", resourceIdParam = "")
    @PostMapping("/submit")
    public Result<Object> getAIAnswer(@RequestBody ChatDTO chatDTO){
        try{
            log.info("获取AI的答案");
            Map<String,Object> respMap = chatService.getAIAnswer(chatDTO);
            return Result.success(respMap);
        }catch (Exception e){
            return Result.error(e.getMessage());
        }
    }


    /**
     * 查询指定任务进度
     * @param userId
     * @param rsType
     * @param taskId
     * @return
     */
    @GetMapping("/getProgress/{userId}/{rsType}/{taskId}")
    public Result<Object> getProgress(
            @PathVariable Integer userId,
            @PathVariable Integer rsType,
            @PathVariable String taskId
    ){
        log.info("查询指定任务进度");
        Map<String,Object> statusInfo = chatService.getResourceDispatcher(userId,rsType,taskId);
        return Result.success(statusInfo);
    }


    /**
     * 重新生成资源
     * @param userId
     * @param rsType
     * @param taskId
     * @return
     */
    @GetMapping("/reCreate/{userId}/{rsType}/{taskId}")
    public Result<Object> reCreateResource(
            @PathVariable Integer userId,
            @PathVariable Integer rsType,
            @PathVariable String taskId
    ){
        log.info("重新生成资源");
        Map<String,Object> statusInfo = chatService.refetchResourceDispatcher(userId,rsType,taskId);
        return Result.success(statusInfo);
    }

    /**
     * 获取聊天历史记录
     * @param userId 用户ID
     * @param lastId 游标id，传0代表首次加载无游标
     * @param queryDTO 查询条件
     * @return 聊天列表
     */
    @GetMapping("/queryHistoryRecords/{userId}/{lastId}")
    public Result<List<Chat>> getChatHistory(
            @PathVariable Long userId,
            @PathVariable Long lastId,
            ChatQueryDTO queryDTO
    ){
        log.info("获取聊天历史记录 userId:{}, pathLastId:{}", userId, lastId);
        queryDTO.setUserId(userId);
        // 路径传0则置为null，否则赋值
        queryDTO.setLastId(lastId.equals(0L) ? null : lastId);
        List<Chat> chatList = chatService.selectChatByUserId(queryDTO);
        return Result.success(chatList);
    }

    /**
     * 悬浮球对话接口
     * @param chatContextDTO 对话请求参数
     * @return 对话结果
     */
    @PostMapping("/chat/context")
    public Result<Object> chatWithContext(@RequestBody ChatContextDTO chatContextDTO){
        log.info("悬浮球对话, userId: {}", chatContextDTO.getUser_id());
        return Result.success(chatService.chatWithContext(chatContextDTO));
    }

    /**
     * 选择学习方案
     * @param request 请求参数（user_id, plan_id, plan_name）
     * @return 学习方案详情
     */
    @PostMapping("/plan")
    public Result<Object> selectPlan(@RequestBody Map<String, Object> request){
        log.info("选择学习方案, request: {}", request);
        Map<String, Object> result = chatService.selectPlan(request);
        return Result.success(result);
    }

    /**
     * 获取方案（当前选择的方案和方案列表）
     * @param userId 用户ID
     * @return 方案信息
     */
    @GetMapping("/plan/{userId}")
    public Result<PlanVO> getPlanByUserId(@PathVariable Long userId){
        log.info("获取学习方案, userId: {}", userId);
        PlanVO planVO = chatService.getPlanByUserId(userId);
        return Result.success(planVO);
    }

    /**
     * 发送问候（主动提醒）
     * @param userId 用户ID
     * @return 问候信息
     */
    @GetMapping("/sendGreetings/{userId}")
    public Result<Object> sendGreetings(@PathVariable Long userId){
        log.info("发送问候（主动提醒）, userId: {}", userId);
        Map<String, Object> result = chatService.sendGreetings(userId);
        return Result.success(result);
    }

    /**
     * 弹窗之后的编程题生成（冲突解决）
     * @param userId 用户ID
     * @param conflictDTO 冲突解决请求
     * @return 成功响应
     */
    @PostMapping("/conflict/{userId}")
    public Result<Object> handleConflict(@PathVariable Long userId, @RequestBody ConflictDTO conflictDTO){
        log.info("弹窗之后的编程题生成, userId: {}, conflictDTO: {}", userId, conflictDTO);
        chatService.handleConflict(userId, conflictDTO);
        return Result.success();
    }
    

}
