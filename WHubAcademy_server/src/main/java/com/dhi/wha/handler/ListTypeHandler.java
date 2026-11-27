package com.dhi.wha.handler;

import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import org.apache.ibatis.type.JdbcType;
import org.apache.ibatis.type.MappedJdbcTypes;
import org.apache.ibatis.type.MappedTypes;

import java.util.List;

//Jackson 类型处理器

@MappedTypes(List.class)
@MappedJdbcTypes(JdbcType.VARCHAR)
public class ListTypeHandler extends JacksonTypeHandler {
    public ListTypeHandler(Class<?> type) {
        super(type);
    }
}