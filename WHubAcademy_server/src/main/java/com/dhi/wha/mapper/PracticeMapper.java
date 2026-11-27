package com.dhi.wha.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.dhi.wha.entity.Practice;
import com.dhi.wha.vo.ChatResourceVO;
import com.dhi.wha.vo.PracticeVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface PracticeMapper extends BaseMapper<Practice> {

    /**
     * 查询用户对应的所有的编程练习题列表
     * @param userId
     * @return
     */
    @Select("select id,user_id,text,status,create_time from practice where user_id = #{userId} order by create_time desc")
    List<PracticeVO> getPracticeList(Long userId);

    /**
     * 获取编程练习题的题目id
     * @param practiceId
     * @return
     */
    @Select("select problem_id from practice where id = #{practiceId}")
    String getProblemId(Long practiceId);

    /**
     * 根据ID查询编程练习题（包含所有字段）
     * @param id
     * @return
     */
    Practice selectPracticeWithDetails(Long id);


    Practice getById(Long practiceId);

    /**
     * 根据题目ID查询编程练习题（包含所有字段）
     * @param resourceId
     * @return
     */
    Practice getByProblemId(String resourceId);

    /**
     * 根据任务ID查询编程练习题（包含所有字段）
     * @param taskId
     * @return
     */
    @Select("select id,status,text,create_time,suggestion_warning from practice where id = #{taskId}")
    ChatResourceVO getPracticeInfoById(Integer taskId);

    @Select("select title from practice where id = #{l}")
    String getTitleById(long l);

    @Select("select suggestion_warning from practice where id = #{practiceId}")
    String getSuggestionWarningById(Long practiceId);
}
