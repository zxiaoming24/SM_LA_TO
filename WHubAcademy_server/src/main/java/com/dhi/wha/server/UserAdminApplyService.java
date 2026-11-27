package com.dhi.wha.server;

import com.baomidou.mybatisplus.extension.service.IService;
import com.dhi.wha.entity.UserAdminApply;
import com.dhi.wha.vo.UserAdminApplyVO;

import java.util.List;

public interface UserAdminApplyService extends IService<UserAdminApply> {
    /**
     * 获取管理员申请列表
     * @return
     */
    List<UserAdminApplyVO> getApplyAdminList();

}
