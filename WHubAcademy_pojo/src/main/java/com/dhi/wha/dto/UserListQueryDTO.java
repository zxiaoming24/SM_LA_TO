package com.dhi.wha.dto;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.Data;
import org.springframework.beans.factory.annotation.Autowired;

import java.util.ArrayList;
import java.util.List;

@Data
public class UserListQueryDTO {
    private String username;
    private String type;
    private Object createTime;
    private Integer currentPage;
    private Integer pageSize;

    // 静态ObjectMapper，避免频繁new
    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();

    public List<String> getCreateTimeList() {
        if (createTime == null) {
            return new ArrayList<>();
        }
        // 情况1：本身就是List
        if (createTime instanceof List<?>) {
            return (List<String>) createTime;
        }
        // 情况2：字符串，比如 "" 或者 "[\"xx\",\"xx\"]"
        if (createTime instanceof String) {
            String str = ((String) createTime).trim();
            if (str.isEmpty()) {
                return new ArrayList<>();
            }
            try {
                // 将JSON字符串转为List<String>
                return OBJECT_MAPPER.readValue(str, new TypeReference<List<String>>() {});
            } catch (Exception e) {
                // 字符串不是合法数组，返回空集合
                return new ArrayList<>();
            }
        }
        // 其他类型直接返回空集合
        return new ArrayList<>();
    }
}
