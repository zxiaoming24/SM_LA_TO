package com.dhi.wha.server;

import com.dhi.wha.dto.ChatDTO;
import com.dhi.wha.dto.WordDTO;
import com.dhi.wha.entity.Word;
import com.dhi.wha.vo.ChatResourceVO;

import java.util.List;
import java.util.Map;

public interface WordService {

    /**
     * 提交生成讲解文档
     * @param request
     * @return
     */
    Map<String, Object> submitTask(WordDTO request);

    /**
     * 获取文档的生成状态
     * @param id
     * @return
     */
    Map<String, Object> getStatus(String id);

    /**
     * 获取对应用户的列表
     * @param userId
     * @return
     */
    List<Word> getByUserId(Long userId);

    /**
     * 根据id删除对应的word文档
     * @param id
     */
    void deleteWordById(Long id);

    /**
     * 添加文档
     * @param chatDTO
     * @return
     */
    Long saveWord(ChatDTO chatDTO);

    /**
     * 根据id查询对应的word文档
     * @param taskId
     * @return
     */
    ChatResourceVO getWordInfoById(Integer taskId);
}
