package com.dhi.wha.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.dhi.wha.entity.RadarChart;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface RadarChartMapper extends BaseMapper<RadarChart> {
    /**
     * 根据雷达图id查询对应的雷达图
     * @param radarMapId
     * @return
     */
    RadarChart selectByRadarMapId(Long radarMapId);
}
