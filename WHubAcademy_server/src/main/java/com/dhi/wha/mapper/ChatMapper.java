package com.dhi.wha.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.dhi.wha.entity.Chat;
import com.dhi.wha.vo.ChatResourceVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.util.List;
import java.util.Map;

@Mapper
public interface ChatMapper extends BaseMapper<Chat> {
    void updateStatusByTaskIdAndUserIdAndRsType(@Param("status") Integer status, @Param("taskId") String taskId, @Param("rsType") Integer rsType, @Param("userId") Integer userId, @Param("resource") Map<String,Object> resource, @Param("content") String content);


    Long getTextByUserIdAndRsTypeAndTaskId(
            @Param("userId") Integer userId,
            @Param("rsType") Integer rsType,
            @Param("taskId") String taskId
    );
    List<Chat> selectChatByUserId(@Param("userId") Long userId,
                                  @Param("lastId") Long lastId,
                                  @Param("pageSize") Integer pageSize);

    @Select("select content as text from chat where id = #{l}")
    String getTextByAIId(long l);

    @Select("select id from chat where user_id = #{userId} and rs_type = #{rsType} and status = #{status} limit 1")
    Long getChatId(Integer userId, Integer rsType, Integer status);

    @Select("select create_time from chat where id = #{chatId}")
    String getCreateTime(Long chatId);
}