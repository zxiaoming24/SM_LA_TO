package com.dhi.wha.server.Impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.dhi.wha.dto.VisualizationDTO;
import com.dhi.wha.entity.Visualization;
import com.dhi.wha.entity.ranking;
import com.dhi.wha.mapper.VisualizationMapper;
import com.dhi.wha.server.VisualizationService;
import com.dhi.wha.utils.PythonRestClient;
import com.dhi.wha.vo.RankingVO;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class VisualizationServiceImpl extends ServiceImpl<VisualizationMapper, Visualization>
        implements VisualizationService {

    @Autowired
    private VisualizationMapper  visualizationMapper;

    @Autowired
    private PythonRestClient pythonRestClient;


    /**
     * 获取可视化代码
     * @param visualizationDTO
     * @return
     */
    @Override
    public Visualization getVisualization(VisualizationDTO visualizationDTO) {
        // 1.根据历史id查询可视化代码是否存在
        Visualization visualization = visualizationMapper.getVisualization(visualizationDTO.getHistoryId());
        if (visualization != null) {
            return visualization;
        }

        //2. 不存在就插入数据
        Visualization newVisualization = new Visualization();
        newVisualization.setHistoryId(visualizationDTO.getHistoryId());

        //3.请求python端
        try {
            Map<String, Object> pythonParam = new HashMap<>();
            pythonParam.put("code", visualizationDTO.getCode());
            pythonParam.put("language", visualizationDTO.getLanguage());
            pythonParam.put("algorithm_type", visualizationDTO.getAlgorithmType());
            Object pythonRes = pythonRestClient.post("/api/visualize/transform", pythonParam);

            Map<String, Object> resultMap = (Map<String, Object>) pythonRes;

            // 逐个取出字段
            String code = (String) resultMap.get("code");
            String detectedType = (String) resultMap.get("detectedType");
            String language = (String) resultMap.get("language");
            String originalCode = (String) resultMap.get("originalCode");

            // 4.插入数据
            newVisualization.setCode(code);
            newVisualization.setDetectedType(detectedType);
            newVisualization.setLanguage(language);
            newVisualization.setOriginalCode(originalCode);
            visualizationMapper.insert(newVisualization);

        } catch (Exception e) {
            e.printStackTrace();
            return null;
        }
        return newVisualization;
    }
}
