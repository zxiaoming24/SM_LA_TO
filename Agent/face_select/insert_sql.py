"""
数据库插入模块
用于向多模态分析表插入数据
"""
import pymysql
from typing import Optional
from datetime import datetime


class DatabaseInserter:
    """数据库插入类"""
    
    def __init__(self, host: str, user: str, password: str, database: str, port: int = 3306):
        """
        初始化数据库连接
        
        Args:
            host: 数据库主机地址
            user: 数据库用户名
            password: 数据库密码
            database: 数据库名称
            port: 数据库端口，默认3306
        """
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.port = port
        self.connection = None
    
    def connect(self):
        """建立数据库连接"""
        try:
            self.connection = pymysql.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                port=self.port,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            print("数据库连接成功")
        except Exception as e:
            print(f"数据库连接失败: {e}")
            raise
    
    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            print("数据库连接已关闭")
    
    def insert_analysis_data(
        self,
        session_id: int,
        video_name: Optional[str] = None,
        type: Optional[str] = None,
        start_analysis_ts: Optional[str] = None,
        end_analysis_ts: Optional[str] = None,
        data: Optional[str] = None
    ) -> bool:
        """
        插入多模态分析数据
        
        Args:
            session_id: 学习会话ID（主键）
            video_name: 视频名称
            type: 多模态分析类型
            start_analysis_ts: 开始时间
            end_analysis_ts: 结束时间
            data: 分析结果
            
        Returns:
            bool: 插入成功返回True，失败返回False
        """
        if not self.connection:
            self.connect()
        
        sql = """
        INSERT INTO multimodal_result (session_id, video_name, type, start_analysis_ts, end_analysis_ts, data)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    sql,
                    (session_id, video_name, type, start_analysis_ts, end_analysis_ts, data)
                )
                self.connection.commit()
                print(f"数据插入成功，学习会话ID: {session_id}")
                return True
        except Exception as e:
            self.connection.rollback()
            print(f"数据插入失败: {e}")
            return False
    
    def insert_analysis_data_batch(self, data_list: list) -> int:
        """
        批量插入多模态分析数据
        
        Args:
            data_list: 数据列表，每个元素为包含session_id, video_name, type, start_analysis_ts, end_analysis_ts, data的字典
            
        Returns:
            int: 成功插入的记录数
        """
        if not self.connection:
            self.connect()
        
        sql = """
        INSERT INTO multimodal_result (session_id, video_name, type, start_analysis_ts, end_analysis_ts, data)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        success_count = 0
        try:
            with self.connection.cursor() as cursor:
                for item in data_list:
                    try:
                        cursor.execute(
                            sql,
                            (
                                item.get('session_id'),
                                item.get('video_name'),
                                item.get('type'),
                                item.get('start_analysis_ts'),
                                item.get('end_analysis_ts'),
                                item.get('data')
                            )
                        )
                        success_count += 1
                    except Exception as e:
                        print(f"记录插入失败 (session_id: {item.get('session_id')}): {e}")
                        continue
                
                self.connection.commit()
                print(f"批量插入完成，成功: {success_count}/{len(data_list)}")
        except Exception as e:
            self.connection.rollback()
            print(f"批量插入失败: {e}")
        
        return success_count
    
    def update_analysis_data(
        self,
        session_id: int,
        video_name: Optional[str] = None,
        type: Optional[str] = None,
        start_analysis_ts: Optional[str] = None,
        end_analysis_ts: Optional[str] = None,
        data: Optional[str] = None
    ) -> bool:
        """
        更新多模态分析数据
        
        Args:
            session_id: 学习会话ID（主键）
            video_name: 视频名称
            type: 多模态分析类型
            start_analysis_ts: 开始时间
            end_analysis_ts: 结束时间
            data: 分析结果
            
        Returns:
            bool: 更新成功返回True，失败返回False
        """
        if not self.connection:
            self.connect()
        
        # 构建动态更新语句
        update_fields = []
        update_values = []
        
        if type is not None:
            update_fields.append("type = %s")
            update_values.append(type)
        if video_name is not None:
            update_fields.append("video_name = %s")
            update_values.append(video_name)
        if start_analysis_ts is not None:
            update_fields.append("start_analysis_ts = %s")
            update_values.append(start_analysis_ts)
        if end_analysis_ts is not None:
            update_fields.append("end_analysis_ts = %s")
            update_values.append(end_analysis_ts)
        if data is not None:
            update_fields.append("data = %s")
            update_values.append(data)
        
        if not update_fields:
            print("没有需要更新的字段")
            return False
        
        update_values.append(session_id)
        sql = f"UPDATE multimodal_result SET {', '.join(update_fields)} WHERE session_id = %s"
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql, tuple(update_values))
                self.connection.commit()
                print(f"数据更新成功，学习会话ID: {session_id}")
                return True
        except Exception as e:
            self.connection.rollback()
            print(f"数据更新失败: {e}")
            return False

    def get_analysis_data_by_session_id(self, session_id: int) -> Optional[list]:
        """
        根据学习会话ID查询多模态分析数据

        Args:
            session_id: 学习会话ID（主键）

        Returns:
            Optional[list]: 查询结果列表，失败返回None
        """
        if not self.connection:
            self.connect()

        sql = """
        SELECT session_id, video_name, type, start_analysis_ts, end_analysis_ts, data
        FROM multimodal_result
        WHERE session_id = %s
        """

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql, (session_id,))
                results = cursor.fetchall()
                print(f"查询完成，学习会话ID: {session_id}，记录数: {len(results)}")
                return results
        except Exception as e:
            print(f"数据查询失败: {e}")
            return None

    def get_student_by_id(self, student_id: int) -> Optional[dict]:
        """
        根据学生ID查询学生档案数据

        Args:
            student_id: 学生ID（主键）

        Returns:
            Optional[dict]: 查询结果字典，失败返回None
        """
        if not self.connection:
            self.connect()

        sql = """
        SELECT *
        FROM student_profile
        WHERE student_id = %s
        """

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql, (student_id,))
                result = cursor.fetchone()
                if result:
                    print(f"查询完成，学生ID: {student_id}")
                else:
                    print(f"未找到学生ID: {student_id}")
                return result
        except Exception as e:
            print(f"学生档案查询失败: {e}")
            return None

    def get_all_students(self, limit: Optional[int] = None) -> Optional[list]:
        """
        查询所有学生档案数据

        Args:
            limit: 限制返回记录数，不传则返回所有记录

        Returns:
            Optional[list]: 查询结果列表，失败返回None
        """
        if not self.connection:
            self.connect()

        sql = "SELECT * FROM student_profile"
        if limit:
            sql += f" LIMIT {limit}"

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql)
                results = cursor.fetchall()
                print(f"查询完成，记录数: {len(results)}")
                return results
        except Exception as e:
            print(f"学生档案查询失败: {e}")
            return None


# 使用示例
if __name__ == "__main__":
    # 创建数据库插入器实例
    db = DatabaseInserter(
        host="localhost",
        user="root",
        password="root",
        database="student_learning"
    )
    
    try:
        # 连接数据库
        db.connect()
        
        # 单条插入示例
        # db.insert_analysis_data(
        #     session_id=1001,
        #     video_name="video_1001.mp4",
        #     type="面部表情分析",
        #     start_analysis_ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        #     end_analysis_ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        #     data='{"emotion": "neutral", "confidence": 0.85}'
        # )
        # db.insert_analysis_data(
        #     session_id=1002,
        #     video_name="video_1002.mp4",
        #     type="面部表情分析",
        #     start_analysis_ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        #     end_analysis_ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        #     data='{"emotion": "neutral", "confidence": 0.85}'
        # )
        
        # # 批量插入示例
        # data_list = [
        #     {
        #         "session_id": 1002,
        #         "video_name": "video_1002.mp4",
        #         "type": "语音情感分析",
        #         "start_analysis_ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        #         "end_analysis_ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        #         "data": '{"sentiment": "positive", "score": 0.75}'
        #     },
        #     {
        #         "session_id": 1003,
        #         "video_name": "video_1003.mp4",
        #         "type": "姿态分析",
        #         "start_analysis_ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        #         "end_analysis_ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        #         "data": '{"posture": "good", "confidence": 0.90}'
        #     }
        # ]
        # db.insert_analysis_data_batch(data_list)
        
        # # 更新示例
        # db.update_analysis_data(
        #     session_id=1001,
        #     video_name="video_1001_v2.mp4",
        #     end_analysis_ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        #     data='{"emotion": "happy", "confidence": 0.92}'
        # )
        import json
        print(json.loads(db.get_student_by_id(1)["content_data"]),type(json.loads(db.get_student_by_id(1)["content_data"])))
    finally:
        # 关闭连接
        db.close()
