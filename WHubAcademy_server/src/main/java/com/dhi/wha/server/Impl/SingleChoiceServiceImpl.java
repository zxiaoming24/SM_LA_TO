package com.dhi.wha.server.Impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.dhi.wha.entity.SingleChoicePO;
import com.dhi.wha.mapper.SingleChoiceMapper;
import com.dhi.wha.server.SingleChoiceService;
import org.springframework.stereotype.Service;

@Service
public class SingleChoiceServiceImpl extends ServiceImpl<SingleChoiceMapper, SingleChoicePO> implements SingleChoiceService {}
