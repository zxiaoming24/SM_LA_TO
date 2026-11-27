package com.dhi.wha.dto;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

@Data
public class QuestionSubmitDTO {
    @JsonProperty("user_id")
    private String userId;

    @JsonProperty("question_type")
    private String questionType;

    private Question question;

    @JsonProperty("user_answer")
    private String userAnswer;

    private String sessionId;

    // 最终给Python接口使用的数组字段
    @JsonIgnore
    private List<String> knowledgePoints;

    // 兼容前端传入 逗号字符串 / JSON数组，解决数组解析报错
    @JsonProperty("knowledge_points")
    public void setKnowledgePointsStr(Object val) {
        if (val == null) {
            this.knowledgePoints = new ArrayList<>();
            return;
        }
        // 前端传数组 [xxx,xxx]
        if (val instanceof List<?>) {
            List<?> tempList = (List<?>) val;
            this.knowledgePoints = new ArrayList<>();
            for (Object item : tempList) {
                if (item != null) {
                    this.knowledgePoints.add(String.valueOf(item));
                }
            }
        }
        // 前端传逗号分割字符串 "xxx,xxx"
        else if (val instanceof String) {
            String str = ((String) val).trim();
            if (str.isBlank()) {
                this.knowledgePoints = new ArrayList<>();
                return;
            }
            this.knowledgePoints = new ArrayList<>(Arrays.asList(str.split(",")));
        }
    }

    // 返回JSON时自动拼接为逗号分隔字符串对外输出
    @JsonProperty("knowledge_points")
    public String getKnowledgePointsStr() {
        if (knowledgePoints == null || knowledgePoints.isEmpty()) {
            return "";
        }
        return String.join(",", knowledgePoints);
    }

    // 提供getter供后端调用，直接获取数组传给Python接口
    public List<String> getKnowledgePoints() {
        return knowledgePoints == null ? Collections.emptyList() : new ArrayList<>(knowledgePoints);
    }

    // 提供setter，后端代码可直接赋值集合
    public void setKnowledgePoints(List<String> knowledgePoints) {
        this.knowledgePoints = knowledgePoints == null ? new ArrayList<>() : new ArrayList<>(knowledgePoints);
    }

    @Data
    public static class Question {
        private String question;
        private List<String> options;
        private String answer;
    }
}
