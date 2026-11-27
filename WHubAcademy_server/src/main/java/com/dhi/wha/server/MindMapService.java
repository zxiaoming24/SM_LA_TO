package com.dhi.wha.server;

import com.dhi.wha.dto.ChatDTO;
import com.dhi.wha.dto.MindMapInsertDTO;
import com.dhi.wha.entity.MindMap;
import com.dhi.wha.vo.ChatResourceVO;
import com.dhi.wha.vo.MindMapVO;

import java.util.List;
import java.util.Map;

public interface MindMapService {
    /**
     * 提交思维导图生成任务
     * @param request 请求参数
     * @return 任务信息
     */
    Map<String, Object> submitGenerateTask(MindMapInsertDTO request);
    /**
     * 获取思维导图生成状态
     * @param taskId 任务ID
     * @return 状态信息
     */
    Map<String, Object> getStatus(Long taskId);

    /**
     * 获取用户思维导图列表
     * @param userId 用户ID
     * @return 思维导图列表
     */
    List<MindMapVO> getMindMapList(Long userId);

    /**
     * 根据ID获取思维导图
     * @param mindMapId 思维导图ID
     * @return 思维导图
     */
    MindMap getById(String mindMapId);

    /**
     * 删除思维导图
     * @param mindMapId 思维导图ID
     */
    void deleteMindMapById(Long mindMapId);

    /**
     * 获取思维导图上/下页数据 operation: 0-上页 1-下页
     * @param mindMapId 思维导图ID
     * @param userId 用户ID
     * @param operation 操作类型
     * @return 思维导图分页数据
     */
    MindMap getMindMapPage(Long mindMapId, Long userId, Long operation);

    /**
     * 保存思维导图
     * @param chatDTO 聊天数据
     * @return 思维导图ID
     */
    Long saveMindMap(ChatDTO chatDTO);

    /**
     * 根据任务ID获取思维导图信息
     * @param taskId 任务ID
     * @return 思维导图信息
     */
    ChatResourceVO getMindMapInfoById(Integer taskId);
}
