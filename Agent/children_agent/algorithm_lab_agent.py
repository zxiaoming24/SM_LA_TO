"""
算法实验室Agent
负责为数据结构的操作生成伪代码执行步骤序列
支持：插入节点、删除节点等操作
"""

import os
import asyncio
import json
import time
from typing import Dict, Any, List, Optional
from langchain_core.prompts import PromptTemplate
from utils.llm_config import get_chat_openai


class AlgorithmLabAgent:
    """
    算法实验室Agent - 为数据结构操作生成可视化步骤序列
    支持内置数据结构 + 用户自定义数据结构
    """

    # 支持的数据结构类型
    SUPPORTED_STRUCTURES = [
        {"key": "singly_linked_list", "name": "单链表", "category": "线性结构"},
        {"key": "doubly_linked_list", "name": "双向链表", "category": "线性结构"},
        {"key": "circular_linked_list", "name": "循环链表", "category": "线性结构"},
        {"key": "stack", "name": "栈", "category": "线性结构"},
        {"key": "queue", "name": "队列", "category": "线性结构"},
        {"key": "binary_search_tree", "name": "二叉搜索树", "category": "树形结构"},
        {"key": "avl_tree", "name": "AVL平衡树", "category": "树形结构"},
        {"key": "red_black_tree", "name": "红黑树", "category": "树形结构"},
        {"key": "heap", "name": "堆", "category": "树形结构"},
        {"key": "hash_table", "name": "哈希表", "category": "哈希结构"},
        {"key": "graph_adjacency_list", "name": "图(邻接表)", "category": "图形结构"},
    ]

    # 用户自定义数据结构存储根目录
    CUSTOM_STORAGE_ROOT = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data", "algorithm_lab"
    )

    def __init__(self):
        self.llm = self._initialize_llm()
        self.operation_prompt = self._create_operation_prompt()

    # ==================== 用户自定义数据结构管理 ====================

    def _get_user_file_path(self, user_id: str) -> str:
        """获取用户自定义数据结构的文件路径"""
        user_dir = os.path.join(self.CUSTOM_STORAGE_ROOT, user_id)
        os.makedirs(user_dir, exist_ok=True)
        return os.path.join(user_dir, "custom_structures.json")

    def get_custom_structures(self, user_id: str) -> List[Dict[str, Any]]:
        """读取用户自定义数据结构列表"""
        file_path = self._get_user_file_path(user_id)
        if not os.path.exists(file_path):
            return []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("custom_structures", [])
        except (json.JSONDecodeError, IOError):
            return []

    def add_custom_structure(
        self,
        user_id: str,
        name: str,
        description: str,
        category: str = "自定义"
    ) -> Dict[str, Any]:
        """添加一个自定义数据结构"""
        if not name or not name.strip():
            return {"success": False, "message": "数据结构名称不能为空"}

        name = name.strip()
        description = (description or "").strip()
        items = self.get_custom_structures(user_id)

        # 去重检查
        for item in items:
            if item.get("name") == name:
                return {"success": False, "message": f"数据结构「{name}」已存在"}

        # 生成唯一key
        key = f"custom_{int(time.time() * 1000)}"

        new_item = {
            "key": key,
            "name": name,
            "category": category or "自定义",
            "description": description,
            "is_custom": True,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")
        }
        items.append(new_item)
        self._save_custom_structures(user_id, items)
        print(f"✅ [算法实验室Agent] 用户 {user_id} 添加自定义数据结构: {name}")
        return {"success": True, "data": new_item, "message": "添加成功"}

    def remove_custom_structure(self, user_id: str, key: str) -> Dict[str, Any]:
        """删除一个自定义数据结构"""
        items = self.get_custom_structures(user_id)
        new_items = [item for item in items if item.get("key") != key]

        if len(new_items) == len(items):
            return {"success": False, "message": f"数据结构不存在"}

        self._save_custom_structures(user_id, new_items)
        print(f"✅ [算法实验室Agent] 用户 {user_id} 删除自定义数据结构: {key}")
        return {"success": True, "message": "删除成功"}

    def _save_custom_structures(self, user_id: str, items: List[Dict[str, Any]]):
        """保存用户自定义数据结构"""
        file_path = self._get_user_file_path(user_id)
        data = {
            "user_id": user_id,
            "custom_structures": items,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_all_structures(self, user_id: str = "") -> List[Dict[str, Any]]:
        """获取内置+用户自定义合并的数据结构列表"""
        result = list(self.SUPPORTED_STRUCTURES)
        if user_id:
            custom_items = self.get_custom_structures(user_id)
            for item in custom_items:
                result.append({
                    "key": item["key"],
                    "name": item["name"],
                    "category": item.get("category", "自定义"),
                    "is_custom": True,
                    "description": item.get("description", "")
                })
        return result

    def _initialize_llm(self):
        try:
            return get_chat_openai(temperature=0.1, max_tokens=4096)
        except Exception as e:
            raise Exception(f"初始化算法实验室Agent LLM失败: {e}")

    def _create_operation_prompt(self) -> PromptTemplate:
        template = """
你是一位专业的算法可视化专家。请为「{structure_name}」的「{operation_type}」操作生成详细的步骤序列。

**操作说明：**
- 结构类型：{structure_name} ({structure_key})
- 操作类型：{operation_type}
- 操作参数：{params}
- 当前状态：{current_state}

**输出要求：**
生成一个严格的JSON格式，包含伪代码和步骤序列。

**输出格式：**
```json
{{
  "pseudocode": {{
    "title": "操作标题",
    "description": "操作描述",
    "code_lines": [
      {{"line": 1, "code": "class Node {{", "is_method": false}},
      {{"line": 2, "code": "    def __init__(self, val):", "is_method": false}},
      {{"line": 3, "code": "        self.val = val", "is_method": false}},
      {{"line": 4, "code": "        self.next = None", "is_method": false}},
      {{"line": 5, "code": "", "is_method": false}},
      {{"line": 6, "code": "class LinkedList:", "is_method": false}},
      {{"line": 7, "code": "    def __init__(self):", "is_method": false}},
      {{"line": 8, "code": "        self.head = None", "is_method": false}},
      {{"line": 9, "code": "", "is_method": false}},
      {{"line": 10, "code": "    def {operation_type}(self, data):", "is_method": true}},
      {{"line": 11, "code": "        # 创建新节点", "is_method": false}},
      {{"line": 12, "code": "        new_node = Node(data)", "is_method": false}}
    ]
  }},
  "steps": [
    {{
      "step_id": 1,
      "code_line": 12,
      "description": "创建新节点，值为 {{data}}",
      "node_changes": [
        {{"action": "create", "node_id": "new", "value": "{{data}}", "position": "calculated"}}
      ],
      "pointer_changes": [],
      "highlight_nodes": ["new"],
      "message": "创建新节点"
    }}
  ],
  "final_state": {{
    "nodes": [],
    "edges": [],
    "pointers": {{}}
  }}
}}
```

**注意：**
1. pseudocode中的code_lines是完整的类定义 + 操作方法
2. steps中的code_line对应pseudocode中的行号
3. 每个step描述执行到该行时代码时的状态变化
4. node_changes描述节点的变化（创建/删除/移动）
5. pointer_changes描述指针的变化
6. highlight_nodes描述需要高亮的节点
7. 如果无法理解具体的结构状态，请基于标准算法生成通用步骤

**请严格输出JSON格式。**
""".strip()
        return PromptTemplate.from_template(template)

    # ==================== 支持的数据结构 ====================

    def get_supported_structures(self) -> List[Dict[str, str]]:
        """获取支持的数据结构列表"""
        return self.SUPPORTED_STRUCTURES

    def get_structure_info(self, structure_key: str, user_id: str = "") -> Optional[Dict[str, Any]]:
        """获取指定数据结构的信息（支持内置和自定义）"""
        # 先查内置
        for s in self.SUPPORTED_STRUCTURES:
            if s["key"] == structure_key:
                return s
        # 再查自定义
        if user_id:
            for s in self.get_custom_structures(user_id):
                if s["key"] == structure_key:
                    return s
        return None

    def get_operations_for_structure(self, structure_key: str, user_id: str = "") -> List[Dict[str, str]]:
        """获取指定数据结构支持的操作（自定义结构返回通用操作）
        精简：只保留插入类操作（头插/尾插等），删除通过画布选中节点完成
        """
        # 自定义数据结构返回通用操作
        if structure_key.startswith("custom_"):
            return [
                {"key": "insert", "name": "插入节点", "params": ["value"]},
                {"key": "delete", "name": "删除节点", "params": ["value"]},
            ]
        ops_map = {
            "singly_linked_list": [
                {"key": "insert_at_head", "name": "头部插入", "params": ["value"]},
                {"key": "insert_at_tail", "name": "尾部插入", "params": ["value"]},
                {"key": "traverse", "name": "遍历", "params": []},
            ],
            "doubly_linked_list": [
                {"key": "insert_at_head", "name": "头部插入", "params": ["value"]},
                {"key": "insert_at_tail", "name": "尾部插入", "params": ["value"]},
                {"key": "traverse", "name": "遍历", "params": []},
            ],
            "circular_linked_list": [
                {"key": "insert_at_head", "name": "头部插入", "params": ["value"]},
                {"key": "insert_at_tail", "name": "尾部插入", "params": ["value"]},
                {"key": "traverse", "name": "遍历", "params": []},
            ],
            "stack": [
                {"key": "push", "name": "入栈", "params": ["value"]},
                {"key": "pop", "name": "出栈", "params": []},
            ],
            "queue": [
                {"key": "enqueue", "name": "入队", "params": ["value"]},
                {"key": "dequeue", "name": "出队", "params": []},
            ],
            "binary_search_tree": [
                {"key": "insert", "name": "插入节点", "params": ["value"]},
                {"key": "traverse_preorder", "name": "前序遍历", "params": []},
                {"key": "traverse_inorder", "name": "中序遍历", "params": []},
                {"key": "traverse_postorder", "name": "后序遍历", "params": []},
            ],
            "avl_tree": [
                {"key": "insert", "name": "插入节点", "params": ["value"]},
                {"key": "traverse_preorder", "name": "前序遍历", "params": []},
                {"key": "traverse_inorder", "name": "中序遍历", "params": []},
                {"key": "traverse_postorder", "name": "后序遍历", "params": []},
            ],
            "red_black_tree": [
                {"key": "insert", "name": "插入节点", "params": ["value"]},
                {"key": "traverse_preorder", "name": "前序遍历", "params": []},
                {"key": "traverse_inorder", "name": "中序遍历", "params": []},
                {"key": "traverse_postorder", "name": "后序遍历", "params": []},
            ],
            "heap": [
                {"key": "insert", "name": "插入元素", "params": ["value"]},
            ],
            "hash_table": [
                {"key": "insert", "name": "插入", "params": ["value"]},
            ],
        }
        return ops_map.get(structure_key, [])

    # ==================== 操作执行 ====================

    # 内置操作快速路径映射：structure_key -> {operation_key: handler}
    # handler 签名: (operation_type, params, current_state) -> Dict
    _BUILTIN_DISPATCH = {
        "singly_linked_list": "_singly_linked_list_operation",
        "doubly_linked_list": "_doubly_linked_list_operation",
        "circular_linked_list": "_singly_linked_list_operation",
        "stack": "_stack_operation",
        "queue": "_queue_operation",
        "binary_search_tree": "_bst_operation",
        "avl_tree": "_bst_operation",
        "red_black_tree": "_bst_operation",
        "heap": "_heap_operation",
        "hash_table": "_hash_table_operation",
    }

    # 内置操作白名单（快速路径覆盖的操作）
    _BUILTIN_OP_WHITELIST = {
        "singly_linked_list": {
            "insert_at_head", "insert_at_tail", "insert_at_position",
            "delete_at_head", "delete_at_tail", "delete_by_value",
            "traverse", "search",
        },
        "doubly_linked_list": {
            "insert_at_head", "insert_at_tail",
            "delete_at_head", "delete_at_tail", "traverse",
        },
        "circular_linked_list": {
            "insert_at_head", "insert_at_tail", "delete_at_head",
            "delete_at_tail", "delete_by_value", "traverse",
        },
        "stack": {"push", "pop", "peek"},
        "queue": {"enqueue", "dequeue", "peek"},
        "binary_search_tree": {
            "insert", "delete", "search",
            "traverse_inorder", "traverse_preorder", "traverse_postorder",
        },
        "avl_tree": {"insert", "delete", "search"},
        "red_black_tree": {"insert", "delete", "search"},
        "heap": {"insert", "delete_max", "peek_max"},
        "hash_table": {"insert", "delete", "search"},
    }

    async def execute_operation_async(
        self,
        structure_key: str,
        operation_type: str,
        params: Dict[str, Any],
        current_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行数据结构操作，生成伪代码和步骤序列。
        内置结构+内置操作 → 快速路径（直接返回状态感知的结果，不调 LLM）
        自定义结构或未覆盖的操作 → LLM 路径
        """
        structure_info = self.get_structure_info(structure_key)
        if not structure_info:
            return {
                "success": False,
                "error": f"不支持的数据结构类型: {structure_key}",
                "supported_structures": self.get_supported_structures()
            }

        operations = self.get_operations_for_structure(structure_key)
        valid_ops = [o["key"] for o in operations]
        if operation_type not in valid_ops:
            return {
                "success": False,
                "error": f"不支持的操作类型: {operation_type}",
                "valid_operations": operations
            }

        # ── 快速路径：内置结构 + 内置操作 → 直接返回状态感知结果 ──
        if (structure_key in self._BUILTIN_DISPATCH
                and structure_key in self._BUILTIN_OP_WHITELIST
                and operation_type in self._BUILTIN_OP_WHITELIST[structure_key]):
            handler_name = self._BUILTIN_DISPATCH[structure_key]
            handler = getattr(self, handler_name)
            try:
                result = handler(operation_type, params, current_state or {})
                result["success"] = True
                result["structure_key"] = structure_key
                result["structure_name"] = structure_info["name"]
                result["operation_type"] = operation_type
                return result
            except Exception as e:
                import traceback
                traceback.print_exc()

        # ── LLM 路径：自定义结构或未覆盖的操作 ──
        try:
            result = await self._generate_operation_steps(
                structure_info["key"],
                structure_info["name"],
                operation_type,
                params,
                current_state
            )
            result["success"] = True
            result["structure_key"] = structure_key
            result["structure_name"] = structure_info["name"]
            result["operation_type"] = operation_type
            return result

        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._generate_fallback_result(
                structure_key, operation_type, params, str(e)
            )

    # ==================== 自定义操作生成 ====================

    async def generate_custom_operation_async(
        self,
        structure_key: str,
        operation_description: str,
        params: Dict[str, Any],
        current_state: Optional[Dict[str, Any]] = None,
        user_id: str = ""
    ) -> Dict[str, Any]:
        """
        根据用户自定义的操作描述，使用LLM生成伪代码和步骤序列
        支持内置数据结构和用户自定义数据结构

        Args:
            structure_key: 数据结构类型（内置key或自定义key）
            operation_description: 用户描述的操作（自然语言）
            params: 操作参数
            current_state: 当前状态
            user_id: 用户ID（用于查询自定义数据结构）

        Returns:
            Dict: 包含伪代码、步骤序列、最终状态
        """
        structure_info = self.get_structure_info(structure_key, user_id)
        if not structure_info:
            return {
                "success": False,
                "error": f"不支持的数据结构类型: {structure_key}",
                "supported_structures": self.get_all_structures(user_id)
            }

        try:
            result = await self._generate_custom_steps(
                structure_info.get("key", structure_key),
                structure_info.get("name", structure_key),
                operation_description,
                params,
                current_state,
                structure_info.get("description", ""),
                structure_info.get("is_custom", False)
            )
            result["success"] = True
            result["structure_key"] = structure_key
            result["structure_name"] = structure_info["name"]
            result["operation_type"] = "custom"
            result["operation_description"] = operation_description
            return result

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": f"自定义操作生成失败: {str(e)}",
                "pseudocode": {
                    "title": f"自定义操作: {operation_description}",
                    "description": "生成失败",
                    "code_lines": [
                        {"line": 1, "code": f"# 用户描述: {operation_description}", "is_method": False},
                        {"line": 2, "code": "# 生成失败，请重试", "is_method": False},
                    ]
                },
                "steps": [],
                "final_state": current_state or {"nodes": [], "edges": [], "pointers": {}}
            }

    async def _generate_custom_steps(
        self,
        structure_key: str,
        structure_name: str,
        operation_description: str,
        params: Dict[str, Any],
        current_state: Optional[Dict[str, Any]],
        structure_description: str = "",
        is_custom_structure: bool = False
    ) -> Dict[str, Any]:
        """通过LLM生成自定义操作的伪代码和步骤"""
        # 自定义数据结构需要把结构描述传给LLM
        structure_context = structure_name
        if is_custom_structure and structure_description:
            structure_context = f"{structure_name}（用户自定义数据结构，描述：{structure_description}）"
        else:
            structure_context = f"{structure_name} ({structure_key})"

        custom_prompt = f"""
你是一位专业的算法可视化专家。请为「{structure_context}」生成一个自定义操作的伪代码和步骤序列。

**用户描述的操作：** {operation_description}

**操作参数：** {json.dumps(params, ensure_ascii=False)}
**当前状态：** {json.dumps(current_state or {{"nodes": [], "edges": [], "pointers": {{}}}}, ensure_ascii=False)}

**要求：**
1. 根据用户描述，生成完整的Python伪代码（包含类定义和操作方法）
2. 将操作分解为多个步骤，每步对应代码中的某一行
3. 每个步骤描述该行代码执行时的状态变化

**输出严格的JSON格式：**
```json
{{
  "pseudocode": {{
    "title": "操作标题",
    "description": "{operation_description}",
    "code_lines": [
      {{"line": 1, "code": "class Node:", "is_method": false}},
      {{"line": 2, "code": "    def __init__(self, val):", "is_method": false}},
      {{"line": 3, "code": "        self.val = val", "is_method": false}}
    ]
  }},
  "steps": [
    {{
      "step_id": 1,
      "code_line": 1,
      "description": "步骤描述",
      "node_changes": [],
      "pointer_changes": [],
      "highlight_nodes": [],
      "message": "提示消息"
    }}
  ],
  "final_state": {{
    "nodes": [],
    "edges": [],
    "pointers": {{}}
  }}
}}
```

**请严格输出JSON格式，不要添加其他内容。**
""".strip()

        response = await self.llm.ainvoke(custom_prompt)
        result_text = response.content if hasattr(response, 'content') else str(response)

        result_text = self._clean_json_text(result_text)

        try:
            return json.loads(result_text)
        except json.JSONDecodeError:
            print(f"⚠️ 自定义操作JSON解析失败")
            return {
                "pseudocode": {
                    "title": f"自定义操作: {operation_description}",
                    "description": operation_description,
                    "code_lines": [
                        {"line": 1, "code": f"# {operation_description}", "is_method": False},
                        {"line": 2, "code": "# 解析失败，请重试", "is_method": False},
                    ]
                },
                "steps": [],
                "final_state": current_state or {"nodes": [], "edges": [], "pointers": {}}
            }

    async def _generate_operation_steps(
        self,
        structure_key: str,
        structure_name: str,
        operation_type: str,
        params: Dict[str, Any],
        current_state: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """通过LLM生成操作步骤"""
        prompt = self.operation_prompt.format(
            structure_key=structure_key,
            structure_name=structure_name,
            operation_type=operation_type,
            params=json.dumps(params, ensure_ascii=False),
            current_state=json.dumps(current_state or {"nodes": [], "edges": []}, ensure_ascii=False)
        )

        response = await self.llm.ainvoke(prompt)
        result_text = response.content if hasattr(response, 'content') else str(response)

        # 清理并解析JSON
        result_text = self._clean_json_text(result_text)

        try:
            return json.loads(result_text)
        except json.JSONDecodeError:
            print(f"⚠️ JSON解析失败，使用降级方案")
            return self._generate_fallback_result(structure_key, operation_type, params, "JSON解析失败")

    def _clean_json_text(self, text: str) -> str:
        """清理LLM返回的JSON文本"""
        import re
        # 去除markdown代码块标记
        text = re.sub(r'^```(?:json)?\s*', '', text.strip())
        text = re.sub(r'\s*```$', '', text)

        # 尝试提取JSON对象
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            text = json_match.group()

        # 清理尾逗号
        text = re.sub(r',\s*}', '}', text)
        text = re.sub(r',\s*]', ']', text)

        return text.strip()

    # ==================== 降级方案 ====================

    def _generate_fallback_result(
        self,
        structure_key: str,
        operation_type: str,
        params: Dict[str, Any],
        error_msg: str
    ) -> Dict[str, Any]:
        """降级方案：生成基础操作步骤"""
        result = self._get_builtin_operation(structure_key, operation_type, params)
        result["_fallback"] = True
        result["_error"] = error_msg
        return result

    def _get_builtin_operation(
        self,
        structure_key: str,
        operation_type: str,
        params: Dict[str, Any],
        current_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """获取内置的操作步骤（状态感知）"""
        cs = current_state or {}
        if structure_key == "singly_linked_list" or structure_key == "circular_linked_list":
            return self._singly_linked_list_operation(operation_type, params, cs)
        if structure_key == "doubly_linked_list":
            return self._doubly_linked_list_operation(operation_type, params, cs)
        if structure_key == "stack":
            return self._stack_operation(operation_type, params, cs)
        if structure_key == "queue":
            return self._queue_operation(operation_type, params, cs)
        if structure_key in ("binary_search_tree", "avl_tree", "red_black_tree"):
            return self._bst_operation(operation_type, params, cs)
        if structure_key == "heap":
            return self._heap_operation(operation_type, params, cs)
        if structure_key == "hash_table":
            return self._hash_table_operation(operation_type, params, cs)
        return self._get_basic_result(operation_type, params.get("value"))

    # ── 状态工具 ──
    @staticmethod
    def _clone_state(state: Dict[str, Any]) -> Dict[str, Any]:
        import copy
        return copy.deepcopy({
            "nodes": state.get("nodes", []),
            "edges": state.get("edges", []),
            "pointers": state.get("pointers", {}) or {},
        })

    @staticmethod
    def _new_node_id(state: Dict[str, Any]) -> str:
        import time
        return f"node_{int(time.time() * 1000) % 1000000}_{len(state.get('nodes', []))}"

    @staticmethod
    def _next_pos_linear(state: Dict[str, Any], base_x: float = 100, dx: float = 110, y: float = 180) -> tuple:
        nodes = state.get("nodes", [])
        if not nodes:
            return base_x, y
        last = max(nodes, key=lambda n: n.get("position_x", 0))
        return last.get("position_x", base_x) + dx, y

    # ==================== 单链表 / 循环链表 ====================
    def _singly_linked_list_operation(self, operation_type: str, params: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        val = params.get("value", 1)
        try:
            val = int(val)
        except Exception:
            val = 1
        ns = self._clone_state(state)
        nodes = ns["nodes"]
        edges = ns["edges"]
        ptrs = ns["pointers"]
        head_id = ptrs.get("head")

        if operation_type == "insert_at_head":
            new_id = self._new_node_id(ns)
            min_x = min(n.get("position_x", 100) for n in nodes) if nodes else 400
            base_x = max(60, min_x - 110)
            new_node = {"id": new_id, "value": val, "position_x": base_x, "position_y": 180}
            steps = [
                {"step_id": 1, "code_line": 12, "description": f"创建新节点，值为 {val}",
                 "node_changes": [{"action": "create", "node_id": new_id, "value": val}],
                 "highlight_nodes": [new_id], "message": "创建新节点"},
                {"step_id": 2, "code_line": 14, "description": "新节点.next 指向原 head",
                 "node_changes": [{"action": "link", "from": new_id, "to": head_id}] if head_id else [],
                 "highlight_nodes": [new_id] + ([head_id] if head_id else []), "message": "建立链接"},
                {"step_id": 3, "code_line": 16, "description": "head 指向新节点",
                 "pointer_changes": [{"pointer": "head", "target": new_id}],
                 "highlight_nodes": [new_id], "message": "更新头部"},
            ]
            nodes.insert(0, new_node)
            if head_id:
                edges.append({"from": new_id, "to": head_id})
            ptrs["head"] = new_id
            return self._pack("单链表 - 头部插入", "在链表头部插入新节点",
                              ["class Node:", "    def __init__(self, val):", "        self.val = val",
                               "        self.next = None", "", "class LinkedList:",
                               "    def __init__(self):", "        self.head = None", "",
                               "    def insert_at_head(self, val):", "        # 创建新节点",
                               "        new_node = Node(val)", "        # 新节点指向原头部",
                               "        new_node.next = self.head", "        # 更新头部指针",
                               "        self.head = new_node", "        return new_node"], 12, steps, ns)

        if operation_type == "insert_at_tail":
            new_id = self._new_node_id(ns)
            if not nodes:
                new_node = {"id": new_id, "value": val, "position_x": 100, "position_y": 180}
                nodes.append(new_node)
                ptrs["head"] = new_id
                steps = [{"step_id": 1, "code_line": 14, "description": f"链表为空，新节点({val})成为 head",
                          "node_changes": [{"action": "create", "node_id": new_id, "value": val}],
                          "pointer_changes": [{"pointer": "head", "target": new_id}],
                          "highlight_nodes": [new_id], "message": "空表插入"}]
                return self._pack("单链表 - 尾部插入", "在链表尾部插入新节点",
                                  ["class LinkedList:", "    def insert_at_tail(self, val):",
                                   "        if not self.head:", "            self.head = Node(val)",
                                   "            return", "        cur = self.head",
                                   "        while cur.next:", "            cur = cur.next",
                                   "        cur.next = Node(val)"], 14, steps, ns)
            # 找尾节点
            child_map = {}
            for e in edges:
                child_map[e["from"]] = e["to"]
            tail_id = head_id
            visited = set()
            while child_map.get(tail_id) and tail_id not in visited:
                visited.add(tail_id)
                tail_id = child_map[tail_id]
            tail_node = next((n for n in nodes if n["id"] == tail_id), None)
            tx, ty = self._next_pos_linear(ns)
            new_node = {"id": new_id, "value": val, "position_x": tx, "position_y": ty}
            steps = [
                {"step_id": 1, "code_line": 8, "description": f"从 head 开始遍历到尾节点",
                 "highlight_nodes": [head_id], "message": "遍历找尾"},
                {"step_id": 2, "code_line": 11, "description": f"尾节点({tail_node['value'] if tail_node else '?'}).next 指向新节点({val})",
                 "node_changes": [{"action": "link", "from": tail_id, "to": new_id}],
                 "highlight_nodes": [tail_id, new_id], "message": "链接新节点"},
                {"step_id": 3, "code_line": 11, "description": f"新节点({val})已挂到尾部",
                 "node_changes": [{"action": "create", "node_id": new_id, "value": val}],
                 "highlight_nodes": [new_id], "message": "插入完成"},
            ]
            nodes.append(new_node)
            edges.append({"from": tail_id, "to": new_id})
            return self._pack("单链表 - 尾部插入", "在链表尾部插入新节点",
                              ["class LinkedList:", "    def insert_at_tail(self, val):",
                               "        if not self.head:", "            self.head = Node(val)",
                               "            return", "        cur = self.head",
                               "        while cur.next:", "            cur = cur.next",
                               "        cur.next = Node(val)"], 8, steps, ns)

        if operation_type == "delete_at_head":
            if not head_id:
                return self._empty_err("链表为空，无法删除头节点")
            head_node = next((n for n in nodes if n["id"] == head_id), None)
            next_edge = next((e for e in edges if e["from"] == head_id), None)
            next_id = next_edge["to"] if next_edge else None
            steps = [
                {"step_id": 1, "code_line": 4, "description": f"记录 head 节点值({head_node['value'] if head_node else '?'})",
                 "highlight_nodes": [head_id], "message": "记录头节点"},
                {"step_id": 2, "code_line": 5, "description": "head = head.next",
                 "pointer_changes": [{"pointer": "head", "target": next_id}],
                 "highlight_nodes": [head_id] + ([next_id] if next_id else []), "message": "移动头指针"},
                {"step_id": 3, "code_line": 6, "description": "返回被删除的值",
                 "node_changes": [{"action": "delete", "node_id": head_id}],
                 "highlight_nodes": [], "message": "删除完成"},
            ]
            nodes[:] = [n for n in nodes if n["id"] != head_id]
            edges[:] = [e for e in edges if e["from"] != head_id and e["to"] != head_id]
            if next_id:
                ptrs["head"] = next_id
            else:
                ptrs.pop("head", None)
            return self._pack("单链表 - 头部删除", "删除链表头节点",
                              ["class LinkedList:", "    def delete_at_head(self):",
                               "        if not self.head:", "            return None",
                               "        val = self.head.val", "        self.head = self.head.next",
                               "        return val"], 4, steps, ns)

        if operation_type == "delete_at_tail":
            if not head_id:
                return self._empty_err("链表为空，无法删除尾节点")
            # 找倒数第二个节点
            child_map = {}
            for e in edges:
                child_map[e["from"]] = e["to"]
            prev_id = None
            cur_id = head_id
            tail_id = head_id
            visited = set()
            while child_map.get(cur_id) and cur_id not in visited:
                visited.add(cur_id)
                prev_id = cur_id
                cur_id = child_map[cur_id]
                tail_id = cur_id
            tail_node = next((n for n in nodes if n["id"] == tail_id), None)
            steps = [
                {"step_id": 1, "code_line": 6, "description": "遍历到尾节点的前驱",
                 "highlight_nodes": [head_id, tail_id], "message": "遍历找尾"},
                {"step_id": 2, "code_line": 8, "description": f"前驱.next = None，断开尾节点({tail_node['value'] if tail_node else '?'})",
                 "node_changes": [{"action": "unlink", "from": prev_id, "to": tail_id}] if prev_id else [],
                 "highlight_nodes": [tail_id], "message": "断开链接"},
                {"step_id": 3, "code_line": 9, "description": "删除尾节点",
                 "node_changes": [{"action": "delete", "node_id": tail_id}],
                 "highlight_nodes": [], "message": "删除完成"},
            ]
            nodes[:] = [n for n in nodes if n["id"] != tail_id]
            edges[:] = [e for e in edges if e["from"] != tail_id and e["to"] != tail_id]
            if prev_id:
                edges[:] = [e for e in edges if not (e["from"] == prev_id and e["to"] == tail_id)]
            elif head_id == tail_id:
                ptrs.pop("head", None)
            return self._pack("单链表 - 尾部删除", "删除链表尾节点",
                              ["class LinkedList:", "    def delete_at_tail(self):",
                               "        if not self.head:", "            return None",
                               "        if not self.head.next:", "            val = self.head.val",
                               "            self.head = None", "            return val",
                               "        prev = self.head", "        while prev.next.next:",
                               "            prev = prev.next", "        val = prev.next.val",
                               "        prev.next = None", "        return val"], 6, steps, ns)

        if operation_type == "delete_by_value":
            target_val = val
            target_node_id = params.get("node_id")
            # 找目标节点及其前驱
            child_map = {}
            for e in edges:
                child_map[e["from"]] = e["to"]
            prev_id = None
            cur_id = head_id
            target_id = None
            visited = set()
            while cur_id and cur_id not in visited:
                visited.add(cur_id)
                cur_node = next((n for n in nodes if n["id"] == cur_id), None)
                # 优先按 node_id 精确匹配，否则按 value 匹配
                if target_node_id:
                    if cur_id == target_node_id:
                        target_id = cur_id
                        break
                elif cur_node and cur_node.get("value") == target_val:
                    target_id = cur_id
                    break
                prev_id = cur_id
                cur_id = child_map.get(cur_id)
            if not target_id:
                steps = [{"step_id": 1, "code_line": 4, "description": f"遍历链表，未找到值 {target_val}",
                          "highlight_nodes": [head_id] if head_id else [], "message": "未找到"}]
                return self._pack("单链表 - 按值删除", "删除指定值的节点",
                                  ["class LinkedList:", "    def delete_by_value(self, val):",
                                   "        if not self.head:", "            return False",
                                   "        if self.head.val == val:", "            self.head = self.head.next",
                                   "            return True", "        prev = self.head",
                                   "        while prev.next:", "            if prev.next.val == val:",
                                   "                prev.next = prev.next.next", "                return True",
                                   "            prev = prev.next", "        return False"], 4, steps, ns)
            target_node = next((n for n in nodes if n["id"] == target_id), None)
            next_edge = next((e for e in edges if e["from"] == target_id), None)
            next_id = next_edge["to"] if next_edge else None
            steps = [
                {"step_id": 1, "code_line": 8, "description": f"遍历找到目标节点({target_val})",
                 "highlight_nodes": [target_id], "message": "找到目标"},
                {"step_id": 2, "code_line": 10, "description": "前驱.next = 目标.next（跳过目标）",
                 "node_changes": [{"action": "link", "from": prev_id, "to": next_id}] if prev_id and next_id else
                                 [{"action": "unlink", "from": prev_id, "to": target_id}] if prev_id else [],
                 "pointer_changes": [{"pointer": "head", "target": next_id}] if not prev_id else [],
                 "highlight_nodes": [target_id] + ([prev_id] if prev_id else []) + ([next_id] if next_id else []),
                 "message": "跳过目标节点"},
                {"step_id": 3, "code_line": 11, "description": "删除目标节点",
                 "node_changes": [{"action": "delete", "node_id": target_id}],
                 "highlight_nodes": [], "message": "删除完成"},
            ]
            nodes[:] = [n for n in nodes if n["id"] != target_id]
            edges[:] = [e for e in edges if e["from"] != target_id and e["to"] != target_id]
            if prev_id and next_id:
                edges.append({"from": prev_id, "to": next_id})
            if not prev_id:
                ptrs["head"] = next_id if next_id else None
                if not next_id:
                    ptrs.pop("head", None)
            return self._pack("单链表 - 按值删除", "删除指定值的节点",
                              ["class LinkedList:", "    def delete_by_value(self, val):",
                               "        if not self.head:", "            return False",
                               "        if self.head.val == val:", "            self.head = self.head.next",
                               "            return True", "        prev = self.head",
                               "        while prev.next:", "            if prev.next.val == val:",
                               "                prev.next = prev.next.next", "                return True",
                               "            prev = prev.next", "        return False"], 8, steps, ns)

        if operation_type == "traverse":
            visited_ids = []
            child_map = {}
            for e in edges:
                child_map[e["from"]] = e["to"]
            cur_id = head_id
            seen = set()
            while cur_id and cur_id not in seen:
                seen.add(cur_id)
                visited_ids.append(cur_id)
                cur_id = child_map.get(cur_id)
            steps = [{"step_id": i + 1, "code_line": 4,
                      "description": f"访问节点 {next((n['value'] for n in nodes if n['id'] == nid), '?')}",
                      "highlight_nodes": [nid], "message": f"访问第 {i+1} 个节点"}
                     for i, nid in enumerate(visited_ids)]
            return self._pack("单链表 - 遍历", "从头到尾遍历链表",
                              ["class LinkedList:", "    def traverse(self):",
                               "        cur = self.head", "        while cur:",
                               "            print(cur.val)", "            cur = cur.next"], 4, steps, ns)

        if operation_type == "search":
            target_val = val
            child_map = {}
            for e in edges:
                child_map[e["from"]] = e["to"]
            cur_id = head_id
            found_id = None
            idx = 0
            seen = set()
            steps = []
            while cur_id and cur_id not in seen:
                seen.add(cur_id)
                cur_node = next((n for n in nodes if n["id"] == cur_id), None)
                cv = cur_node.get("value") if cur_node else "?"
                steps.append({"step_id": idx + 1, "code_line": 5,
                              "description": f"比较 cur.val({cv}) == {target_val}?",
                              "highlight_nodes": [cur_id], "message": f"第 {idx+1} 步比较"})
                if cv == target_val:
                    found_id = cur_id
                    steps.append({"step_id": idx + 2, "code_line": 6,
                                  "description": f"找到目标！返回位置 {idx}",
                                  "highlight_nodes": [cur_id], "message": "查找成功"})
                    break
                cur_id = child_map.get(cur_id)
                idx += 1
            if not found_id and steps:
                steps.append({"step_id": len(steps) + 1, "code_line": 8,
                              "description": f"未找到值 {target_val}",
                              "highlight_nodes": [], "message": "查找失败"})
            elif not steps:
                steps = [{"step_id": 1, "code_line": 3, "description": "链表为空",
                          "highlight_nodes": [], "message": "空链表"}]
            return self._pack("单链表 - 查找", "按值查找节点",
                              ["class LinkedList:", "    def search(self, val):",
                               "        cur = self.head", "        idx = 0",
                               "        while cur:", "            if cur.val == val:",
                               "                return idx", "            cur = cur.next",
                               "            idx += 1", "        return -1"], 5, steps, ns)

        if operation_type == "insert_at_position":
            pos = int(params.get("position", 0))
            new_id = self._new_node_id(ns)
            if pos <= 0 or not head_id:
                return self._singly_linked_list_operation("insert_at_head", params, state)
            child_map = {}
            for e in edges:
                child_map[e["from"]] = e["to"]
            cur_id = head_id
            prev_id = None
            for i in range(pos):
                prev_id = cur_id
                cur_id = child_map.get(cur_id)
                if not cur_id:
                    break
            if not cur_id:
                return self._singly_linked_list_operation("insert_at_tail", params, state)
            prev_node = next((n for n in nodes if n["id"] == prev_id), None)
            px = prev_node["position_x"] + 110 if prev_node else 100
            py = prev_node.get("position_y", 180) if prev_node else 180
            new_node = {"id": new_id, "value": val, "position_x": px, "position_y": py}
            steps = [
                {"step_id": 1, "code_line": 6, "description": f"遍历到位置 {pos} 的前驱",
                 "highlight_nodes": [prev_id, cur_id], "message": "定位插入点"},
                {"step_id": 2, "code_line": 8, "description": f"新节点({val}).next = 前驱.next",
                 "node_changes": [{"action": "link", "from": new_id, "to": cur_id}],
                 "highlight_nodes": [new_id, cur_id], "message": "新节点指向后继"},
                {"step_id": 3, "code_line": 9, "description": f"前驱.next = 新节点",
                 "node_changes": [{"action": "link", "from": prev_id, "to": new_id}],
                 "highlight_nodes": [prev_id, new_id], "message": "前驱指向新节点"},
            ]
            nodes.append(new_node)
            edges[:] = [e for e in edges if not (e["from"] == prev_id and e["to"] == cur_id)]
            edges.append({"from": prev_id, "to": new_id})
            edges.append({"from": new_id, "to": cur_id})
            return self._pack("单链表 - 指定位置插入", "在指定位置插入节点",
                              ["class LinkedList:", "    def insert_at_position(self, pos, val):",
                               "        if pos <= 0:", "            return self.insert_at_head(val)",
                               "        prev = self.head", "        for _ in range(pos - 1):",
                               "            if not prev:", "                return self.insert_at_tail(val)",
                               "            prev = prev.next", "        new_node = Node(val)",
                               "        new_node.next = prev.next", "        prev.next = new_node"], 6, steps, ns)

        return self._get_basic_result(operation_type, val)

    # ==================== 双链表 ====================
    def _doubly_linked_list_operation(self, operation_type: str, params: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        val = int(params.get("value", 1) or 1)
        ns = self._clone_state(state)
        nodes, edges, ptrs = ns["nodes"], ns["edges"], ns["pointers"]
        head_id = ptrs.get("head")

        if operation_type == "insert_at_head":
            new_id = self._new_node_id(ns)
            min_x = min(n.get("position_x", 100) for n in nodes) if nodes else 400
            bx = max(60, min_x - 110)
            new_node = {"id": new_id, "value": val, "position_x": bx, "position_y": 180}
            steps = [
                {"step_id": 1, "code_line": 11, "description": f"创建新节点({val})",
                 "node_changes": [{"action": "create", "node_id": new_id, "value": val}],
                 "highlight_nodes": [new_id], "message": "创建节点"},
                {"step_id": 2, "code_line": 12, "description": "new.next = head",
                 "node_changes": [{"action": "link", "from": new_id, "to": head_id}] if head_id else [],
                 "highlight_nodes": [new_id] + ([head_id] if head_id else []), "message": "next 指向原头"},
                {"step_id": 3, "code_line": 13, "description": "head.prev = new（双向）" if head_id else "head 为空，跳过",
                 "node_changes": [{"action": "link", "from": head_id, "to": new_id, "type": "prev"}] if head_id else [],
                 "highlight_nodes": [head_id, new_id] if head_id else [new_id], "message": "prev 反向指向"},
                {"step_id": 4, "code_line": 14, "description": "head = new",
                 "pointer_changes": [{"pointer": "head", "target": new_id}],
                 "highlight_nodes": [new_id], "message": "更新头指针"},
            ]
            nodes.insert(0, new_node)
            if head_id:
                edges.append({"from": new_id, "to": head_id})
                edges.append({"from": head_id, "to": new_id, "type": "prev"})
            ptrs["head"] = new_id
            return self._pack("双链表 - 头部插入", "双向链表头部插入",
                              ["class DNode:", "    def __init__(self, val):", "        self.val = val",
                               "        self.prev = None", "        self.next = None", "",
                               "class DLinkedList:", "    def __init__(self):", "        self.head = None", "",
                               "    def insert_at_head(self, val):", "        new_node = DNode(val)",
                               "        new_node.next = self.head", "        if self.head:",
                               "            self.head.prev = new_node", "        self.head = new_node"], 11, steps, ns)

        if operation_type == "insert_at_tail":
            new_id = self._new_node_id(ns)
            if not head_id:
                return self._doubly_linked_list_operation("insert_at_head", params, state)
            child_map = {e["from"]: e["to"] for e in edges if e.get("type") != "prev"}
            tail_id = head_id
            seen = set()
            while child_map.get(tail_id) and tail_id not in seen:
                seen.add(tail_id)
                tail_id = child_map[tail_id]
            tx, ty = self._next_pos_linear(ns)
            new_node = {"id": new_id, "value": val, "position_x": tx, "position_y": ty}
            steps = [
                {"step_id": 1, "code_line": 7, "description": "遍历到尾节点",
                 "highlight_nodes": [head_id, tail_id], "message": "找尾"},
                {"step_id": 2, "code_line": 9, "description": f"tail.next = new({val})",
                 "node_changes": [{"action": "link", "from": tail_id, "to": new_id}],
                 "highlight_nodes": [tail_id, new_id], "message": "尾节点next指向新"},
                {"step_id": 3, "code_line": 10, "description": "new.prev = tail（双向）",
                 "node_changes": [{"action": "link", "from": new_id, "to": tail_id, "type": "prev"}],
                 "highlight_nodes": [new_id, tail_id], "message": "新节点prev指向尾"},
            ]
            nodes.append(new_node)
            edges.append({"from": tail_id, "to": new_id})
            edges.append({"from": new_id, "to": tail_id, "type": "prev"})
            return self._pack("双链表 - 尾部插入", "双向链表尾部插入",
                              ["class DLinkedList:", "    def insert_at_tail(self, val):",
                               "        if not self.head:", "            return self.insert_at_head(val)",
                               "        cur = self.head", "        while cur.next:",
                               "            cur = cur.next", "        new_node = DNode(val)",
                               "        cur.next = new_node", "        new_node.prev = cur"], 7, steps, ns)

        if operation_type == "delete_at_head":
            if not head_id:
                return self._empty_err("双链表为空")
            next_edge = next((e for e in edges if e["from"] == head_id and e.get("type") != "prev"), None)
            next_id = next_edge["to"] if next_edge else None
            head_node = next((n for n in nodes if n["id"] == head_id), None)
            steps = [
                {"step_id": 1, "code_line": 4, "description": f"记录 head({head_node['value'] if head_node else '?'})",
                 "highlight_nodes": [head_id], "message": "记录头"},
                {"step_id": 2, "code_line": 5, "description": "head = head.next",
                 "pointer_changes": [{"pointer": "head", "target": next_id}],
                 "highlight_nodes": [head_id] + ([next_id] if next_id else []), "message": "移动头指针"},
                {"step_id": 3, "code_line": 6, "description": "head.prev = None（断开反向）" if next_id else "无后继",
                 "node_changes": [{"action": "unlink", "from": next_id, "to": head_id, "type": "prev"}] if next_id else [],
                 "highlight_nodes": [next_id] if next_id else [], "message": "断开prev"},
                {"step_id": 4, "code_line": 7, "description": "返回被删值",
                 "node_changes": [{"action": "delete", "node_id": head_id}],
                 "highlight_nodes": [], "message": "删除完成"},
            ]
            nodes[:] = [n for n in nodes if n["id"] != head_id]
            edges[:] = [e for e in edges if e["from"] != head_id and e["to"] != head_id]
            ptrs["head"] = next_id if next_id else None
            if not next_id:
                ptrs.pop("head", None)
            return self._pack("双链表 - 头部删除", "双向链表头部删除",
                              ["class DLinkedList:", "    def delete_at_head(self):",
                               "        if not self.head:", "            return None",
                               "        val = self.head.val", "        self.head = self.head.next",
                               "        if self.head:", "            self.head.prev = None",
                               "        return val"], 4, steps, ns)

        if operation_type == "delete_at_tail":
            if not head_id:
                return self._empty_err("双链表为空")
            child_map = {e["from"]: e["to"] for e in edges if e.get("type") != "prev"}
            tail_id = head_id
            seen = set()
            while child_map.get(tail_id) and tail_id not in seen:
                seen.add(tail_id)
                tail_id = child_map[tail_id]
            prev_edge = next((e for e in edges if e["from"] == tail_id and e.get("type") == "prev"), None)
            prev_id = prev_edge["to"] if prev_edge else None
            tail_node = next((n for n in nodes if n["id"] == tail_id), None)
            steps = [
                {"step_id": 1, "code_line": 6, "description": "通过 prev 找尾节点",
                 "highlight_nodes": [tail_id], "message": "定位尾节点"},
                {"step_id": 2, "code_line": 8, "description": f"tail.prev.next = None" if prev_id else "tail 即 head",
                 "node_changes": [{"action": "unlink", "from": prev_id, "to": tail_id}] if prev_id else [],
                 "pointer_changes": [{"pointer": "head", "target": None}] if not prev_id else [],
                 "highlight_nodes": [tail_id] + ([prev_id] if prev_id else []), "message": "断开前驱链接"},
                {"step_id": 3, "code_line": 9, "description": "删除尾节点",
                 "node_changes": [{"action": "delete", "node_id": tail_id}],
                 "highlight_nodes": [], "message": "删除完成"},
            ]
            nodes[:] = [n for n in nodes if n["id"] != tail_id]
            edges[:] = [e for e in edges if e["from"] != tail_id and e["to"] != tail_id]
            if not prev_id:
                ptrs.pop("head", None)
            return self._pack("双链表 - 尾部删除", "双向链表尾部删除",
                              ["class DLinkedList:", "    def delete_at_tail(self):",
                               "        if not self.head:", "            return None",
                               "        if not self.head.next:", "            val = self.head.val",
                               "            self.head = None", "            return val",
                               "        tail = self.head", "        while tail.next:",
                               "            tail = tail.next", "        tail.prev.next = None",
                               "        return tail.val"], 6, steps, ns)

        if operation_type == "traverse":
            child_map = {e["from"]: e["to"] for e in edges if e.get("type") != "prev"}
            ids = []
            cur = head_id
            seen = set()
            while cur and cur not in seen:
                seen.add(cur)
                ids.append(cur)
                cur = child_map.get(cur)
            steps = [{"step_id": i + 1, "code_line": 4,
                      "description": f"访问 {next((n['value'] for n in nodes if n['id'] == nid), '?')}",
                      "highlight_nodes": [nid], "message": f"第 {i+1} 个"} for i, nid in enumerate(ids)]
            return self._pack("双链表 - 遍历", "双向链表遍历",
                              ["class DLinkedList:", "    def traverse(self):",
                               "        cur = self.head", "        while cur:",
                               "            print(cur.val)", "            cur = cur.next"], 4, steps, ns)

        return self._get_basic_result(operation_type, val)

    # ==================== 栈 ====================
    def _stack_operation(self, operation_type: str, params: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        val = int(params.get("value", 1) or 1)
        ns = self._clone_state(state)
        nodes, ptrs = ns["nodes"], ns["pointers"]
        top_id = ptrs.get("top")

        if operation_type == "push":
            new_id = self._new_node_id(ns)
            top_node = next((n for n in nodes if n["id"] == top_id), None) if top_id else None
            ny = (top_node["position_y"] - 50) if top_node else 280
            nx = top_node["position_x"] if top_node else 200
            new_node = {"id": new_id, "value": val, "position_x": nx, "position_y": ny}
            steps = [
                {"step_id": 1, "code_line": 6, "description": f"将 {val} append 到栈顶",
                 "node_changes": [{"action": "create", "node_id": new_id, "value": val}],
                 "highlight_nodes": [new_id], "message": "入栈"},
                {"step_id": 2, "code_line": 6, "description": "top 指向新栈顶",
                 "pointer_changes": [{"pointer": "top", "target": new_id}],
                 "highlight_nodes": [new_id], "message": "更新栈顶"},
            ]
            nodes.append(new_node)
            ptrs["top"] = new_id
            return self._pack("栈 - 入栈", "push 操作",
                              ["class Stack:", "    def __init__(self):", "        self.stack = []", "",
                               "    def push(self, val):", "        self.stack.append(val)",
                               "        return True"], 6, steps, ns)

        if operation_type == "pop":
            if not top_id:
                return self._empty_err("栈为空，无法 pop")
            top_node = next((n for n in nodes if n["id"] == top_id), None)
            top_y = top_node["position_y"] if top_node else 0
            # 找紧邻 top 下面的节点（position_y 最接近且大于 top_y 的）
            candidates = [n for n in nodes if n["id"] != top_id and n.get("position_y", 0) > top_y]
            below = min(candidates, key=lambda n: n["position_y"]) if candidates else None
            below_id = below["id"] if below else None
            steps = [
                {"step_id": 1, "code_line": 3, "description": "检查栈非空",
                 "highlight_nodes": [top_id], "message": "栈非空"},
                {"step_id": 2, "code_line": 4, "description": f"弹出栈顶({top_node['value'] if top_node else '?'})",
                 "node_changes": [{"action": "delete", "node_id": top_id}],
                 "pointer_changes": [{"pointer": "top", "target": below_id}],
                 "highlight_nodes": [], "message": "出栈"},
            ]
            nodes[:] = [n for n in nodes if n["id"] != top_id]
            if below_id:
                ptrs["top"] = below_id
            else:
                ptrs.pop("top", None)
            return self._pack("栈 - 出栈", "pop 操作",
                              ["class Stack:", "    def pop(self):", "        if not self.stack:",
                               "            return None", "        return self.stack.pop()"], 4, steps, ns)

        if operation_type == "peek":
            if not top_id:
                return self._empty_err("栈为空")
            top_node = next((n for n in nodes if n["id"] == top_id), None)
            steps = [{"step_id": 1, "code_line": 3, "description": f"返回栈顶值({top_node['value'] if top_node else '?'})，不删除",
                      "highlight_nodes": [top_id], "message": "查看栈顶"}]
            return self._pack("栈 - 查看栈顶", "peek 操作",
                              ["class Stack:", "    def peek(self):", "        if not self.stack:",
                               "            return None", "        return self.stack[-1]"], 3, steps, ns)

        return self._get_basic_result(operation_type, val)

    # ==================== 队列 ====================
    def _queue_operation(self, operation_type: str, params: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        val = int(params.get("value", 1) or 1)
        ns = self._clone_state(state)
        nodes, ptrs = ns["nodes"], ns["pointers"]
        front_id = ptrs.get("front")
        rear_id = ptrs.get("rear")

        if operation_type == "enqueue":
            new_id = self._new_node_id(ns)
            rear_node = next((n for n in nodes if n["id"] == rear_id), None) if rear_id else None
            rx = (rear_node["position_x"] + 100) if rear_node else 80
            ry = rear_node.get("position_y", 180) if rear_node else 180
            new_node = {"id": new_id, "value": val, "position_x": rx, "position_y": ry}
            steps = [
                {"step_id": 1, "code_line": 6, "description": f"将 {val} 加入队尾",
                 "node_changes": [{"action": "create", "node_id": new_id, "value": val}],
                 "highlight_nodes": [new_id], "message": "入队"},
                {"step_id": 2, "code_line": 6, "description": "rear 指向新队尾",
                 "pointer_changes": [{"pointer": "rear", "target": new_id}],
                 "highlight_nodes": [new_id], "message": "更新队尾"},
            ]
            nodes.append(new_node)
            ptrs["rear"] = new_id
            if not front_id:
                ptrs["front"] = new_id
            return self._pack("队列 - 入队", "enqueue 操作",
                              ["class Queue:", "    def __init__(self):", "        self.queue = []", "",
                               "    def enqueue(self, val):", "        self.queue.append(val)",
                               "        return True"], 6, steps, ns)

        if operation_type == "dequeue":
            if not front_id:
                return self._empty_err("队列为空，无法 dequeue")
            front_node = next((n for n in nodes if n["id"] == front_id), None)
            front_x = front_node["position_x"] if front_node else 0
            # 找紧邻 front 右边的节点（position_x 最接近且大于 front_x 的）
            candidates = [n for n in nodes if n["id"] != front_id and n.get("position_x", 0) > front_x]
            nxt = min(candidates, key=lambda n: n["position_x"]) if candidates else None
            nxt_id = nxt["id"] if nxt else None
            steps = [
                {"step_id": 1, "code_line": 3, "description": "检查队列非空",
                 "highlight_nodes": [front_id], "message": "队列非空"},
                {"step_id": 2, "code_line": 4, "description": f"移除队首({front_node['value'] if front_node else '?'})",
                 "node_changes": [{"action": "delete", "node_id": front_id}],
                 "pointer_changes": [{"pointer": "front", "target": nxt_id}],
                 "highlight_nodes": [], "message": "出队"},
            ]
            nodes[:] = [n for n in nodes if n["id"] != front_id]
            if nxt_id:
                ptrs["front"] = nxt_id
            else:
                ptrs.pop("front", None)
                ptrs.pop("rear", None)
            return self._pack("队列 - 出队", "dequeue 操作",
                              ["class Queue:", "    def dequeue(self):", "        if not self.queue:",
                               "            return None", "        return self.queue.pop(0)"], 4, steps, ns)

        if operation_type == "peek":
            if not front_id:
                return self._empty_err("队列为空")
            front_node = next((n for n in nodes if n["id"] == front_id), None)
            steps = [{"step_id": 1, "code_line": 3, "description": f"返回队首({front_node['value'] if front_node else '?'})，不删除",
                      "highlight_nodes": [front_id], "message": "查看队首"}]
            return self._pack("队列 - 查看队首", "peek 操作",
                              ["class Queue:", "    def peek(self):", "        if not self.queue:",
                               "            return None", "        return self.queue[0]"], 3, steps, ns)

        return self._get_basic_result(operation_type, val)

    # ==================== 二叉搜索树 ====================
    def _bst_operation(self, operation_type: str, params: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        val = int(params.get("value", 10) or 10)
        ns = self._clone_state(state)
        nodes, edges, ptrs = ns["nodes"], ns["edges"], ns["pointers"]
        root_id = ptrs.get("root")

        if operation_type == "insert":
            new_id = self._new_node_id(ns)
            if not root_id:
                new_node = {"id": new_id, "value": val, "position_x": 400, "position_y": 80}
                nodes.append(new_node)
                ptrs["root"] = new_id
                steps = [{"step_id": 1, "code_line": 16, "description": f"树为空，新节点({val})成为 root",
                          "node_changes": [{"action": "create", "node_id": new_id, "value": val}],
                          "pointer_changes": [{"pointer": "root", "target": new_id}],
                          "highlight_nodes": [new_id], "message": "插入为根"}]
                return self._pack("BST - 插入", "插入节点到 BST",
                                  ["class TreeNode:", "    def __init__(self, val):", "        self.val = val",
                                   "        self.left = None", "        self.right = None", "",
                                   "class BST:", "    def insert(self, val):",
                                   "        self.root = self._insert(self.root, val)", "",
                                   "    def _insert(self, node, val):", "        if node is None:",
                                   "            return TreeNode(val)", "        if val < node.val:",
                                   "            node.left = self._insert(node.left, val)", "        else:",
                                   "            node.right = self._insert(node.right, val)", "        return node"], 16, steps, ns)
            # 找插入位置
            steps = [{"step_id": 1, "code_line": 12, "description": f"从 root 开始查找插入位置",
                      "highlight_nodes": [root_id], "message": "从根开始"}]
            cur_id = root_id
            parent_id = None
            direction = None
            visited = set()
            while cur_id and cur_id not in visited:
                visited.add(cur_id)
                cur_node = next((n for n in nodes if n["id"] == cur_id), None)
                if not cur_node:
                    break
                cv = cur_node["value"]
                steps.append({"step_id": len(steps) + 1, "code_line": 17,
                              "description": f"比较 {val} 与 {cv}",
                              "highlight_nodes": [cur_id], "message": f"{val} {'<' if val < cv else '>='} {cv}"})
                parent_id = cur_id
                child_edges = [e for e in edges if e["from"] == cur_id and e.get("type") != "prev"]
                if val < cv:
                    direction = "left"
                    left_edge = next((e for e in child_edges if e.get("type") == "left" or
                                      (next((n for n in nodes if n["id"] == e["to"]), None) and
                                       next(n for n in nodes if n["id"] == e["to"])["value"] < cv)), None)
                    cur_id = left_edge["to"] if left_edge else None
                else:
                    direction = "right"
                    right_edge = next((e for e in child_edges if e.get("type") == "right" or
                                       (next((n for n in nodes if n["id"] == e["to"]), None) and
                                        next(n for n in nodes if n["id"] == e["to"])["value"] >= cv)), None)
                    cur_id = right_edge["to"] if right_edge else None
                if cur_id:
                    steps.append({"step_id": len(steps) + 1, "code_line": 18 if direction == "left" else 20,
                                  "description": f"向{direction}子树移动",
                                  "highlight_nodes": [cur_id], "message": f"进入{direction}子树"})
            parent_node = next((n for n in nodes if n["id"] == parent_id), None)
            px = parent_node["position_x"] + (-70 if direction == "left" else 70)
            py = parent_node["position_y"] + 70
            new_node = {"id": new_id, "value": val, "position_x": max(50, px), "position_y": py}
            steps.append({"step_id": len(steps) + 1, "code_line": 16,
                          "description": f"当前位置为空，创建新节点({val})",
                          "node_changes": [{"action": "create", "node_id": new_id, "value": val},
                                           {"action": "link", "from": parent_id, "to": new_id, "type": direction}],
                          "highlight_nodes": [new_id, parent_id], "message": f"插入为{direction}子节点"})
            nodes.append(new_node)
            edges.append({"from": parent_id, "to": new_id, "type": direction})
            return self._pack("BST - 插入", "插入节点到 BST",
                              ["class TreeNode:", "    def __init__(self, val):", "        self.val = val",
                               "        self.left = None", "        self.right = None", "",
                               "class BST:", "    def insert(self, val):",
                               "        self.root = self._insert(self.root, val)", "",
                               "    def _insert(self, node, val):", "        if node is None:",
                               "            return TreeNode(val)", "        if val < node.val:",
                               "            node.left = self._insert(node.left, val)", "        else:",
                               "            node.right = self._insert(node.right, val)", "        return node"], 12, steps, ns)

        if operation_type == "search":
            target = val
            if not root_id:
                steps = [{"step_id": 1, "code_line": 3, "description": "树为空", "highlight_nodes": [], "message": "空树"}]
                return self._pack("BST - 查找", "查找节点",
                                  ["class BST:", "    def search(self, val):",
                                   "        return self._search(self.root, val)", "",
                                   "    def _search(self, node, val):", "        if node is None:",
                                   "            return None", "        if val == node.val:",
                                   "            return node", "        elif val < node.val:",
                                   "            return self._search(node.left, val)", "        else:",
                                   "            return self._search(node.right, val)"], 3, steps, ns)
            cur_id = root_id
            steps = [{"step_id": 1, "code_line": 5, "description": f"从 root 开始查找 {target}",
                      "highlight_nodes": [root_id], "message": "从根开始"}]
            found_id = None
            visited = set()
            while cur_id and cur_id not in visited:
                visited.add(cur_id)
                cur_node = next((n for n in nodes if n["id"] == cur_id), None)
                if not cur_node:
                    break
                cv = cur_node["value"]
                steps.append({"step_id": len(steps) + 1, "code_line": 6,
                              "description": f"比较 {target} 与 {cv}",
                              "highlight_nodes": [cur_id], "message": f"{target} {'==' if target == cv else ('<' if target < cv else '>')} {cv}"})
                if target == cv:
                    found_id = cur_id
                    steps.append({"step_id": len(steps) + 1, "code_line": 7,
                                  "description": "找到目标！",
                                  "highlight_nodes": [cur_id], "message": "查找成功"})
                    break
                child_edges = [e for e in edges if e["from"] == cur_id]
                if target < cv:
                    left_edge = next((e for e in child_edges if e.get("type") == "left"), None)
                    cur_id = left_edge["to"] if left_edge else None
                else:
                    right_edge = next((e for e in child_edges if e.get("type") == "right"), None)
                    cur_id = right_edge["to"] if right_edge else None
                if cur_id:
                    steps.append({"step_id": len(steps) + 1, "code_line": 9 if target < cv else 11,
                                  "description": f"向{'左' if target < cv else '右'}子树移动",
                                  "highlight_nodes": [cur_id], "message": f"进入{'左' if target < cv else '右'}子树"})
            if not found_id:
                steps.append({"step_id": len(steps) + 1, "code_line": 5,
                              "description": f"到达空节点，未找到 {target}",
                              "highlight_nodes": [], "message": "查找失败"})
            return self._pack("BST - 查找", "查找节点",
                              ["class BST:", "    def search(self, val):",
                               "        return self._search(self.root, val)", "",
                               "    def _search(self, node, val):", "        if node is None:",
                               "            return None", "        if val == node.val:", "            return node",
                               "        elif val < node.val:", "            return self._search(node.left, val)",
                               "        else:", "            return self._search(node.right, val)"], 5, steps, ns)

        if operation_type == "delete":
            target = val
            target_node_id = params.get("node_id")
            if not root_id:
                return self._empty_err("BST 为空")
            # 找目标节点
            cur_id = root_id
            parent_id = None
            direction = None
            target_id = None
            visited = set()
            while cur_id and cur_id not in visited:
                visited.add(cur_id)
                cur_node = next((n for n in nodes if n["id"] == cur_id), None)
                if not cur_node:
                    break
                cv = cur_node["value"]
                # 优先按 node_id 精确匹配，否则按 value 匹配
                if target_node_id:
                    if cur_id == target_node_id:
                        target_id = cur_id
                        break
                elif cv == target:
                    target_id = cur_id
                    break
                parent_id = cur_id
                child_edges = [e for e in edges if e["from"] == cur_id]
                if target < cv:
                    direction = "left"
                    left_edge = next((e for e in child_edges if e.get("type") == "left"), None)
                    cur_id = left_edge["to"] if left_edge else None
                else:
                    direction = "right"
                    right_edge = next((e for e in child_edges if e.get("type") == "right"), None)
                    cur_id = right_edge["to"] if right_edge else None
            if not target_id:
                steps = [{"step_id": 1, "code_line": 4, "description": f"未找到值 {target}",
                          "highlight_nodes": [root_id], "message": "未找到"}]
                return self._pack("BST - 删除", "删除节点",
                                  ["class BST:", "    def delete(self, val):",
                                   "        self.root = self._delete(self.root, val)", "",
                                   "    def _delete(self, node, val):", "        if node is None:",
                                   "            return None", "        if val < node.val:",
                                   "            node.left = self._delete(node.left, val)", "        elif val > node.val:",
                                   "            node.right = self._delete(node.right, val)", "        else:",
                                   "            # 找到目标节点", "            ...", "        return node"], 4, steps, ns)
            target_node = next((n for n in nodes if n["id"] == target_id), None)
            child_edges = [e for e in edges if e["from"] == target_id]
            steps = [{"step_id": 1, "code_line": 9, "description": f"找到目标节点({target})",
                      "highlight_nodes": [target_id], "message": "找到目标"}]
            if not child_edges:
                # 叶子节点：直接删
                steps.append({"step_id": 2, "code_line": 11, "description": "叶子节点，直接删除",
                              "node_changes": [{"action": "delete", "node_id": target_id}],
                              "highlight_nodes": [], "message": "删除叶子"})
                nodes[:] = [n for n in nodes if n["id"] != target_id]
                edges[:] = [e for e in edges if e["from"] != target_id and e["to"] != target_id]
                if parent_id:
                    edges[:] = [e for e in edges if not (e["from"] == parent_id and e["to"] == target_id)]
                else:
                    ptrs.pop("root", None)
            elif len(child_edges) == 1:
                # 单子节点：用子节点替换
                child_id = child_edges[0]["to"]
                steps.append({"step_id": 2, "code_line": 13, "description": f"单子节点，用子节点替换",
                              "node_changes": [{"action": "delete", "node_id": target_id},
                                               {"action": "link", "from": parent_id, "to": child_id}] if parent_id else
                              [{"action": "delete", "node_id": target_id}],
                              "pointer_changes": [{"pointer": "root", "target": child_id}] if not parent_id else [],
                              "highlight_nodes": [child_id], "message": "用子节点替换"})
                nodes[:] = [n for n in nodes if n["id"] != target_id]
                edges[:] = [e for e in edges if e["from"] != target_id and e["to"] != target_id]
                if parent_id:
                    edges.append({"from": parent_id, "to": child_id, "type": direction})
                else:
                    ptrs["root"] = child_id
            else:
                # 双子节点：找右子树最小值替换
                right_child = next((e for e in child_edges if e.get("type") == "right"), None)
                right_id = right_child["to"] if right_child else None
                min_id = right_id
                min_parent = target_id
                visited2 = set()
                while min_id and min_id not in visited2:
                    visited2.add(min_id)
                    left_edge = next((e for e in edges if e["from"] == min_id and e.get("type") == "left"), None)
                    if not left_edge:
                        break
                    min_parent = min_id
                    min_id = left_edge["to"]
                min_node = next((n for n in nodes if n["id"] == min_id), None)
                steps.append({"step_id": 2, "code_line": 16, "description": f"双子节点，找右子树最小值({min_node['value'] if min_node else '?'})",
                              "highlight_nodes": [target_id, min_id], "message": "找右子树最小"})
                steps.append({"step_id": 3, "code_line": 17, "description": f"用最小值替换目标值",
                              "node_changes": [{"action": "update", "node_id": target_id, "value": min_node["value"] if min_node else target}],
                              "highlight_nodes": [target_id], "message": "值替换"})
                steps.append({"step_id": 4, "code_line": 18, "description": "删除右子树最小节点",
                              "node_changes": [{"action": "delete", "node_id": min_id}],
                              "highlight_nodes": [], "message": "删除最小节点"})
                if target_node and min_node:
                    target_node["value"] = min_node["value"]
                nodes[:] = [n for n in nodes if n["id"] != min_id]
                edges[:] = [e for e in edges if e["from"] != min_id and e["to"] != min_id]
                if min_parent != target_id:
                    edges[:] = [e for e in edges if not (e["from"] == min_parent and e["to"] == min_id)]
            return self._pack("BST - 删除", "删除节点",
                              ["class BST:", "    def delete(self, val):",
                               "        self.root = self._delete(self.root, val)", "",
                               "    def _delete(self, node, val):", "        if node is None:",
                               "            return None", "        if val < node.val:",
                               "            node.left = self._delete(node.left, val)", "        elif val > node.val:",
                               "            node.right = self._delete(node.right, val)", "        else:",
                               "            # 叶子节点", "            if not node.left and not node.right:",
                               "                return None", "            # 单子节点", "            if not node.left:",
                               "                return node.right", "            if not node.right:",
                               "                return node.left", "            # 双子节点",
                               "            succ = self._min(node.right)", "            node.val = succ.val",
                               "            node.right = self._delete(node.right, succ.val)", "        return node"], 9, steps, ns)

        if operation_type in ("traverse_inorder", "traverse_preorder", "traverse_postorder"):
            order_map = {"traverse_inorder": ("中序", "left", "root", "right"),
                         "traverse_preorder": ("前序", "root", "left", "right"),
                         "traverse_postorder": ("后序", "left", "right", "root")}
            label, first, second, third = order_map[operation_type]
            result_ids = []
            def visit(node_id, order_pos):
                if not node_id or node_id in visited:
                    return
                visited.add(node_id)
                node = next((n for n in nodes if n["id"] == node_id), None)
                child_edges = {e.get("type"): e["to"] for e in edges if e["from"] == node_id}
                seq = [("left", child_edges.get("left")),
                       ("root", node_id if order_pos == "root" else None),
                       ("right", child_edges.get("right"))]
                # 按 order 重排
                order_seq = []
                for pos in (first, second, third):
                    if pos == "root":
                        order_seq.append(("root", node_id))
                    elif pos == "left":
                        order_seq.append(("left", child_edges.get("left")))
                    elif pos == "right":
                        order_seq.append(("right", child_edges.get("right")))
                for kind, nid in order_seq:
                    if kind == "root" and nid:
                        result_ids.append(nid)
                    elif nid:
                        visit(nid, None)
            visited = set()
            if root_id:
                visit(root_id, None)
            steps = [{"step_id": i + 1, "code_line": 4,
                      "description": f"访问 {next((n['value'] for n in nodes if n['id'] == nid), '?')}",
                      "highlight_nodes": [nid], "message": f"第 {i+1} 个"} for i, nid in enumerate(result_ids)]
            code_map = {"traverse_inorder": ["class BST:", "    def inorder(self, node, result):",
                                             "        if node:", "            self.inorder(node.left, result)",
                                             "            result.append(node.val)", "            self.inorder(node.right, result)"],
                        "traverse_preorder": ["class BST:", "    def preorder(self, node, result):",
                                              "        if node:", "            result.append(node.val)",
                                              "            self.preorder(node.left, result)", "            self.preorder(node.right, result)"],
                        "traverse_postorder": ["class BST:", "    def postorder(self, node, result):",
                                               "        if node:", "            self.postorder(node.left, result)",
                                               "            self.postorder(node.right, result)", "            result.append(node.val)"]}
            return self._pack(f"BST - {label}遍历", f"{label}遍历", code_map[operation_type], 4, steps, ns)

        return self._get_basic_result(operation_type, val)

    # ==================== 堆 ====================
    def _heap_operation(self, operation_type: str, params: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        val = int(params.get("value", 10) or 10)
        ns = self._clone_state(state)
        nodes, edges, ptrs = ns["nodes"], ns["edges"], ns["pointers"]
        root_id = ptrs.get("root")

        if operation_type == "insert":
            import math
            new_id = self._new_node_id(ns)
            idx = len(nodes)
            level = int(math.log2(idx + 1)) if idx > 0 else 0
            pos_in_level = idx - (2 ** level - 1)
            x = 400 + (pos_in_level - (2 ** level - 1) / 2) * (300 / max(1, 2 ** level))
            y = 80 + level * 80
            new_node = {"id": new_id, "value": val, "position_x": x, "position_y": y}
            parent_idx = (idx - 1) // 2 if idx > 0 else -1
            parent_id = nodes[parent_idx]["id"] if parent_idx >= 0 and parent_idx < len(nodes) else None
            steps = [
                {"step_id": 1, "code_line": 5, "description": f"将 {val} 放到末尾位置 {idx}",
                 "node_changes": [{"action": "create", "node_id": new_id, "value": val}],
                 "highlight_nodes": [new_id], "message": "插入末尾"},
                {"step_id": 2, "code_line": 6, "description": f"与父节点({nodes[parent_idx]['value'] if parent_idx >= 0 else '?'})比较，上浮",
                 "highlight_nodes": [new_id] + ([parent_id] if parent_id else []), "message": "上浮调整"},
                {"step_id": 3, "code_line": 6, "description": "堆性质满足，插入完成",
                 "highlight_nodes": [new_id], "message": "调整完成"},
            ]
            nodes.append(new_node)
            if parent_id:
                edges.append({"from": parent_id, "to": new_id})
            if not root_id:
                ptrs["root"] = new_id
            return self._pack("堆 - 插入", "插入元素并上浮",
                              ["class MaxHeap:", "    def insert(self, val):",
                               "        self.heap.append(val)", "        self._sift_up(len(self.heap) - 1)", "",
                               "    def _sift_up(self, i):", "        while i > 0:",
                               "            parent = (i - 1) // 2", "            if self.heap[i] > self.heap[parent]:",
                               "                self.heap[i], self.heap[parent] = self.heap[parent], self.heap[i]",
                               "                i = parent", "            else:", "                break"], 5, steps, ns)

        if operation_type == "delete_max":
            if not root_id:
                return self._empty_err("堆为空")
            root_node = next((n for n in nodes if n["id"] == root_id), None)
            last_node = nodes[-1] if nodes else None
            steps = [
                {"step_id": 1, "code_line": 4, "description": f"记录堆顶({root_node['value'] if root_node else '?'})",
                 "highlight_nodes": [root_id], "message": "记录最大值"},
                {"step_id": 2, "code_line": 5, "description": "末尾元素替换堆顶",
                 "node_changes": [{"action": "update", "node_id": root_id, "value": last_node["value"] if last_node else 0}],
                 "highlight_nodes": [root_id], "message": "末尾上移"},
                {"step_id": 3, "code_line": 6, "description": "删除末尾",
                 "node_changes": [{"action": "delete", "node_id": last_node["id"]}] if last_node else [],
                 "highlight_nodes": [], "message": "删除末尾"},
                {"step_id": 4, "code_line": 7, "description": "堆顶下沉调整",
                 "highlight_nodes": [root_id], "message": "下沉调整"},
            ]
            if last_node and root_node:
                root_node["value"] = last_node["value"]
            if last_node:
                nodes[:] = [n for n in nodes if n["id"] != last_node["id"]]
                edges[:] = [e for e in edges if e["from"] != last_node["id"] and e["to"] != last_node["id"]]
            if not nodes:
                ptrs.pop("root", None)
            return self._pack("堆 - 删除最大值", "删除堆顶并下沉",
                              ["class MaxHeap:", "    def delete_max(self):",
                               "        if not self.heap:", "            return None",
                               "        max_val = self.heap[0]", "        self.heap[0] = self.heap[-1]",
                               "        self.heap.pop()", "        self._sift_down(0)", "        return max_val"], 4, steps, ns)

        if operation_type == "peek_max":
            if not root_id:
                return self._empty_err("堆为空")
            root_node = next((n for n in nodes if n["id"] == root_id), None)
            steps = [{"step_id": 1, "code_line": 3, "description": f"返回堆顶({root_node['value'] if root_node else '?'})，不删除",
                      "highlight_nodes": [root_id], "message": "查看最大值"}]
            return self._pack("堆 - 查看最大值", "peek_max",
                              ["class MaxHeap:", "    def peek_max(self):",
                               "        if not self.heap:", "            return None",
                               "        return self.heap[0]"], 3, steps, ns)

        return self._get_basic_result(operation_type, val)

    # ==================== 哈希表 ====================
    def _hash_table_operation(self, operation_type: str, params: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        val = params.get("value", 1)
        try:
            val = int(val)
        except Exception:
            val = 1
        ns = self._clone_state(state)
        nodes, edges, ptrs = ns["nodes"], ns["pointers"]
        bucket_size = 10
        bucket = val % bucket_size

        if operation_type == "insert":
            new_id = self._new_node_id(ns)
            bucket_nodes = [n for n in nodes if n.get("bucket") == bucket]
            bx = 80 + bucket * 110
            by = 100 + len(bucket_nodes) * 60
            new_node = {"id": new_id, "value": val, "bucket": bucket, "position_x": bx, "position_y": by}
            steps = [
                {"step_id": 1, "code_line": 5, "description": f"计算 hash({val}) % {bucket_size} = {bucket}",
                 "highlight_nodes": [], "message": "计算哈希"},
                {"step_id": 2, "code_line": 6, "description": f"放入桶 {bucket}",
                 "node_changes": [{"action": "create", "node_id": new_id, "value": val}],
                 "highlight_nodes": [new_id], "message": "插入桶中"},
            ]
            nodes.append(new_node)
            ptrs[f"bucket_{bucket}"] = new_id
            return self._pack("哈希表 - 插入", "插入键值对（拉链法）",
                              ["class HashTable:", "    def __init__(self, size=10):",
                               "        self.size = size", "        self.table = [[] for _ in range(size)]", "",
                               "    def insert(self, key, val):", "        idx = key % self.size",
                               "        self.table[idx].append((key, val))"], 5, steps, ns)

        if operation_type == "delete":
            target = val
            target_node_id = params.get("node_id")
            # 优先按 node_id 精确匹配，否则按 value 匹配
            target_node = next((n for n in nodes if n["id"] == target_node_id), None) if target_node_id else \
                          next((n for n in nodes if n.get("value") == target), None)
            if not target_node:
                steps = [{"step_id": 1, "code_line": 4, "description": f"hash({target}) = {target % bucket_size}，桶中未找到",
                          "highlight_nodes": [], "message": "未找到"}]
                return self._pack("哈希表 - 删除", "删除键值对",
                                  ["class HashTable:", "    def delete(self, key):",
                                   "        idx = key % self.size", "        for i, (k, v) in enumerate(self.table[idx]):",
                                   "            if k == key:", "                self.table[idx].pop(i)",
                                   "                return True", "        return False"], 4, steps, ns)
            tid = target_node["id"]
            tbucket = target_node.get("bucket", target % bucket_size)
            steps = [
                {"step_id": 1, "code_line": 2, "description": f"计算 hash({target}) = {tbucket}",
                 "highlight_nodes": [], "message": "计算哈希"},
                {"step_id": 2, "code_line": 3, "description": f"在桶 {tbucket} 中找到目标",
                 "highlight_nodes": [tid], "message": "找到目标"},
                {"step_id": 3, "code_line": 5, "description": "从链表中删除",
                 "node_changes": [{"action": "delete", "node_id": tid}],
                 "highlight_nodes": [], "message": "删除完成"},
            ]
            nodes[:] = [n for n in nodes if n["id"] != tid]
            return self._pack("哈希表 - 删除", "删除键值对",
                              ["class HashTable:", "    def delete(self, key):",
                               "        idx = key % self.size", "        for i, (k, v) in enumerate(self.table[idx]):",
                               "            if k == key:", "                self.table[idx].pop(i)",
                               "                return True", "        return False"], 2, steps, ns)

        if operation_type == "search":
            target = val
            tbucket = target % bucket_size
            target_node = next((n for n in nodes if n.get("value") == target), None)
            steps = [
                {"step_id": 1, "code_line": 2, "description": f"计算 hash({target}) = {tbucket}",
                 "highlight_nodes": [], "message": "计算哈希"},
                {"step_id": 2, "code_line": 3, "description": "在桶中遍历查找",
                 "highlight_nodes": [n["id"] for n in nodes if n.get("bucket") == tbucket], "message": "桶中查找"},
            ]
            if target_node:
                steps.append({"step_id": 3, "code_line": 4, "description": f"找到目标({target})",
                              "highlight_nodes": [target_node["id"]], "message": "查找成功"})
            else:
                steps.append({"step_id": 3, "code_line": 6, "description": f"桶中未找到 {target}",
                              "highlight_nodes": [], "message": "查找失败"})
            return self._pack("哈希表 - 查找", "查找键",
                              ["class HashTable:", "    def search(self, key):",
                               "        idx = key % self.size", "        for k, v in self.table[idx]:",
                               "            if k == key:", "                return v",
                               "        return None"], 2, steps, ns)

        return self._get_basic_result(operation_type, val)

    # ==================== 打包工具 ====================
    def _pack(self, title: str, desc: str, code_lines: List[str], start_line: int, steps: List[Dict], final_state: Dict) -> Dict[str, Any]:
        """打包伪代码、步骤、最终状态"""
        return {
            "pseudocode": {
                "title": title,
                "description": desc,
                "code_lines": [{"line": i + 1, "code": c, "is_method": c.strip().startswith("def ")} for i, c in enumerate(code_lines)],
            },
            "steps": steps,
            "final_state": final_state,
        }

    def _empty_err(self, msg: str) -> Dict[str, Any]:
        return {
            "pseudocode": {"title": "操作无法执行", "description": msg, "code_lines": [{"line": 1, "code": f"# {msg}", "is_method": False}]},
            "steps": [{"step_id": 1, "code_line": 1, "description": msg, "node_changes": [], "pointer_changes": [], "highlight_nodes": [], "message": msg}],
            "final_state": {"nodes": [], "edges": [], "pointers": {}},
            "_error": msg,
        }

    def _get_basic_result(self, operation_type: str, value: Any) -> Dict[str, Any]:
        """基础降级结果"""
        return {
            "pseudocode": {
                "title": f"操作 - {operation_type}",
                "description": "基础操作实现",
                "code_lines": [
                    {"line": 1, "code": f"def {operation_type}(self, val):", "is_method": True},
                    {"line": 2, "code": "    pass", "is_method": False},
                ]
            },
            "steps": [
                {"step_id": 1, "code_line": 1, "description": f"执行 {operation_type} 操作",
                 "node_changes": [], "pointer_changes": [], "highlight_nodes": [], "message": "执行操作"}
            ],
            "final_state": {"nodes": [], "edges": [], "pointers": {}}
        }

    # ==================== 初始状态生成 ====================

    def get_initial_state(
        self, structure_key: str, node_count: int = 5
    ) -> Dict[str, Any]:
        """
        获取数据结构的初始状态
        
        Args:
            structure_key: 数据结构类型
            node_count: 初始节点数量
            
        Returns:
            Dict: 初始状态
        """
        import random
        random.seed(42)  # 固定种子便于调试

        values = [random.randint(1, 100) for _ in range(node_count)]

        if structure_key == "singly_linked_list":
            return self._create_linked_list_state(values)
        elif structure_key == "stack":
            return self._create_stack_state(values)
        elif structure_key == "queue":
            return self._create_queue_state(values)
        elif structure_key == "binary_search_tree":
            return self._create_bst_state(values)
        elif structure_key == "heap":
            return self._create_heap_state(values)
        else:
            return {
                "nodes": [],
                "edges": [],
                "pointers": {},
                "values": values,
                "structure_key": structure_key
            }

    async def generate_custom_initial_state_async(
        self,
        structure_key: str,
        user_id: str,
        node_count: int = 5
    ) -> Dict[str, Any]:
        """
        为自定义数据结构生成初始状态（通过LLM）

        Args:
            structure_key: 自定义数据结构key
            user_id: 用户ID
            node_count: 初始节点数量

        Returns:
            Dict: 初始状态
        """
        structure_info = self.get_structure_info(structure_key, user_id)
        if not structure_info:
            return {
                "nodes": [],
                "edges": [],
                "pointers": {},
                "structure_key": structure_key
            }

        structure_desc = structure_info.get("description", "")
        structure_name = structure_info.get("name", structure_key)

        prompt = f"""
你是一位专业的算法可视化专家。请为自定义数据结构「{structure_name}」生成一个初始可视化状态。

**数据结构描述：** {structure_desc or '（无描述，请根据名称推断）'}
**节点数量：** {node_count}

**要求：**
1. 生成 {node_count} 个节点的初始状态
2. 每个节点包含：id（如 node_0）、value（1-100的整数）、position_x、position_y（画布坐标，范围 50-900 x 50-500）
3. edges 描述节点间连接关系，每条边包含 from 和 to（节点id）
4. pointers 描述特殊指针（如 head、tail、root 等），key为指针名，value为指向的节点id

**输出严格的JSON格式：**
```json
{{
  "nodes": [
    {{"id": "node_0", "value": 42, "position_x": 100, "position_y": 200}}
  ],
  "edges": [
    {{"from": "node_0", "to": "node_1"}}
  ],
  "pointers": {{
    "head": "node_0"
  }}
}}
```

**请严格输出JSON格式，不要添加其他内容。**
""".strip()

        try:
            response = await self.llm.ainvoke(prompt)
            result_text = response.content if hasattr(response, 'content') else str(response)
            result_text = self._clean_json_text(result_text)
            state = json.loads(result_text)
            state["structure_key"] = structure_key
            return state
        except Exception as e:
            print(f"⚠️ 自定义数据结构初始状态生成失败: {e}")
            # 降级：生成简单的线性节点
            import random
            random.seed()
            nodes = []
            for i in range(node_count):
                nodes.append({
                    "id": f"node_{i}",
                    "value": random.randint(1, 100),
                    "position_x": 80 + i * 120,
                    "position_y": 250
                })
            edges = []
            for i in range(node_count - 1):
                edges.append({"from": f"node_{i}", "to": f"node_{i+1}"})
            return {
                "nodes": nodes,
                "edges": edges,
                "pointers": {"head": "node_0"} if nodes else {},
                "structure_key": structure_key,
                "_fallback": True
            }

    def _create_linked_list_state(self, values: List[int]) -> Dict[str, Any]:
        """创建链表初始状态"""
        nodes = []
        edges = []
        for i, val in enumerate(values):
            node_id = f"node_{i}"
            nodes.append({
                "id": node_id,
                "value": val,
                "position_x": 80 + i * 120,
                "position_y": 150,
                "next": f"node_{i+1}" if i < len(values) - 1 else None
            })
            if i < len(values) - 1:
                edges.append({"from": node_id, "to": f"node_{i+1}"})

        return {
            "nodes": nodes,
            "edges": edges,
            "pointers": {"head": "node_0"},
            "structure_key": "singly_linked_list"
        }

    def _create_stack_state(self, values: List[int]) -> Dict[str, Any]:
        """创建栈初始状态"""
        nodes = []
        for i, val in enumerate(values):
            nodes.append({
                "id": f"node_{i}",
                "value": val,
                "position_x": 150,
                "position_y": 280 - i * 50,
                "level": i
            })

        return {
            "nodes": nodes,
            "edges": [],
            "pointers": {"top": f"node_{len(values)-1}" if values else None},
            "structure_key": "stack"
        }

    def _create_queue_state(self, values: List[int]) -> Dict[str, Any]:
        """创建队列初始状态"""
        nodes = []
        for i, val in enumerate(values):
            nodes.append({
                "id": f"node_{i}",
                "value": val,
                "position_x": 80 + i * 100,
                "position_y": 180
            })

        return {
            "nodes": nodes,
            "edges": [],
            "pointers": {
                "front": "node_0" if values else None,
                "rear": f"node_{len(values)-1}" if values else None
            },
            "structure_key": "queue"
        }

    def _create_bst_state(self, values: List[int]) -> Dict[str, Any]:
        """创建BST初始状态"""
        sorted_vals = sorted(values)
        nodes = []
        edges = []
        positions = {}

        # 使用数组形式的BST布局
        def build_bst(arr, depth=0, offset=0):
            if not arr:
                return None
            mid = len(arr) // 2
            val = arr[mid]
            node_id = f"bst_{val}"
            x = 300 + (offset - 2) * 80
            y = 100 + depth * 80
            nodes.append({
                "id": node_id,
                "value": val,
                "position_x": x,
                "position_y": y,
                "depth": depth
            })
            positions[val] = node_id

            left_child = build_bst(arr[:mid], depth + 1, offset - 1)
            right_child = build_bst(arr[mid+1:], depth + 1, offset + 1)

            if left_child:
                edges.append({"from": node_id, "to": left_child, "type": "left"})
            if right_child:
                edges.append({"from": node_id, "to": right_child, "type": "right"})

            return node_id

        root_id = build_bst(sorted_vals)

        return {
            "nodes": nodes,
            "edges": edges,
            "pointers": {"root": root_id},
            "structure_key": "binary_search_tree"
        }

    def _create_heap_state(self, values: List[int]) -> Dict[str, Any]:
        """创建堆初始状态"""
        # 使用数组表示堆
        nodes = []
        for i, val in enumerate(values):
            level = (i + 1).bit_length() - 1
            nodes.append({
                "id": f"heap_{i}",
                "value": val,
                "index": i,
                "level": level
            })

        return {
            "nodes": nodes,
            "edges": [],
            "pointers": {"root": "heap_0"},
            "structure_key": "heap",
            "is_max_heap": True
        }
