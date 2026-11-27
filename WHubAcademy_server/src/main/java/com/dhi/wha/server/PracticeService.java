package com.dhi.wha.server;

import com.baomidou.mybatisplus.extension.service.IService;
import com.dhi.wha.dto.ChatDTO;
import com.dhi.wha.dto.PracticeDTO;
import com.dhi.wha.entity.Practice;
import com.dhi.wha.vo.ChatResourceVO;
import com.dhi.wha.vo.PracticeVO;

import java.util.List;
import java.util.Map;

public interface PracticeService extends IService<Practice> {
    /**
     * 提交任务
     * @param request
     * @return
     */
    Map<String, Object> submitGenerateTask(PracticeDTO request);


    /**
     * 获取对应用户的列表（编程练习题的）
     * @param userId
     * @return
     */
    List<PracticeVO> getPracticeList(Long userId);

    /**
     * 获取指定的编程练习题
     */
    Practice getPracticeById(Long id);

    /**
     * 删除指定的编程练习题
     */
    void deletePracticeById(Long id);

    /**
     * 保存指定的编程练习题
     */
    Long savePractice(ChatDTO chatDTO);

    /**
     * 获取指定的编程练习题
     */
    Practice getPractice(String id);

    /**
     * 获取指定的编程练习题
     */
    ChatResourceVO getPracticeInfoById(Integer taskId);

    /**
     * 获取指定的编程练习题
     */
    String getSuggestionWarningById(Long practiceId);
}
