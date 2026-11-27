package com.dhi.wha.server;

import com.baomidou.mybatisplus.extension.service.IService;
import com.dhi.wha.dto.ChatContextDTO;
import com.dhi.wha.dto.ChatDTO;
import com.dhi.wha.dto.ChatQueryDTO;
import com.dhi.wha.dto.ConflictDTO;
import com.dhi.wha.entity.Chat;
import com.dhi.wha.vo.PlanVO;

import java.util.List;
import java.util.Map;

public interface ChatService extends IService<Chat> {
    /**
     * 获取AI的答案
     * @param chatDTO 请求参数
     * @return 响应结果
     */
    Map<String, Object> getAIAnswer(ChatDTO chatDTO);

    /**
     * 前端轮询的接口
     * @param userId
     * @param rsType
     * @param taskId
     * @return
     */
    Map<String, Object> getResourceDispatcher(Integer userId, Integer rsType, String taskId);

    /**
     * 重新获取资源
     * @param userId
     * @param rsType
     * @param taskId
     * @return
     */
    Map<String, Object> refetchResourceDispatcher(Integer userId, Integer rsType, String taskId);

    List<Chat> selectChatByUserId(ChatQueryDTO chatQueryDTO);

    /**
     * 悬浮球对话接口
     * @param chatContextDTO 对话请求参数
     * @return 对话结果
     */
    Object chatWithContext(ChatContextDTO chatContextDTO);

    /**
     * 选择学习方案
     * @param request 请求参数（user_id, plan_id, plan_name）
     * @return 学习方案详情
     */
    Map<String, Object> selectPlan(Map<String, Object> request);

    /**
     * 获取方案（当前选择的方案和方案列表）
     * @param userId 用户ID
     * @return 方案信息
     */
    PlanVO getPlanByUserId(Long userId);

    /**
     * 发送问候（主动提醒）
     * @param userId 用户ID
     * @return 问候信息
     */
    Map<String, Object> sendGreetings(Long userId);

    /**
     * 弹窗后的编程题生成（冲突解决）
     * @param userId 用户ID
     * @param conflictDTO 冲突解决请求
     */
    void handleConflict(Long userId, ConflictDTO conflictDTO);

    String getCreateTime(Integer userId, Integer rsType, Integer status);
}
