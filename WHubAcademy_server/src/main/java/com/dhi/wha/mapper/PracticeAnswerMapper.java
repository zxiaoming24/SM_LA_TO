package com.dhi.wha.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.dhi.wha.entity.PracticeAnswer;
import com.dhi.wha.vo.PracticeAnswerListVO;
import com.dhi.wha.vo.PracticeAnswerVO;
import com.dhi.wha.vo.PracticeVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface PracticeAnswerMapper extends BaseMapper<PracticeAnswer> {

    /**
     * 根据id查询对应的编程练习题
     * @param id
     * @return
     */
    PracticeAnswerVO getPracticeAnswerById(Long id);

    /**
     * 根据id查询对应的编程练习题的答案列表
     * @param practiceId
     * @return
     */
    List<PracticeAnswerListVO> getPracticeAnswerList(Long practiceId, Long userId);
}
