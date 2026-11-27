package com.dhi.wha.server;

import com.baomidou.mybatisplus.extension.service.IService;
import com.dhi.wha.dto.ChatDTO;
import com.dhi.wha.dto.VideoDTO;
import com.dhi.wha.dto.VideoQuizDTO;
import com.dhi.wha.entity.Video;
import com.dhi.wha.vo.ChatResourceVO;
import com.dhi.wha.vo.VideoVO;

import java.util.List;
import java.util.Map;

public interface VideoService extends IService<Video> {

    /**
     * 根据用户ID查询视频列表
     * @param userId 用户ID
     * @return 视频集合
     */
    List<Video> listByUserId(Long userId);

    /**
     * 根据用户输入的文本查询视频
     * @param videoDTO 用户输入的文本
     * @return 视频信息
     */
    Map<String, Object> getVideoByText(VideoDTO videoDTO);

    /**
     * 轮询视频列表
     * @param batchId 批次ID
     * @return 视频信息
     */
    List<Video> pollVideoByBatchId(String batchId);

    /**
     * 根据用户ID查询视频列表
     * @param userId 用户ID
     * @return 视频信息
     */
    List<VideoVO> getListByUserId(Long userId);

    /**
     * 保存视频
     */
    String saveVideo(ChatDTO chatDTO);

    /**
     * 删除视频记录
     * @param batchId 批次ID
     */
    void deleteByBatchId(String batchId);

    /**
     * 获取视频信息
     * @param bvid
     * @param page
     * @return
     */
    Object getVideoInfo(String bvid, Integer page);

    /**
     * 获取视频的第一条数据
     * @param taskId
     * @return
     */
    ChatResourceVO getVideoInfoById(String taskId);

    /**
     * 根据py端的视频id查询视频资源
     * @param resourceId
     * @return
     */
    Video getByResourceId(String resourceId);

    /**
     * 视频观看完成后生成小测试
     * @param videoQuizDTO 视频小测试请求参数
     * @return 测试题数据
     */
    Object postVideoQuiz(VideoQuizDTO videoQuizDTO);

    /**
     * 获取视频综述
     * @param params 请求参数（包含bvid和page）
     * @return 视频综述数据
     */
    Object getSummary(Map<String, Object> params);

    /**
     * 获取视频思维导图
     * @param params 请求参数（包含bvid和page）
     * @return 视频思维导图数据
     */
    Object getMindmap(Map<String, Object> params);
}
