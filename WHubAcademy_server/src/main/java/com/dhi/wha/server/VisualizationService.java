package com.dhi.wha.server;

import com.baomidou.mybatisplus.extension.service.IService;
import com.dhi.wha.dto.VisualizationDTO;
import com.dhi.wha.entity.Visualization;

public interface VisualizationService extends IService<Visualization> {
    /**
     * 获取可视化信息
     * @param visualizationDTO
     * @return
     */
    Visualization getVisualization(VisualizationDTO visualizationDTO);
}
