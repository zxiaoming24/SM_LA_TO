package com.dhi.wha.server.Impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.dhi.wha.entity.FillBlankPO;
import com.dhi.wha.mapper.FillBlankMapper;
import com.dhi.wha.server.FillBlankService;
import org.springframework.stereotype.Service;

@Service
public class FillBlankServiceImpl extends ServiceImpl<FillBlankMapper, FillBlankPO> implements FillBlankService {}
