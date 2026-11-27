package com.dhi.wha.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.dhi.wha.entity.Visualization;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface VisualizationMapper extends BaseMapper<Visualization> {

    /**
     * 根据历史记录id查询对应的可视化
     * @param historyId
     * @return
     */
    @Select("SELECT * FROM visualization WHERE history_id = #{historyId}")
    Visualization getVisualization(Long historyId);
}
