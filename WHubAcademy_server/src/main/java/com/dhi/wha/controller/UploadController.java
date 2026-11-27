package com.dhi.wha.controller;

import com.dhi.wha.result.Result;
import com.dhi.wha.utils.AliOssUtil;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.UUID;


@RequestMapping("/common")
@RestController
@Slf4j
public class UploadController {

    @Autowired
    private AliOssUtil aliOssUtil;

    /**
     * 文件上传
     *
     * @param file
     * @return
     */
    @PostMapping("/upload")
    public Result<String> upload(MultipartFile file) {

        // 避免文件覆盖,注意tlias哪个项目的这个工具类更好用，不过需要自己改进一下，来变成自己的。
        String originalFilename = file.getOriginalFilename();
        String fileName = UUID.randomUUID().toString() + originalFilename.substring(originalFilename.lastIndexOf("."));

        String url = null;
        try {
            url = aliOssUtil.upload(file.getBytes(), fileName);
        } catch (IOException e) {
            log.error(e.getMessage());
        }
        return Result.success(url);
    }
}
