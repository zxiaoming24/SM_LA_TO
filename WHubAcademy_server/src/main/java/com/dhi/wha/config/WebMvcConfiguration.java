package com.dhi.wha.config;

import com.dhi.wha.Interceptor.JwtTokenAdminInterceptor;
import com.dhi.wha.json.JacksonObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.converter.HttpMessageConverter;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.web.filter.CharacterEncodingFilter;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurationSupport;

import java.nio.charset.StandardCharsets;
import java.util.List;

/**
 * 配置类，注册web层相关组件，这些代码会改就可以了
 */
@Configuration
@Slf4j
public class WebMvcConfiguration extends WebMvcConfigurationSupport {

    @Autowired
    private JwtTokenAdminInterceptor jwtTokenAdminInterceptor;


    /**
     * 注册自定义拦截器
     *
     * @param registry
     */
    protected void addInterceptors(InterceptorRegistry registry) {
        log.info("开始注册自定义拦截器...");
        registry.addInterceptor(jwtTokenAdminInterceptor)
                .addPathPatterns("/**")
                .excludePathPatterns("/login")
                .excludePathPatterns("/register")
                .excludePathPatterns("/email/**")
                .excludePathPatterns("/ppt/**")
                .excludePathPatterns("/word/**")
                .excludePathPatterns("/sse/**")
                .excludePathPatterns("/common/upload");
    }


    /**
     * 设置静态资源映射(映射word文档等资源)
     * @param registry
     */
    protected void addResourceHandlers(ResourceHandlerRegistry registry) {
        registry.addResourceHandler("/doc.html").addResourceLocations("classpath:/META-INF/resources/");
        registry.addResourceHandler("/webjars/**").addResourceLocations("classpath:/META-INF/resources/webjars/");


        // 访问地址：http://localhost:8080/word/你的文件名.docx
        registry.addResourceHandler("/word/**")
                // 这里改成你本地存Word的真实文件夹路径
                .addResourceLocations("file:D:/WisdomHubAcademy/WHubAcademy/assets/");
    }

    /**
     * 日期格式化
     * @param converters
     */
    @Override
    protected void extendMessageConverters(List<HttpMessageConverter<?>> converters) {
        log.info("开启消息转换器...");

        //创建一个消息转换器对象
        MappingJackson2HttpMessageConverter converter = new MappingJackson2HttpMessageConverter();
        //调用它
        converter.setObjectMapper(new JacksonObjectMapper());
        //放入容器中，并且优先执行它(索引是0)
        converters.add(0,converter);
    }
}
