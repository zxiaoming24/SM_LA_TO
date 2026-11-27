//src/utils/skip.js
//用于跳转路由调用资源
import { ref } from 'vue'

//======通用参数======
//reType: 资源类型
//resourceId: 资源id
//======错题本编程题使用======
//recordId: 重练id
//======复习提醒使用======
//sessionId: 复习sessionId
//message: 复习提示语

//保存资源：同rsType只存一条，新增前先移除同类型旧数据
export const saveSkip = (rsType = -1, resourceId = '', recordId = '', sessionId = '', message = '') => {
  if (rsType === -1) {
    console.log('保存失败，请检查 rsType 参数是否正确');
    return;
  }

  // 读取本地数组，无则初始空数组
  let skipList = JSON.parse(localStorage.getItem('skipRs')) || [];

  // 先过滤掉当前同类型数据，保证同rsType唯一
  skipList = skipList.filter(item => item.rsType !== rsType);

  const skipItem = ref({
    rsType: null,
    resourceId: '',
    recordId: '',
    sessionId: '',
    message: ''
  });

  skipItem.value.rsType = rsType;
  console.log('保存信息类型：', rsType);

  switch (rsType) {
    case 0://ppt
    case 1://mindMap
    case 2://word
    case 3://reading
    case 5://video
    case 6://anima
    case 7:// paper
    case 8:// pathPlan
    case 9://post
      skipItem.value.resourceId = resourceId;
      break
    case 4:
      //code
      skipItem.value.resourceId = resourceId;
      skipItem.value.recordId = recordId;
      break
    case 10://aiAnswer
      skipItem.value.sessionId = sessionId;
      skipItem.value.message = message;
      break

  }

  // 追加新对象
  skipList.push(skipItem.value);
  console.log("全部保存信息：", skipList);

  localStorage.setItem('skipRs', JSON.stringify(skipList));
  console.log('已经更新 skipRs 数组');

  // 重置临时对象
  skipItem.value = {
    rsType: null,
    resourceId: '',
    recordId: '',
    sessionId: '',
    message: ''
  }
};

//检测是否有对应类型保存的值，有则返回数据
export const isSkip = (rsType = -1) => {
  if (rsType === -1) {
    console.log('检测失败，请检查 rsType 参数是否正确');
    return false
  }
  const skipStr = localStorage.getItem('skipRs');
  if (!skipStr) {
    console.log('没有跳转信息，不存在该类型资源打开');
    return false;
  }

  try {
    const skipList = JSON.parse(skipStr);
    // 查找对应类型数据（同类型唯一，最多一条）
    const targetItem = skipList.find(item => item.rsType === rsType);
    if (!targetItem) {
      console.log('跳转信息不匹配');
      return false;
    }

    switch (rsType) {
      case 0://ppt
      case 1://mindMap
      case 2://word
      case 3://reading
      case 5://video
      case 6://anima
      case 7:// paper
      case 8:// pathPlan
      case 9:// post
        console.log('返回信息：(resourceId)', targetItem.resourceId)
        return { resourceId: targetItem.resourceId }
        break
      case 4: //编程练习code
        console.log('返回信息：(resourceId，recordId)', targetItem.resourceId, targetItem.recordId)
        return { resourceId: targetItem.resourceId, recordId: targetItem.recordId }
        break
      case 10://aiAnswer
        console.log('返回信息：(sessionId，message)', targetItem.sessionId, targetItem.message)
        return { sessionId: targetItem.sessionId, message: targetItem.message }
        break
    }
    return false;
  } catch (e) {
    console.error('数据解析失败', e)
    return false;
  }
};

//删除指定 rsType 的数据
export const removeSkip = (rsType = -1) => {
  if (rsType === -1) {
    console.log('删除失败，请检查 rsType 参数是否正确')
    return false
  }
  const skipStr = localStorage.getItem('skipRs');
  if (!skipStr) {
    console.log('没有跳转信息，无法删除');
    return false;
  }

  try {
    let skipList = JSON.parse(skipStr);
    // 移除对应类型
    skipList = skipList.filter(item => item.rsType !== rsType);

    if (skipList.length === 0) {
      localStorage.removeItem('skipRs');
    } else {
      localStorage.setItem('skipRs', JSON.stringify(skipList));
    }
    console.log(`已删除 rsType=${rsType} 的跳转数据`);
    return true;
  } catch (e) {
    console.error('删除数据失败', e)
    return false;
  }
};

// 清空全部数据
export const clearAllSkip = () => {
  localStorage.removeItem('skipRs');
  console.log('已清空所有跳转资源数据');
}