package com.dhi.wha.server;


import com.alibaba.fastjson.JSONObject;
import com.dhi.wha.dto.ChatDTO;
import com.dhi.wha.dto.PptDTO;
import com.dhi.wha.entity.Ppt;
import com.dhi.wha.vo.ChatResourceVO;

import java.util.List;
import java.util.Map;

public interface PptService  {

    /**
     * 创建PPT任务，异步调用Python /chat接口
     * @param pptDTO
     * @return
     */
    Map<String, Object> createPPT(PptDTO pptDTO,String userId);

    /**
     * 查询PPT进度，从数据库获取
     * @param taskId
     * @return
     */
    Map<String, Object> getProgress(String taskId);

    /**
     * 插入用户id和任务id（保留兼容）
     * @param userId
     * @param id
     */
    void insertUserIdAndTaskId(Long userId, String id);

    /**
     * 获取PPT结果（保留兼容）
     * @param id
     * @return
     */
    JSONObject getPptResultWithOss(String id);

    /**
     * 获取下载地址
     * @param id
     * @param type
     * @return
     */
    JSONObject getDownload(String id, String type) throws Exception;

    /**
     * 获取用户id和任务id
     * @return
     */
    List<Ppt> getByUserId(Long userId);

    /**
     * 删除用户id和任务id
     * @param pptId
     */
    void deleteTable(Long pptId);

    /**
     * 保存PPT
     * @param chatDTO
     * @return
     */
    Long savePpt(ChatDTO chatDTO);

    /**
     * 获取PPT信息
     * @param taskId
     * @return
     */
    ChatResourceVO getPptInfoById(Integer taskId);
}
