package com.dhi.wha.server;

import com.baomidou.mybatisplus.extension.service.IService;
import com.dhi.wha.dto.CompareDTO;
import com.dhi.wha.dto.PracticeAnswerDTO;
import com.dhi.wha.entity.PracticeAnswer;
import com.dhi.wha.vo.PracticeAnswerListVO;
import com.dhi.wha.vo.PracticeAnswerVO;
import com.dhi.wha.vo.PracticeVO;

import java.util.List;
import java.util.Map;

public interface PracticeAnswerService extends IService<PracticeAnswer> {

    /**
     * 获取编程练习题的答案
     * @param request
     * @return
     */
    Map<String, Object> getPracticeAnswer(PracticeAnswerDTO request);

    /**
     * 获取指定的编程练习题
     * @param id
     * @return
     */
    PracticeAnswerVO getPracticeAnswerById(Long id);

    /**
     * 获取对应编程题的答案列表
     * @param practiceId
     * @return
     */
    List<PracticeAnswerListVO> getPracticeAnswerList(Long practiceId, Long userId);

    /**
     * 删除对应的编程题
     * @param id
     */
    void deletePracticeAnswerById(Long id);

    /**
     * 比较分析两个人的编程题
     * @param compareDTO 比较请求参数
     * @return 比较结果数据
     */
    List<Object> comparePracticeAnswers(CompareDTO compareDTO);
}
