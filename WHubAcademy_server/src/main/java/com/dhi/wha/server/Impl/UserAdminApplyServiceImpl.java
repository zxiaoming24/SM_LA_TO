package com.dhi.wha.server.Impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.dhi.wha.entity.UserAdminApply;
import com.dhi.wha.vo.UserAdminApplyVO;
import com.dhi.wha.mapper.UserAdminApplyMapper;
import com.dhi.wha.server.UserAdminApplyService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class UserAdminApplyServiceImpl extends ServiceImpl<UserAdminApplyMapper, UserAdminApply>
        implements UserAdminApplyService {

    @Autowired
    private UserAdminApplyMapper userAdminApplyMapper;



    @Override
    public List<UserAdminApplyVO> getApplyAdminList() {
        return userAdminApplyMapper.getApplyAdminList();
    }
}