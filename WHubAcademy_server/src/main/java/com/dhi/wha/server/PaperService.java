package com.dhi.wha.server;

import com.baomidou.mybatisplus.extension.service.IService;
import com.dhi.wha.dto.ChatDTO;
import com.dhi.wha.dto.PaperDTO;
import com.dhi.wha.dto.QuestionSubmitDTO;
import com.dhi.wha.entity.PaperPO;
import com.dhi.wha.result.Result;
import com.dhi.wha.vo.ChatResourceVO;

import java.util.List;
import java.util.Map;

public interface PaperService extends IService<PaperPO> {

    /**
     * 生成试卷
     * @param paperDTO
     * @return
     */
    Map<String, Object> generatePaper(PaperDTO paperDTO);

    /**
     * 获取指定试卷
     * @param id 可以是Java端数字ID或Python端resourceId
     * @return
     */
    Map<String, Object> getPaperInfoById(String id);

    /**
     * 删除指定试卷
     * @param id
     * @return
     */
    void deletePaper(Integer id);

    /**
     * 获取指定用户所有试卷
     * @param userId
     * @return
     */
    List<PaperPO> getPaperById(Long userId);

    /**
     * 保存理论题id
     * @param chatDTO
     * @return
     */
    Long saveTheoryId(ChatDTO chatDTO);

    /**
     * 获取指定用户指定任务id的试卷信息
     * @param taskId
     */
    ChatResourceVO getPaperInfoByUserIdAndTaskId(Integer taskId);

    /**
     * 提交试卷
     */
    Object submitPaper(QuestionSubmitDTO questionSubmitDTO);
}
