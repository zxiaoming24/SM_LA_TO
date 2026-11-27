from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import MultiLabelBinarizer
from xgboost import XGBClassifier
from sklearn.multiclass import OneVsRestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn import svm
from sklearn.tree import DecisionTreeClassifier
from sklearn import metrics
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

class ML_Model():
    def __init__(self,data,fea_start,fea_end,targetname = 'label'):
        self.data = data
        #数据处理
        self.features = self.data.iloc[:,fea_start:fea_end]
        self.labels = self.data[targetname]
        self.mlb = MultiLabelBinarizer()
        self.labels_encoded = self.mlb.fit_transform(self.labels.apply(lambda x: x.split(', ')))

    def ml_model(self,threshold=0.02,labelcount=5,tree_num=50,tree_depth=6,learning_rates=0.1):
        #XGBoost作为基分类器
        self.xgb = XGBClassifier()
        self.xgb.fit(self.features, self.labels_encoded)
        self.importance = self.xgb.feature_importances_
        self.threshold = threshold  # 设置特征重要性阈值
        self.selected_features = self.features.columns[self.importance > self.threshold]  # 选择特征评估指标＞阈值的特征
        self.selected_features_data = self.features[self.selected_features]

        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(self.selected_features_data, self.labels_encoded, random_state=0)
        self.clf_multilabel = OneVsRestClassifier(XGBClassifier(
            objective='multi:softprob',  # 使用'multi:softprob'作为损失函数
            num_class=labelcount,  # 标签的数量
            n_estimators=tree_num,
            max_depth=tree_depth,
            learning_rate=learning_rates
        ))

        self.clf_multilabel.fit(self.X_train, self.y_train)
        self.prediction = self.clf_multilabel.predict(self.X_test)
        self.score = metrics.accuracy_score(self.prediction, self.y_test)

        return self.clf_multilabel,self.score,self.mlb


class SL_Model():
    def __init__(self,data,fea_start,fea_end ,targetname = 'label'):
        self.data = data
        self.x = self.data.iloc[:,fea_start:fea_end]
        self.y = self.data[targetname]
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(self.x, self.y, random_state=0)
    #svm
    def svm_model(self):
        self.model_s = svm.SVC()
        self.model_s.fit(self.X_train,self.y_train)
        self.pre_s = self.model_s.predict(self.X_test)
        self.score_s = metrics.accuracy_score(self.pre_s,self.y_test)
        print("self.model_s,self.score_s",self.model_s,self.score_s)
        return self.model_s,self.score_s

    #logistic
    def log_model(self):
        self.model_l = LogisticRegression(max_iter=300)
        self.model_l.fit(self.X_train,self.y_train)
        self.pre_l = self.model_l.predict(self.X_test)
        self.score_l = metrics.accuracy_score(self.pre_l,self.y_test)
        print("self.model_l,self.score_l", self.model_l, self.score_l)
        return self.model_l,self.score_l

    #decision tree
    def dec_model(self):
        self.model_d = DecisionTreeClassifier()
        self.model_d.fit(self.X_train,self.y_train)
        self.pre_d = self.model_d.predict(self.X_test)
        self.score_d = metrics.accuracy_score(self.pre_d,self.y_test)
        print("self.model_d,self.score_d",self.model_d,self.score_d)
        return self.model_d,self.score_d

    #k-neighbors
    def k_model(self):
        self.model_k = KNeighborsClassifier(n_neighbors=3)
        self.model_k.fit(self.X_train,self.y_train)
        self.pre_k = self.model_k.predict(self.X_test)
        self.score_k = metrics.accuracy_score(self.pre_k,self.y_test)
        print("self.model_k,self.score_k",self.model_k,self.score_k)
        return self.model_k,self.score_k

    #构建随机森林模型
    def r_model(self):
        self.model_r = RandomForestClassifier(n_estimators=100)
        self.model_r.fit(self.X_train, self.y_train)
        self.pre_r = self.model_k.predict(self.X_test)
        self.score_r = metrics.accuracy_score(self.pre_r, self.y_test)
        print("self.model_r,self.score_r", self.model_r, self.score_r)
        return self.model_r, self.score_r


    def score_mean(self):
        _, self.score_s = self.svm_model()
        _, self.score_l = self.log_model()
        _, self.score_d = self.dec_model()
        _, self.score_k = self.k_model()
        _, self.score_r=self.r_model()
        self.mean = (self.score_s+self.score_d+self.score_k+self.score_r)/3
        return self.mean

    #选择模型
    def select_model(self):
        self.model_s, self.score_s = self.svm_model()
        self.model_d, self.score_d = self.dec_model()
        self.model_k, self.score_k = self.k_model()
        self.model_l,self.score_l=self.r_model()
        self.model_r, self.score_r=self.r_model()
        self.max_score = max(self.score_s, self.score_d, self.score_k,self.score_l,self.score_r)

        if self.max_score == self.score_s:
            self.best_model = self.model_s
        elif self.max_score == self.score_d:
            self.best_model = self.model_d
        else:
            self.best_model = self.model_k
        return self.best_model,self.max_score

    # 绘制混淆矩阵
    def plot_confusion_matrix(self, model_type='best', class_names=None, save_path=None, normalize=False):
        """
        绘制混淆矩阵
        @param model_type: 模型类型，可选 'svm', 'logistic', 'decision_tree', 'k_neighbors', 'random_forest', 'best'
        @param class_names: 类别名称列表，如果为None则自动从y_test中提取
        @param save_path: 保存路径，如果为None则只显示不保存
        @param normalize: 是否显示比例而不是计数，默认为False（显示计数）
        """
        # 根据模型类型获取预测结果
        if model_type == 'svm':
            y_pred = self.pre_s
        elif model_type == 'logistic':
            y_pred = self.pre_l
        elif model_type == 'decision_tree':
            y_pred = self.pre_d
        elif model_type == 'k_neighbors':
            y_pred = self.pre_k
        elif model_type == 'random_forest':
            y_pred = self.pre_r
        elif model_type == 'best':
            # 先选择最佳模型
            best_model, _ = self.select_model()
            y_pred = best_model.predict(self.X_test)
        else:
            raise ValueError("model_type 必须是以下值之一: 'svm', 'logistic', 'decision_tree', 'k_neighbors', 'random_forest', 'best'")
        
        # 计算混淆矩阵
        cm = confusion_matrix(self.y_test, y_pred)
        
        # 如果需要显示比例，则对混淆矩阵进行归一化处理
        if normalize:
            cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
            fmt = '.2f'  # 显示两位小数
        else:
            fmt = 'd'  # 显示整数
        
        # 如果没有提供类别名称，则从测试集中提取
        if class_names is None:
            class_names = sorted(list(set(list(self.y_test))))
        
        # 创建图形
        plt.figure(figsize=(8, 6))
        
        # 使用seaborn绘制混淆矩阵
        sns.heatmap(cm, 
                    annot=True,       # 在格子中显示数字
                    fmt=fmt,          # 数字格式，比例用'.2f'，计数用'd'
                    cmap='Blues',     # 使用蓝白色调
                    xticklabels=class_names,  # 设置x轴刻度标签为类别名
                    yticklabels=class_names)  # 设置y轴刻度标签为类别名

        plt.xlabel('Predicted Label')
        plt.ylabel('True Label')
        title_type = f'{model_type} model'
        title_suffix = ' (Normalized)' if normalize else ''
        plt.title(f'Confusion Matrix - {title_type}{title_suffix}')
        
        # 自动调整布局
        plt.tight_layout() 
        
        # 保存或显示图片
        if save_path:
            plt.savefig(save_path)
            print(f"混淆矩阵已保存至: {save_path}")
        plt.show()