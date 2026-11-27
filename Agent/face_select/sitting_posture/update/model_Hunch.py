import pandas as pd
import numpy as np
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.model_selection import GridSearchCV
from sklearn.feature_selection import SelectFromModel
import joblib
from sklearn.metrics import confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns

# 读取数据
df = pd.read_excel(r'D:\pythonproject\multimodal_part_of_mock_interview\sitting_posture\model3\datasets\HunchTotal.xlsx')
# 获取输入特征与目标标签
x_data = df[[ 'distAverage', 'distShoulder','distMounthToShoulder','distNoseToMounth']].values
y_data = df['label'].values
# 训练测试切分
x_train, x_test, y_train, y_test = train_test_split(x_data, y_data, test_size=0.2)
# 调参选择最佳参数
param_grid = {
    'n_estimators': [100, 200, 300],
    'max_features': [0.6, 0.8, 1.0]
}
grid_search = GridSearchCV(RandomForestClassifier(), param_grid, scoring='accuracy', cv=5)
grid_search.fit(x_train, y_train)
# 构建最佳模型
rf = grid_search.best_estimator_
rf.fit(x_train, y_train)
print(x_test)
# 模型预测
y_pred = rf.predict(x_test)
print(y_pred )
# ... (前面的数据读取、模型训练和预测代码不变)

# 获取唯一的类别标签，并按顺序排列。假设你的标签是0,1,2等。
# 如果你的类别有具体的名称（如‘正常’，‘驼背’），请直接定义一个列表：
# class_names = ['正常', '驼背', ...] 
class_names = sorted(df['label'].astype(int).unique())  # 这会得到类似 [0, 1] 的结果
# 为了可读性，也可以将它们转为字符串
class_names = [str(x) for x in class_names]

# 计算混淆矩阵
cm = confusion_matrix(y_test, y_pred)

# 创建图形
plt.figure(figsize=(8, 6))

# 使用seaborn的heatmap绘制混淆矩阵
# 主要修改：1. 将 `xticklabels` 和 `yticklabels` 参数设置为正确的类别名称列表 `class_names`
sns.heatmap(cm, 
            annot=True,       # 在格子中显示数字
            fmt='d',          # 数字格式为整数
            cmap='Blues',     # 使用蓝白色调
            xticklabels=class_names,  # 修正：设置x轴刻度标签为类别名
            yticklabels=class_names)  # 修正：设置y轴刻度标签为类别名

plt.xlabel('Predicted Label')
plt.ylabel('True Label')
plt.title('Random Forest Confusion Matrix')

# 关键修改2：自动调整布局，防止标签显示不全[6](@ref)
plt.tight_layout() 

# 如果使用tight_layout后仍然显示不全，可以手动调整底部边距
# plt.gcf().subplots_adjust(bottom=0.15)

plt.show()

# ... (后面的模型评估和保存代码不变)
# 模型评估
accuracy = round(rf.score(x_test, y_test) * 100, 2)
print('随机森林模型精度:%.2f%%' % accuracy)
# 模型序列化
joblib.dump(rf, 'rf_model_Hunch_1.joblib')