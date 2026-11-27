package com.dhi.wha.server.Impl;

import com.dhi.wha.dto.AdoptRouteDTO;
import com.dhi.wha.dto.EvaluateRouteDTO;
import com.dhi.wha.result.Result;
import com.dhi.wha.server.RouteMarketService;
import com.dhi.wha.utils.PythonRestClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;

@Service
public class RouteMarketServiceImpl implements RouteMarketService {

    @Autowired
    private PythonRestClient pythonRestClient;

    @Override
    public Result<Object> getCategories() {
        Object data = pythonRestClient.get("/api/route-market/categories");
        return Result.success(data);
    }

    @Override
    public Result<Object> getRouteList(String userId, String sort, String search) {
        StringBuilder api = new StringBuilder("/api/route-market/list?userId={userId}");
        if (sort != null && !sort.isEmpty()) {
            api.append("&sort={sort}");
        }
        if (search != null && !search.isEmpty()) {
            api.append("&search={search}");
        }
        
        Object data;
        if (sort != null && !sort.isEmpty() && search != null && !search.isEmpty()) {
            data = pythonRestClient.getWithQueryParam(api.toString(), userId, sort, search);
        } else if (sort != null && !sort.isEmpty()) {
            data = pythonRestClient.getWithQueryParam(api.toString(), userId, sort);
        } else if (search != null && !search.isEmpty()) {
            data = pythonRestClient.getWithQueryParam(api.toString(), userId, search);
        } else {
            data = pythonRestClient.getWithQueryParam(api.toString(), userId);
        }
        
        return Result.success(data);
    }

    @Override
    public Result<Object> getRouteDetail(String routeId) {
        Object data = pythonRestClient.getWithPathParam("/api/route-market/{route_id}", routeId);
        return Result.success(data);
    }

    @Override
    public Result<Object> adoptRoute(String routeId, AdoptRouteDTO adoptRouteDTO) {
        Object data = pythonRestClient.postWithPathParam("/api/route-market/{route_id}/adopt", adoptRouteDTO, routeId);
        return Result.success(data);
    }

    @Override
    public Result<Object> getAdoptedRoutes(String userId) {
        Object data = pythonRestClient.getWithPathParam("/api/route-market/{user_id}/adopted", userId);
        return Result.success(data);
    }

    @Override
    public Result<Object> evaluateRoute(String routeId, EvaluateRouteDTO evaluateRouteDTO) {
        Object data = pythonRestClient.postWithPathParam("/api/route-market/{route_id}/rate", evaluateRouteDTO, routeId);
        return Result.success(data);
    }

    @Override
    public Result<Object> aiArrangeRoute(Map<String, Object> requestData) {
        Object data = pythonRestClient.post("/api/route-market/auto-generate", requestData);
        return Result.success(data);
    }

    @Override
    public Result<Object> publishRouteToMarket(Map<String, Object> requestData) {
        Object data = pythonRestClient.post("/api/route-market/publish", requestData);
        return Result.success(data);
    }

    @Override
    public Result<Object> deleteRoute(String routeId, String userId) {
        Map<String,String> body = new HashMap<>();
        body.put("user_id",userId);
        Object data = pythonRestClient.deleteWithPathParamAndBody("/api/route-market/{route_id}/delete", body, routeId);
        return Result.success(data);
    }

    @Override
    public Result<Object> updateRoute(String routeId, Map<String, Object> requestData) {
        Object data = pythonRestClient.putWithPathParamAndBody("/api/route-market/{route_id}/update", requestData, routeId);
        return Result.success(data);
    }
}
