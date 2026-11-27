package com.dhi.wha;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@MapperScan("com.dhi.wha.mapper")
public class WHubAcademyServerApplication {

    public static void main(String[] args) {
        SpringApplication.run(WHubAcademyServerApplication.class, args);
    }

}
