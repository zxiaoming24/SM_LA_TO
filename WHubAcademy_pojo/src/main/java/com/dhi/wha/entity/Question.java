package com.dhi.wha.entity;

import lombok.Data;

@Data
public class Question {
    private Integer count;
    private Integer newItem;
    private Integer oldItem;
    private QuestionName name;
}
