package com.dhi.wha.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.dhi.wha.entity.Word;
import com.dhi.wha.vo.ChatResourceVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface WordMapper extends BaseMapper<Word> {
    /**
     * 根据用户ID查询用户所生成的所有思维导图
     * @param userId
     * @return
     */
    @Select("SELECT * FROM word WHERE user_id = #{userId} order by create_time desc")
    List<Word> getWordListByUserId(Long userId);

    /**
     * 根据资源ID查询word
     * @param id
     * @return
     */
    @Select("SELECT * FROM word WHERE resource_id = #{id} LIMIT 1")
    Word selectByResourceId(String id);

    /**
     * 根据标题查询文档
     * @param text 标题
     * @return 文档
     */
    @Select("SELECT * FROM word WHERE text = #{text} limit 1")
    Word getByText(String text);

    /**
     * 根据OSS URL查询文档
     * @param ossUrl OSS URL
     * @return 文档
     */
    @Select("SELECT * FROM word WHERE oss_url = #{ossUrl} limit 1")
    Word getByOssUrl(String ossUrl);

    /**
     * 根据任务ID查询思维导图信息
     * @param taskId
     * @return
     */
    @Select("SELECT id,status,text,create_time FROM word WHERE id = #{taskId}")
    ChatResourceVO getWordInfoById(Integer taskId);

    /**
     * 根据ID获取resourceId
     * @param id
     * @return resourceId
     */
    @Select("SELECT resource_id FROM word WHERE id = #{id}")
    String getResourceIdById(Integer id);

    /**
     * 根据ID获取标题
     * @param
     * @return 标题
     */
    @Select("SELECT text from word where id = #{l}")
    String getTitleById(long l);
}
