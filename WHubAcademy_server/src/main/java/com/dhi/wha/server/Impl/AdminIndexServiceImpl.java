package com.dhi.wha.server.Impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.dhi.wha.entity.*;
import com.dhi.wha.mapper.*;
import com.dhi.wha.server.AdminIndexService;
import com.dhi.wha.vo.ResourceBasicInfoVO;
import com.dhi.wha.vo.ResourceClickVO;
import com.dhi.wha.vo.ResourceGenerationTrendVO;
import com.dhi.wha.vo.UserBasicInfoVO;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.*;
import java.time.format.DateTimeFormatter;
import java.time.temporal.IsoFields;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Service
public class AdminIndexServiceImpl implements AdminIndexService {

    @Autowired
    private LoginMapper loginMapper;

    @Autowired
    private UserOnlineMapper userOnlineMapper;

    @Autowired
    private AnimationMapper animationMapper;

    @Autowired
    private ExtensionReadingMapper extensionReadingMapper;

    @Autowired
    private MindMapMapper mindMapMapper;

    @Autowired
    private PaperMapper paperMapper;

    @Autowired
    private PptMapper pptMapper;

    @Autowired
    private PracticeMapper practiceMapper;

    @Autowired
    private VideoMapper videoMapper;

    @Autowired
    private WordMapper wordMapper;

    @Autowired
    private ResourceClickMapper resourceClickMapper;

    @Override
    public UserBasicInfoVO getUserBasicInfo() {
        UserBasicInfoVO vo = new UserBasicInfoVO();

        Long totalUsers = loginMapper.selectCount(null);
        vo.setTotalUsers(totalUsers);

        LocalDateTime sevenDaysAgo = LocalDateTime.now().minusDays(7);
        LambdaQueryWrapper<User> newUserWrapper = new LambdaQueryWrapper<>();
        newUserWrapper.eq(User::getIsNew, true)
                .ge(User::getCreateTime, sevenDaysAgo);
        Long newUsers = loginMapper.selectCount(newUserWrapper);
        vo.setNewUsers(newUsers);

        LocalDate today = LocalDate.now();
        LambdaQueryWrapper<UserOnline> activeWrapper = new LambdaQueryWrapper<>();
        activeWrapper.eq(UserOnline::getStatDate, today)
                .gt(UserOnline::getTotalSeconds, 3600L);
        Long dailyActiveUsers = userOnlineMapper.selectCount(activeWrapper);
        vo.setDailyActiveUsers(dailyActiveUsers);

        LambdaQueryWrapper<User> portraitWrapper = new LambdaQueryWrapper<>();
        portraitWrapper.eq(User::getIsBuildProfile, 1);
        Long portraitConstructedUsers = loginMapper.selectCount(portraitWrapper);
        vo.setPortraitConstructedUsers(portraitConstructedUsers);

        return vo;
    }

    @Override
    public ResourceBasicInfoVO getResourceBasicInfo() {
        ResourceBasicInfoVO vo = new ResourceBasicInfoVO();

        LocalDateTime todayStart = LocalDateTime.of(LocalDate.now(), LocalTime.MIN);
        LocalDateTime todayEnd = LocalDateTime.of(LocalDate.now(), LocalTime.MAX);

        Long totalResources = 0L;
        Long newResources = 0L;

        // Animation
        totalResources += animationMapper.selectCount(null);
        newResources += countTodayRecords(animationMapper, todayStart, todayEnd);

        // ExtensionReading
        totalResources += extensionReadingMapper.selectCount(null);
        newResources += countTodayRecords(extensionReadingMapper, todayStart, todayEnd);

        // MindMap
        totalResources += mindMapMapper.selectCount(null);
        newResources += countTodayRecords(mindMapMapper, todayStart, todayEnd);

        // PaperPO
        totalResources += paperMapper.selectCount(null);
        newResources += countTodayRecords(paperMapper, todayStart, todayEnd);

        // Ppt
        totalResources += pptMapper.selectCount(null);
        newResources += countTodayRecords(pptMapper, todayStart, todayEnd);

        // Practice
        totalResources += practiceMapper.selectCount(null);
        newResources += countTodayRecords(practiceMapper, todayStart, todayEnd);

        // Video
        totalResources += videoMapper.selectCount(null);
        newResources += countTodayRecords(videoMapper, todayStart, todayEnd);

        // Word
        totalResources += wordMapper.selectCount(null);
        newResources += countTodayRecords(wordMapper, todayStart, todayEnd);

        vo.setTotalResources(totalResources);
        vo.setNewResources(newResources);

        return vo;
    }

    private Long countTodayRecords(AnimationMapper mapper, LocalDateTime start, LocalDateTime end) {
        LambdaQueryWrapper<Animation> wrapper = new LambdaQueryWrapper<>();
        wrapper.between(Animation::getCreateTime, start, end);
        return mapper.selectCount(wrapper);
    }

    private Long countTodayRecords(ExtensionReadingMapper mapper, LocalDateTime start, LocalDateTime end) {
        LambdaQueryWrapper<ExtensionReading> wrapper = new LambdaQueryWrapper<>();
        wrapper.between(ExtensionReading::getCreateTime, start, end);
        return mapper.selectCount(wrapper);
    }

    private Long countTodayRecords(MindMapMapper mapper, LocalDateTime start, LocalDateTime end) {
        LambdaQueryWrapper<MindMap> wrapper = new LambdaQueryWrapper<>();
        wrapper.between(MindMap::getCreateTime, start, end);
        return mapper.selectCount(wrapper);
    }

    private Long countTodayRecords(PaperMapper mapper, LocalDateTime start, LocalDateTime end) {
        LambdaQueryWrapper<PaperPO> wrapper = new LambdaQueryWrapper<>();
        wrapper.between(PaperPO::getCreateTime, start, end);
        return mapper.selectCount(wrapper);
    }

    private Long countTodayRecords(PptMapper mapper, LocalDateTime start, LocalDateTime end) {
        LambdaQueryWrapper<Ppt> wrapper = new LambdaQueryWrapper<>();
        wrapper.between(Ppt::getCreatedAt, start, end);
        return mapper.selectCount(wrapper);
    }

    private Long countTodayRecords(PracticeMapper mapper, LocalDateTime start, LocalDateTime end) {
        LambdaQueryWrapper<Practice> wrapper = new LambdaQueryWrapper<>();
        wrapper.between(Practice::getCreateTime, start, end);
        return mapper.selectCount(wrapper);
    }

    private Long countTodayRecords(VideoMapper mapper, LocalDateTime start, LocalDateTime end) {
        LambdaQueryWrapper<Video> wrapper = new LambdaQueryWrapper<>();
        wrapper.between(Video::getCreateTime, start, end);
        return mapper.selectCount(wrapper);
    }

    private Long countTodayRecords(WordMapper mapper, LocalDateTime start, LocalDateTime end) {
        LambdaQueryWrapper<Word> wrapper = new LambdaQueryWrapper<>();
        wrapper.between(Word::getCreateTime, start, end);
        return mapper.selectCount(wrapper);
    }

    @Override
    public List<ResourceClickVO> getPopularResourcesRank() {
        List<Map<String, Object>> statsList = resourceClickMapper.countAllByResourceType();

        if (statsList == null || statsList.isEmpty()) {
            return new ArrayList<>();
        }

        long total = 0;
        for (Map<String, Object> row : statsList) {
            total += ((Number) row.get("clickCount")).longValue();
        }

        long finalTotal = total;
        List<ResourceClickVO> result = new ArrayList<>();
        for (Map<String, Object> row : statsList) {
            long count = ((Number) row.get("clickCount")).longValue();
            result.add(ResourceClickVO.builder()
                    .resourceType((String) row.get("resourceType"))
                    .clickCount(count)
                    .percentage(Math.round(count * 10000.0 / finalTotal) / 100.0)
                    .build());
        }

        return result;
    }

    @Override
    public ResourceGenerationTrendVO getResourceGenerationTrend(String rangeType) {
        if (rangeType == null || rangeType.isEmpty()) {
            rangeType = "week";
        }

        LocalDate today = LocalDate.now();
        LocalDate startDate;
        List<LocalDate> dateList = new ArrayList<>();

        switch (rangeType) {
            case "year":
                startDate = today.minusYears(1);
                LocalDate currentMonthStart = LocalDate.of(today.getYear(), today.getMonth(), 1);
                for (LocalDate d = startDate; !d.isAfter(currentMonthStart); d = d.plusMonths(1)) {
                    dateList.add(d);
                }
                break;
            case "month":
                startDate = today.minusMonths(3);
                LocalDate weekStart = startDate;
                while (!weekStart.isAfter(today)) {
                    dateList.add(weekStart);
                    weekStart = weekStart.plusWeeks(1);
                }
                if (!dateList.contains(today)) {
                    dateList.add(today);
                }
                break;
            default:
                startDate = today.minusDays(6);
                for (int i = 0; i < 7; i++) {
                    dateList.add(startDate.plusDays(i));
                }
                break;
        }

        List<String> dates = new ArrayList<>();
        List<Long> values = new ArrayList<>();
        DateTimeFormatter dayFormatter = DateTimeFormatter.ofPattern("MM-dd");
        DateTimeFormatter monthFormatter = DateTimeFormatter.ofPattern("yyyy-MM");

        for (int i = 0; i < dateList.size(); i++) {
            LocalDate d = dateList.get(i);
            LocalDate endDate;

            if ("year".equals(rangeType)) {
                endDate = d.plusMonths(1).minusDays(1);
                if (endDate.isAfter(today)) {
                    endDate = today;
                }
                dates.add(d.format(monthFormatter));
            } else if ("month".equals(rangeType)) {
                endDate = d.plusWeeks(1).minusDays(1);
                if (endDate.isAfter(today)) {
                    endDate = today;
                }
                dates.add(d.format(dayFormatter));
            } else {
                endDate = d;
                dates.add(d.format(dayFormatter));
            }

            long count = countResourcesInRange(d, endDate);
            values.add(count);
        }

        List<Long> cumulativeValues = new ArrayList<>();
        long cumulative = 0;
        for (Long v : values) {
            cumulative += v;
            cumulativeValues.add(cumulative);
        }

        long total = cumulativeValues.get(cumulativeValues.size() - 1);
        long max = values.stream().mapToLong(Long::longValue).max().orElse(0L);
        long min = values.stream().mapToLong(Long::longValue).min().orElse(0L);
        double avg = Math.round(total * 10.0 / dateList.size()) / 10.0;

        double growthRate = calculateGrowthRate(rangeType, startDate, today, total);

        ResourceGenerationTrendVO.RangeInfo rangeInfo = new ResourceGenerationTrendVO.RangeInfo();
        rangeInfo.setType(rangeType);
        rangeInfo.setStartDate(startDate.toString());
        rangeInfo.setEndDate(today.toString());
        rangeInfo.setTotalDays((int) startDate.until(today).getDays() + 1);

        ResourceGenerationTrendVO.ChartData chartData = new ResourceGenerationTrendVO.ChartData();
        chartData.setDates(dates);
        chartData.setValues(values);
        chartData.setCumulativeValues(cumulativeValues);

        ResourceGenerationTrendVO.Summary summary = new ResourceGenerationTrendVO.Summary();
        summary.setTotal(total);
        summary.setAvg(avg);
        summary.setMax(max);
        summary.setMin(min);
        summary.setGrowthRate(Math.round(growthRate * 10) / 10.0);

        ResourceGenerationTrendVO.ExtraInfo extraInfo = new ResourceGenerationTrendVO.ExtraInfo();
        if ("week".equals(rangeType)) {
            extraInfo.setWeekNumber(today.get(IsoFields.WEEK_OF_WEEK_BASED_YEAR));
            extraInfo.setYear(today.getYear());
        } else if ("month".equals(rangeType)) {
            extraInfo.setMonthRange(startDate.getYear() + "-" + String.format("%02d", startDate.getMonthValue()) + " 至 " + today.getYear() + "-" + String.format("%02d", today.getMonthValue()));
            int peakIndex = 0;
            for (int i = 1; i < values.size(); i++) {
                if (values.get(i) > values.get(peakIndex)) {
                    peakIndex = i;
                }
            }
            extraInfo.setPeakDay(dateList.get(peakIndex).toString());
            extraInfo.setPeakValue(values.get(peakIndex));
        } else {
            extraInfo.setYearRange(startDate.getYear() + "-" + String.format("%02d", startDate.getMonthValue()) + " 至 " + today.getYear() + "-" + String.format("%02d", today.getMonthValue()));
            int peakIndex = 0;
            for (int i = 1; i < values.size(); i++) {
                if (values.get(i) > values.get(peakIndex)) {
                    peakIndex = i;
                }
            }
            extraInfo.setPeakMonth(dateList.get(peakIndex).format(monthFormatter));
            extraInfo.setPeakValue(values.get(peakIndex));
            extraInfo.setMonthlyAvg(Math.round(total * 10.0 / dateList.size()) / 10.0);
        }

        ResourceGenerationTrendVO vo = new ResourceGenerationTrendVO();
        vo.setRangeInfo(rangeInfo);
        vo.setChartData(chartData);
        vo.setSummary(summary);
        vo.setExtraInfo(extraInfo);

        return vo;
    }

    private long countResourcesInRange(LocalDate startDate, LocalDate endDate) {
        LocalDateTime start = LocalDateTime.of(startDate, LocalTime.MIN);
        LocalDateTime end = LocalDateTime.of(endDate, LocalTime.MAX);

        long count = 0;

        LambdaQueryWrapper<Animation> animationWrapper = new LambdaQueryWrapper<>();
        animationWrapper.between(Animation::getCreateTime, start, end);
        count += animationMapper.selectCount(animationWrapper);

        LambdaQueryWrapper<ExtensionReading> readingWrapper = new LambdaQueryWrapper<>();
        readingWrapper.between(ExtensionReading::getCreateTime, start, end);
        count += extensionReadingMapper.selectCount(readingWrapper);

        LambdaQueryWrapper<MindMap> mindMapWrapper = new LambdaQueryWrapper<>();
        mindMapWrapper.between(MindMap::getCreateTime, start, end);
        count += mindMapMapper.selectCount(mindMapWrapper);

        LambdaQueryWrapper<PaperPO> paperWrapper = new LambdaQueryWrapper<>();
        paperWrapper.between(PaperPO::getCreateTime, start, end);
        count += paperMapper.selectCount(paperWrapper);

        LambdaQueryWrapper<Ppt> pptWrapper = new LambdaQueryWrapper<>();
        pptWrapper.between(Ppt::getCreatedAt, start, end);
        count += pptMapper.selectCount(pptWrapper);

        LambdaQueryWrapper<Practice> practiceWrapper = new LambdaQueryWrapper<>();
        practiceWrapper.between(Practice::getCreateTime, start, end);
        count += practiceMapper.selectCount(practiceWrapper);

        LambdaQueryWrapper<Video> videoWrapper = new LambdaQueryWrapper<>();
        videoWrapper.between(Video::getCreateTime, start, end);
        count += videoMapper.selectCount(videoWrapper);

        LambdaQueryWrapper<Word> wordWrapper = new LambdaQueryWrapper<>();
        wordWrapper.between(Word::getCreateTime, start, end);
        count += wordMapper.selectCount(wordWrapper);

        return count;
    }

    private double calculateGrowthRate(String rangeType, LocalDate startDate, LocalDate endDate, long currentTotal) {
        LocalDate prevStart;
        LocalDate prevEnd;

        switch (rangeType) {
            case "year":
                prevStart = startDate.minusYears(1);
                prevEnd = endDate.minusYears(1);
                break;
            case "month":
                prevStart = startDate.minusMonths(3);
                prevEnd = endDate.minusMonths(3);
                break;
            default:
                prevStart = startDate.minusWeeks(1);
                prevEnd = endDate.minusWeeks(1);
                break;
        }

        long prevTotal = countResourcesInRange(prevStart, prevEnd);
        if (prevTotal == 0) {
            return 0;
        }
        return (currentTotal - prevTotal) * 100.0 / prevTotal;
    }
}
