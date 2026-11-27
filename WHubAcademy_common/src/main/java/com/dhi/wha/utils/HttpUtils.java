package com.dhi.wha.utils;

import org.apache.http.HttpResponse;
import org.apache.http.client.HttpClient;
import org.apache.http.client.methods.HttpGet;
import org.apache.http.conn.ssl.SSLConnectionSocketFactory;
import org.apache.http.conn.ssl.SSLContextBuilder;
import org.apache.http.conn.ssl.TrustStrategy;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;
import javax.net.ssl.SSLContext;
import java.security.GeneralSecurityException;
import java.security.cert.X509Certificate;
import java.util.Map;
import java.util.Map.Entry;

public class HttpUtils {
    public static HttpResponse doGet(String host, String path, String method, Map<String, String> headers, Map<String, String> querys) throws Exception {
        HttpClient httpClient = wrapClient(host);
        HttpGet request = new HttpGet(buildUrl(host, path, querys));
        for (Entry<String, String> e : headers.entrySet()) request.addHeader(e.getKey(), e.getValue());
        return httpClient.execute(request);
    }

    private static String buildUrl(String host, String path, Map<String, String> querys) {
        StringBuilder sb = new StringBuilder(host);
        if (!path.startsWith("/")) sb.append("/");
        sb.append(path);
        if (querys != null && !querys.isEmpty()) {
            sb.append("?");
            for (Map.Entry<String, String> q : querys.entrySet())
                sb.append(q.getKey()).append("=").append(q.getValue()).append("&");
        }
        return sb.toString();
    }

    private static HttpClient wrapClient(String host) {
        CloseableHttpClient client = HttpClients.createDefault();
        if (host.startsWith("https://")) sslClient(client);
        return client;
    }

    private static void sslClient(CloseableHttpClient client) {
        try {
            SSLContext ctx = new SSLContextBuilder().loadTrustMaterial(null, (chain, auth) -> true).build();
            SSLConnectionSocketFactory factory = new SSLConnectionSocketFactory(ctx, (s, session) -> true);
            HttpClients.custom().setSSLSocketFactory(factory).build();
        } catch (GeneralSecurityException e) { e.printStackTrace(); }
    }
}
