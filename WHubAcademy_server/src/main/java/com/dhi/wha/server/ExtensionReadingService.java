package com.dhi.wha.server;


import com.baomidou.mybatisplus.extension.service.IService;
import com.dhi.wha.dto.ChatDTO;
import com.dhi.wha.dto.ExtensionReadingDTO;
import com.dhi.wha.entity.ExtensionReading;
import com.dhi.wha.vo.ChatResourceVO;
import com.dhi.wha.vo.ExtensionReadingVO;

import java.util.List;
import java.util.Map;

public interface ExtensionReadingService extends IService<ExtensionReading> {

    /**
     * 提交生成任务
     * @param request
     * @return
     */
    Map<String, Object> submitGenerateTask(ExtensionReadingDTO request);

    /**
     * 获取任务状态
     * @param id
     * @return
     */
    Map<String, Object> getStatus(String id);

    /**
     * 获取用户所有拓展阅读
     * @param userId
     * @return
     */
    List<ExtensionReadingVO> getExtensionReadingList(Long userId);

    /**
     * 保存拓展阅读
     * @param chatDTO
     * @return
     */
    Long saveExtension(ChatDTO chatDTO);

    /**
     * 根据任务id获取拓展阅读信息
     * @param taskId
     * @return
     */
    ChatResourceVO getExtensionInfoById(Integer taskId);
}
