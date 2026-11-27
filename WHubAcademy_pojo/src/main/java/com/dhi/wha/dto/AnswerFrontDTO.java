package com.dhi.wha.dto;

import lombok.Data;
import java.util.List;

@Data
public class AnswerFrontDTO {
    private List<String> programm;
    private List<String> theory;
}
