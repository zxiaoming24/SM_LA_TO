package com.dhi.wha.entity;

import lombok.Data;

import java.util.List;

@Data
public class QuestionName {
    private String newName;
    private List<String> oldName;
}
