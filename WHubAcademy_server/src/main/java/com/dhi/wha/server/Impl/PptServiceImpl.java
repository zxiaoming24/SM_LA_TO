package com.dhi.wha.server.Impl;

import com.alibaba.fastjson.JSONObject;
import com.dhi.wha.constant.PptStatusConstant;
import com.dhi.wha.dto.ChatDTO;
import com.dhi.wha.dto.PptDTO;
import com.dhi.wha.entity.Ppt;
import com.dhi.wha.mapper.PptMapper;
import com.dhi.wha.server.PptService;
import com.dhi.wha.server.SseConnectionService;
import com.dhi.wha.utils.AliOssUtil;
import com.dhi.wha.utils.AsyncUtil;
import com.dhi.wha.utils.PythonSseClient;
import com.dhi.wha.vo.ChatResourceVO;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.apache.poi.xslf.usermodel.XMLSlideShow;
import org.apache.poi.xslf.usermodel.XSLFSlide;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.URL;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Slf4j
@Service
public class PptServiceImpl implements PptService {

    @Autowired
    private PptMapper pptMapper;

    @Autowired
    private PythonSseClient pythonSseClient;

    @Autowired
    private SseConnectionService sseConnectionService;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private AliOssUtil aliOssUtil;

    /**
     * 创建PPT任务，异步调用Python /chat接口
     * @param pptDTO
     * @return
     */
    @Override
    public Map<String, Object> createPPT(PptDTO pptDTO,String userId) {
        Long userId1 = safeToLong(userId,null);
        String userIdStr = userId;

        // 1. 创建数据库记录（生成中状态）
        Ppt ppt = Ppt.builder()
                .userId(userId1)
                .pptTitle(pptDTO.getText())
                .status(PptStatusConstant.PPT_STATUS_GENERATING)
                .createdAt(String.valueOf(LocalDateTime.now()))
                .build();
        pptMapper.insert(ppt);

        // 2. 检查是否有SSE连接
        boolean hasSseConnection = sseConnectionService.isConnected(userIdStr);

        // 3. 异步调用Python /chat接口
        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("user_id", userIdStr);
        requestBody.put("user_input", "帮我生成关于" + pptDTO.getText() + "的PPT");

        AsyncUtil.execute(() -> {
            try {
                pythonSseClient.consumePostSse("/chat", requestBody, jsonData -> {
                    log.info("PPT SSE事件数据: {}", jsonData.length() > 500 ? jsonData.substring(0, 500) + "..." : jsonData);
                    
                    // 如果有SSE连接，转发给前端
                    if (hasSseConnection) {
                        sseConnectionService.sendMessage(userIdStr, "ppt_stream", jsonData);
                    }

                    // 监听 task_result 事件，保存到数据库
                    try {
                        JsonNode root = objectMapper.readTree(jsonData);
                        String eventType = root.path("type").asText("");
                        log.info("PPT SSE事件类型: {}", eventType);
                        
                        if ("task_result".equals(eventType)) {
                            JsonNode resultNode = root.path("result");
                            log.info("PPT task_result result节点是否存在: {}, ppt节点是否存在: {}", 
                                    !resultNode.isMissingNode(), 
                                    !resultNode.isMissingNode() && !resultNode.path("ppt").isMissingNode());
                            
                            if (!resultNode.isMissingNode()) {
                                savePptResultFromJson(ppt.getId(), resultNode);
                            }
                        }
                    } catch (Exception e) {
                        log.error("处理PPT SSE事件失败", e);
                    }
                });
            } catch (Exception e) {
                log.error("SSE流式调用Python失败", e);
                Ppt failBean = Ppt.builder()
                        .id(ppt.getId())
                        .status(PptStatusConstant.PPT_STATUS_FAILED)
                        .build();
                pptMapper.updateById(failBean);
            }
        });

        // 4. 返回任务ID和状态
        Map<String, Object> result = new HashMap<>();
        result.put("id", ppt.getId());
        result.put("status", PptStatusConstant.PPT_STATUS_GENERATING);
        return result;
    }

    /**
     * 从task_result事件中保存PPT结果到数据库
     */
    private void savePptResultFromJson(Long pptId, JsonNode resultNode) {
        log.info("savePptResultFromJson 被调用, pptId={}", pptId);
        
        JsonNode pptNode = resultNode.path("ppt");
        log.info("pptNode 是否存在: {}", !pptNode.isMissingNode());
        
        if (!pptNode.isMissingNode()) {
            String status = pptNode.path("status").asText("");
            log.info("ppt status: {}", status);
            
            Ppt ppt = new Ppt();
            ppt.setId(pptId);

            if ("success".equals(status)) {
                ppt.setStatus(PptStatusConstant.PPT_STATUS_GENERATED);
                ppt.setPageCount(pptNode.path("pages").asInt());
                ppt.setTaskId(pptNode.path("topic").asText());
                ppt.setPptTitle(ppt.getPptTitle()); // 同时更新pptTitle字段
                ppt.setOssUrl(pptNode.path("oss_url").asText());
                ppt.setResourceId(pptNode.path("resource_id").asText());
                
                log.info("PPT数据: pages={}, taskId={}, ossUrl={}, resourceId={}", 
                        ppt.getPageCount(), ppt.getTaskId(), ppt.getOssUrl(), ppt.getResourceId());

                // 异步将PPT第一张幻灯片转换为图片并上传OSS，避免阻塞SSE事件处理
                String ossUrl = ppt.getOssUrl();
                if (ossUrl != null && !ossUrl.isEmpty()) {
                    AsyncUtil.execute(() -> {
                        try {
                            String firstImageOssUrl = convertFirstSlideToImage(ossUrl, pptId.toString());
                            // 更新数据库中的图片URL
                            Ppt updatePpt = new Ppt();
                            updatePpt.setId(pptId);
                            updatePpt.setImageUrl(firstImageOssUrl);
                            pptMapper.updateById(updatePpt);
                            log.info("PPT首图已上传OSS: {}", firstImageOssUrl);
                        } catch (Exception e) {
                            log.error("将PPT第一张幻灯片转换为图片失败", e);
                            // 转换失败不影响整体流程
                        }
                    });
                } else {
                    log.warn("PPT OSS URL为空，跳过图片转换");
                }
            } else {
                ppt.setStatus(PptStatusConstant.PPT_STATUS_FAILED);
                log.warn("PPT生成失败");
            }

            pptMapper.updateById(ppt);
            log.info("PPT结果已保存到数据库, id={}, status={}", pptId, ppt.getStatus());
        } else {
            log.warn("pptNode不存在，跳过保存");
        }
    }

    /**
     * 将PPT第一张幻灯片转换为图片并上传OSS
     * @param pptUrl PPT文件的OSS链接
     * @param pptId PPT任务ID
     * @return 图片的OSS链接
     */
    private String convertFirstSlideToImage(String pptUrl, String pptId) throws Exception {
        // 下载PPT文件
        URL url = new URL(pptUrl);
        try (InputStream is = url.openStream();
             XMLSlideShow ppt = new XMLSlideShow(is)) {

            // 获取第一张幻灯片
            XSLFSlide firstSlide = ppt.getSlides().get(0);

            // 获取幻灯片尺寸
            Dimension pageSize = ppt.getPageSize();
            int width = pageSize.width;
            int height = pageSize.height;

            // 创建BufferedImage
            BufferedImage image = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
            Graphics2D graphics = image.createGraphics();

            try {
                // 设置背景为白色
                graphics.setPaint(Color.WHITE);
                graphics.fill(new Rectangle(0, 0, width, height));

                // 设置抗锯齿和渲染提示，提高文字清晰度
                graphics.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
                graphics.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
                graphics.setRenderingHint(RenderingHints.KEY_RENDERING, RenderingHints.VALUE_RENDER_QUALITY);
                graphics.setRenderingHint(RenderingHints.KEY_FRACTIONALMETRICS, RenderingHints.VALUE_FRACTIONALMETRICS_ON);

                // 渲染幻灯片到图片（字体由FontConfig类在启动时注册到GraphicsEnvironment）
                firstSlide.draw(graphics);

                // 将图片转换为字节数组
                ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
                ImageIO.write(image, "png", outputStream);
                byte[] imageBytes = outputStream.toByteArray();

                // 生成文件名并上传OSS
                String fileName = "ppt/image/" + pptId + "_" + UUID.randomUUID().toString() + ".png";
                return aliOssUtil.upload(imageBytes, fileName);
            } finally {
                // 释放Graphics2D资源
                graphics.dispose();
            }
        }
    }

    /**
     * 插入 userId + taskId（保留兼容）
     * @param userId
     * @param id
     */
    @Override
    public void insertUserIdAndTaskId(Long userId, String id) {
        Ppt ppt = new Ppt();
        ppt.setUserId(userId);
        ppt.setTaskId(id);
        ppt.setCreatedAt(String.valueOf(LocalDateTime.now()));
        pptMapper.insert(ppt);
    }

    /**
     * 查询PPT进度，从数据库获取
     * 支持根据数据库ID或Python端resourceId查询
     * @param id 数据库ID(数字)或resourceId(字符串)
     * @return
     */
    @Override
    public Map<String, Object> getProgress(String id) {
        Ppt ppt = null;
        // 判断是否为数字类型(数据库ID)
        if (isNumber(id)) {
            // 是数字类型，将id转为数字
            Long num = Long.parseLong(id);
            ppt = pptMapper.selectById(num);
        } else {
            // 如果不是数字就是资源id(py端的)
            ppt = pptMapper.getPptByResourceId(id);
        }

        if (ppt == null) {
            throw new RuntimeException("PPT任务不存在");
        }

        Map<String, Object> result = new HashMap<>();
        result.put("id", ppt.getId());
        result.put("userId", ppt.getUserId());
        result.put("imagesUrl", ppt.getImageUrl());
        result.put("pptTitle", ppt.getPptTitle());
        result.put("pageCount", ppt.getPageCount());
        result.put("status", ppt.getStatus());
        result.put("createdAt", ppt.getCreatedAt());
        result.put("ossUrl", ppt.getOssUrl());

        return result;
    }

    /**
     * 判断是否为数字
     * @param str
     * @return
     */
    private static boolean isNumber(String str) {
        if (str == null || str.isEmpty()) return false;
        return str.matches("\\d+");
    }

    /**
     * 获取 PPT 状态（保留兼容）
     * @param id
     * @return
     */
    @Override
    public JSONObject getPptResultWithOss(String id) {
        return null;
    }

    /**
     * 获取 PPT 下载地址（从数据库获取OSS链接）
     * @param id
     * @param type
     * @return
     * @throws Exception
     */
    @Override
    public JSONObject getDownload(String id, String type) throws Exception {
        Ppt ppt = pptMapper.selectById(id);
        if (ppt == null) {
            throw new RuntimeException("PPT任务不存在");
        }

        JSONObject json = new JSONObject();
        JSONObject data = new JSONObject();
        data.put("download_url", ppt.getOssUrl());
        json.put("data", data);
        return json;
    }

    /**
     * 获取用户id和任务id
     * @return
     */
    @Override
    public List<Ppt> getByUserId(Long userId) {
        return pptMapper.getByUserId(userId);
    }

    /**
     * 删除用户id和任务id
     * @param pptId
     */
    @Override
    public void deleteTable(Long pptId) {
        pptMapper.deleteById(pptId);
    }

    @Override
    public Long savePpt(ChatDTO chatDTO) {
        String userIdStr = chatDTO.getUserId().toString();

        // 1. 创建数据库记录（生成中状态）
        Ppt ppt = Ppt.builder()
                .userId(chatDTO.getUserId())
                .pptTitle(chatDTO.getText())
                .status(PptStatusConstant.PPT_STATUS_GENERATING)
                .createdAt(String.valueOf(LocalDateTime.now()))
                .build();
        pptMapper.insert(ppt);

        // 2. 检查是否有SSE连接
        boolean hasSseConnection = sseConnectionService.isConnected(userIdStr);

        // 3. 异步调用Python /chat接口
        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("user_id", userIdStr);
        requestBody.put("user_input", chatDTO.getText());

        AsyncUtil.execute(() -> {
            try {
                pythonSseClient.consumePostSse("/chat", requestBody, jsonData -> {
                    log.info("PPT SSE事件数据: {}", jsonData.length() > 500 ? jsonData.substring(0, 500) + "..." : jsonData);
                    
                    // 如果有SSE连接，转发给前端
                    if (hasSseConnection) {
                        sseConnectionService.sendMessage(userIdStr, "ppt_stream", jsonData);
                    }

                    // 监听 task_result 事件，保存到数据库
                    try {
                        JsonNode root = objectMapper.readTree(jsonData);
                        String eventType = root.path("type").asText("");
                        log.info("PPT SSE事件类型: {}", eventType);
                        
                        if ("task_result".equals(eventType)) {
                            JsonNode resultNode = root.path("result");
                            log.info("PPT task_result result节点是否存在: {}, ppt节点是否存在: {}", 
                                    !resultNode.isMissingNode(), 
                                    !resultNode.isMissingNode() && !resultNode.path("ppt").isMissingNode());
                            
                            if (!resultNode.isMissingNode()) {
                                savePptResultFromJson(ppt.getId(), resultNode);
                            }
                        }
                    } catch (Exception e) {
                        log.error("处理PPT SSE事件失败", e);
                    }
                });
            } catch (Exception e) {
                log.error("SSE流式调用Python失败", e);
                Ppt failBean = Ppt.builder()
                        .id(ppt.getId())
                        .status(PptStatusConstant.PPT_STATUS_FAILED)
                        .build();
                pptMapper.updateById(failBean);
            }
        });

        return ppt.getId();
    }

    @Override
    public ChatResourceVO getPptInfoById(Integer taskId) {
        Ppt ppt = pptMapper.selectById(taskId.longValue());
        if (ppt == null) {
            return null;
        }
        
        ChatResourceVO chatResourceVO = new ChatResourceVO();
        chatResourceVO.setId(ppt.getId().toString());
        chatResourceVO.setStatus(ppt.getStatus());
        chatResourceVO.setText(ppt.getPptTitle()); // 使用pptTitle作为text
        chatResourceVO.setCreateTime(ppt.getCreatedAt());
        chatResourceVO.setSuggestionWarning(ppt.getSuggestionWarning());
        
        return chatResourceVO;
    }

    /**
     * 字符串安全转为Long
     * @param str 待转换文本
     * @param defaultVal 转换失败返回值
     * @return Long
     */
    private Long safeToLong(String str, Long defaultVal) {
        if (str == null || str.isBlank()) {
            return defaultVal;
        }
        try {
            return Long.valueOf(str.trim());
        } catch (NumberFormatException ignored) {
            return defaultVal;
        }
    }
}