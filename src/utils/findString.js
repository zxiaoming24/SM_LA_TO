// src/utils/findString.js
// aiAnswer的检测用户输入的文本中是否包含生成资源关键词

//0ppt，1思维导图，2讲解文档/word，3拓展阅读，4编程题，5视频，6动画，7非编程题/理论题/试卷，8学习计划
//ai对话判断用户是否是资源请求
export const findString = (text) => {
  if (!text || typeof text !== 'string') {
    console.error('输入无效：请输入一个非空字符串');
    return null
  }

  const lowerText = text.toLowerCase();

  if (lowerText.includes('什么') || lowerText.includes('是什么') || lowerText.includes('你知道')) {
    console.log('询问资源，不是生成资源');
    return null
  }

  const foundTypes = new Set();//创建一个 Set 来存储找到的资源类型，不重复

  if (lowerText.includes('搜索') || lowerText.includes('生成') || lowerText.includes('生成资源') || lowerText.includes('资源')) {
    console.log('检测到 生成类 关键词')

    if (lowerText.includes('复习')) {
      console.log('检测到 复习 关键词');
    }

    if (lowerText.includes('ppt') || lowerText.includes('演示') || lowerText.includes('幻灯片') || lowerText.includes('powerpoint')) {
      console.log('检测到 PPT 关键词，设置 rsType 为 0');
      foundTypes.add(0)
    }

    if (lowerText.includes('思维导图') || lowerText.includes('脑图')) {
      console.log('检测到 思维导图 关键词，设置 rsType 为 1');
      foundTypes.add(1);
    }

    if (lowerText.includes('word') || lowerText.includes('文档') || lowerText.includes('讲解')) {
      console.log('检测到 讲解文档/word 关键词，设置 rsType 为 2');
      foundTypes.add(2);
    }

    if (lowerText.includes('拓展阅读') || lowerText.includes('扩展阅读')) {
      console.log('检测到 拓展阅读 关键词，设置 rsType 为 3');
      foundTypes.add(3);
    }

    if (lowerText.includes('视频')) {
      console.log('检测到 视频 关键词，设置 rsType 为 5');
      foundTypes.add(5);
    }

    if (lowerText.includes('动画')) {
      console.log('检测到 动画 关键词，设置 rsType 为 6');
      foundTypes.add(6);
    }

    if (lowerText.includes('题') || lowerText.includes('题目') || lowerText.includes('练习')) {
      console.log('检测到 题/题目/练习 关键词');
      if (lowerText.includes('编程')) {
        console.log('检测到 编程练习 关键词，设置 rsType 为 4');
        foundTypes.add(4);
        if (lowerText.includes('非编程') || lowerText.includes('试卷') || lowerText.includes('理论题')) {
          console.log('检测到 编程练习 关键词，设置 rsType 为 4');
          foundTypes.add(7);
        }
      } else {
        console.log('检测后为 非编程题 关键词，设置 rsType 为 7 ');
        foundTypes.add(7);
      }
    }

    if (lowerText.includes('试卷')) {
      console.log('检测到 试卷 关键词，设置 rsType 为 7');
      foundTypes.add(7);
    }

    if (lowerText.includes('学习')) {
      if (lowerText.includes('计划') || lowerText.includes('规划') || lowerText.includes('路线') || lowerText.includes('路径') || lowerText.includes('方案')) {
        console.log('检测到 学习计划 关键词，设置 rsType 为 8');
        foundTypes.add(8);
      }
    }

  }

  const typesArray = Array.from(foundTypes);

  if (typesArray.length === 0) {
    console.log('未检测到特定资源类型关键词');
    return null
  }

  if (typesArray.includes(8) && typesArray.length > 1) {
    console.log('检测到学习计划和其他资源混合，返回 cancel');
    return 'cancel'
  }

  if (typesArray.length === 1) {
    return typesArray[0]
  }

  return typesArray
}