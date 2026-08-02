#!/usr/bin/env python3
"""
IMA OpenAPI 通用封装 - 支持 connector 优先 + 降级到直接 HTTPS

优先级:
1. 环境变量 IMA_CONNECTOR (指向 connector 脚本路径) → 调 connector
2. PATH 里的 ima-connector 命令 → 调命令
3. 都不存在 → 降级到直接 HTTPS (X-IMA-CLIENTID/APIKEY headers)
"""
import json
import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional
import requests

# 凭证加载
def _load_creds() -> tuple:
    cid_file = Path.home() / ".config" / "ima" / "client_id"
    key_file = Path.home() / ".config" / "ima" / "api_key"
    if cid_file.exists() and key_file.exists():
        return cid_file.read_text().strip(), key_file.read_text().strip()
    return os.environ.get("IMA_OPENAPI_CLIENTID", ""), os.environ.get("IMA_OPENAPI_APIKEY", "")

CLIENT_ID, API_KEY = _load_creds()
BASE_URL = "https://ima.qq.com"

# 默认 IMA 资源 ID
# 注: 2026-08-02 主人规则调整, 入库直接进"聚宽量化策略库"父文件夹,
#     不再按年度分子文件夹 (1.聚宽策略合集2026年 等)
KB_ID = os.environ.get("IMA_KB_ID", "AZo_6kQ-8psF9GTr152Bn0Uj4cS60sdH6SO_AJLDsrE=")
TARGET_FOLDER_ID = os.environ.get("IMA_TARGET_FOLDER_ID", "folder_7403603866166189")
# 兼容旧引用 (PARENT_FOLDER_ID 已废弃)
PARENT_FOLDER_ID = TARGET_FOLDER_ID
# 历史年度映射 (2026-08-02 起不再使用, 仅保留兼容旧代码)
YEAR_FOLDER_MAP = {
    "2026": "folder_7460938768731745",
}


# ============================================================
# 抽象客户端
# ============================================================
class IMAClient(ABC):
    """IMA 客户端抽象基类"""
    
    @abstractmethod
    def call(self, api_path: str, params: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
        """调用 IMA API"""
        pass
    
    # 高层方法 (所有客户端都实现)
    def search_knowledge_base(self, query: str, limit: int = 20) -> list:
        resp = self.call("/openapi/wiki/v1/search_knowledge_base", {
            "query": query, "cursor": "", "limit": limit
        })
        return resp.get("data", {}).get("info_list", [])
    
    def get_knowledge_list(self, kb_id: str, folder_id: Optional[str] = None, limit: int = 50) -> list:
        params = {"knowledge_base_id": kb_id, "cursor": "", "limit": limit}
        if folder_id:
            params["folder_id"] = folder_id
        all_items = []
        while True:
            resp = self.call("/openapi/wiki/v1/get_knowledge_list", params)
            data = resp.get("data", {})
            all_items.extend(data.get("knowledge_list", []))
            if data.get("is_end", True):
                break
            cursor = data.get("next_cursor", "")
            if not cursor:
                break
            params["cursor"] = cursor
        return all_items
    
    def create_folder(self, kb_id: str, name: str, parent_id: str) -> str:
        resp = self.call("/openapi/wiki/v1/create_folder", {
            "knowledge_base_id": kb_id, "folder_name": name, "parent_folder_id": parent_id
        })
        if resp.get("code") != 0:
            raise RuntimeError(f"create_folder 失败: {resp.get('msg')}")
        return resp.get("data", {}).get("folder_id", "")
    
    def find_or_create_year_folder(self, year: str) -> str:
        # 2026-08-02 主人规则调整: 不再按年度创建子文件夹, 直接返回 target folder
        # 历史: 旧逻辑会按 year 查/建 "1.聚宽策略合集{year}年" 子文件夹
        return TARGET_FOLDER_ID
    
    def get_existing_titles_in_folder(self, folder_id: str) -> set:
        items = self.get_knowledge_list(KB_ID, folder_id, 50)
        return {it.get("title", "").strip() for it in items if it.get("title")}
    
    def check_repeated(self, file_name: str, media_type: int, folder_id: str) -> bool:
        resp = self.call("/openapi/wiki/v1/check_repeated_names", {
            "params": [{"name": file_name, "media_type": media_type}],
            "knowledge_base_id": KB_ID, "folder_id": folder_id,
        })
        if resp.get("code") != 0:
            return False
        return any(it.get("is_repeated") for it in resp.get("data", {}).get("repeated_items", []))
    
    def create_media(self, file_name: str, file_size: int, content_type: str, file_ext: str) -> Dict:
        resp = self.call("/openapi/wiki/v1/create_media", {
            "file_name": file_name, "file_size": file_size,
            "content_type": content_type, "knowledge_base_id": KB_ID, "file_ext": file_ext,
        })
        if resp.get("code") != 0:
            raise RuntimeError(f"create_media 失败: {resp.get('msg')}")
        return resp.get("data", {})
    
    def add_knowledge(self, media_id: str, title: str, folder_id: str, media_type: int,
                      cos_key: str, file_size: int, file_name: str) -> None:
        resp = self.call("/openapi/wiki/v1/add_knowledge", {
            "media_type": media_type, "media_id": media_id, "title": title,
            "knowledge_base_id": KB_ID, "folder_id": folder_id,
            "file_info": {"cos_key": cos_key, "file_size": file_size, "file_name": file_name},
        })
        if resp.get("code") != 0:
            raise RuntimeError(f"add_knowledge 失败: {resp.get('msg')}")
    
    def upload_to_cos(self, file_path: Path, cos_credential: dict, content_type: str,
                      timeout: int = 300) -> None:
        """上传到 COS (子类可重写)"""
        bucket = cos_credential.get("bucket_name", "")
        region = cos_credential.get("region", "")
        cos_key = cos_credential.get("cos_key", "")
        if region == "ap-shanghai":
            host = f"https://{bucket}.cos.ap-shanghai.myqcloud.com"
        else:
            host = f"https://{bucket}.cos.{region}.myqcloud.com"
        url = f"{host}/{cos_key}"
        headers = {
            "Authorization": cos_credential.get("token", ""),
            "Content-Type": content_type,
            "x-cos-security-token": cos_credential.get("token", ""),
        }
        with open(file_path, "rb") as f:
            r = requests.put(url, headers=headers, data=f, timeout=timeout)
        r.raise_for_status()


# ============================================================
# 模式 1: 直接 HTTPS (默认, 降级方案)
# ============================================================
class DirectIMAClient(IMAClient):
    """直接 HTTPS 调 IMA OpenAPI"""
    
    def __init__(self):
        if not CLIENT_ID or not API_KEY:
            raise RuntimeError("IMA 凭证未配置: ~/.config/ima/client_id 和 api_key")
        self.client_id = CLIENT_ID
        self.api_key = API_KEY
    
    def call(self, api_path: str, params: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
        url = f"{BASE_URL}{api_path}"
        headers = {
            "ima-openapi-clientid": self.client_id,
            "ima-openapi-apikey": self.api_key,
            "Content-Type": "application/json",
        }
        r = requests.post(url, headers=headers, json=params, timeout=timeout)
        r.raise_for_status()
        return r.json()


# ============================================================
# 模式 2: 外部 connector (CLI 命令或脚本)
# ============================================================
class ConnectorIMAClient(IMAClient):
    """通过外部 connector 脚本/命令访问 IMA
    
    connector 调用约定: 
        connector <api_path> <params_json>
        返回 JSON 到 stdout
    """
    
    def __init__(self, connector_cmd: list):
        self.connector_cmd = connector_cmd
    
    def call(self, api_path: str, params: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
        cmd = self.connector_cmd + [api_path, json.dumps(params, ensure_ascii=False)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            raise RuntimeError(f"connector 失败: {r.stderr}")
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"connector 输出非 JSON: {r.stdout[:200]}")


# ============================================================
# 模式 3: MCP connector (如果 agent 支持 MCP)
# ============================================================
class MCPIMAClient(IMAClient):
    """通过 MCP 工具访问 IMA (需要 agent 暴露 MCP 工具)
    
    使用时需传入 agent 提供的 call_mcp 回调
    """
    
    def __init__(self, mcp_call_fn):
        """
        Args:
            mcp_call_fn: agent 提供的 MCP 调用函数
                          签名: call_mcp(server: str, method: str, params: dict) -> dict
        """
        self.mcp_call = mcp_call_fn
    
    def call(self, api_path: str, params: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
        return self.mcp_call("ima", api_path, params)


# ============================================================
# 智能检测 + 单例
# ============================================================
_client: Optional[IMAClient] = None
_mode: str = ""


def detect_client(prefer: str = "auto") -> IMAClient:
    """智能检测可用的 IMA 客户端

    优先级链 (auto 模式):
      1. MCP 连接器 (IMA_MCP_CALLBACK)        ← WorkBuddy 默认首选
      2. 外部 connector 脚本 (IMA_CONNECTOR)
      3. PATH 里的 ima-connector 命令
      4. (workbuddy_strict=True 时) 报错退出, 不允许降级
      5. (workbuddy_strict=False 时) 降级到 HTTPS API (ima skills)

    prefer:
      - "auto"      : 按上述优先级自动检测
      - "connector" : 强制 connector/MCP, 没就报错
      - "direct"    : 强制直接 HTTPS (无视 workbuddy_strict)

    WorkBuddy 严格模式:
      设了环境变量 WORKBUDDY_REQUIRE_CONNECTOR=1 后, 若未检测到 MCP/connector
      会抛出 RuntimeError, 禁止降级到 HTTPS。这是为了确保 WorkBuddy 内永远
      走连接器, 避免 HTTPS API 凭证问题。
    """
    global _client, _mode

    if _client is not None:
        return _client

    # 强制 HTTPS 模式 (绕过 workbuddy_strict)
    if prefer == "direct":
        _client = DirectIMAClient()
        _mode = "direct"
        return _client

    workbuddy_strict = os.environ.get(
        "WORKBUDDY_REQUIRE_CONNECTOR", ""
    ).lower() in ("1", "true", "yes")

    def _load_mcp() -> Optional[IMAClient]:
        spec_path = os.environ.get("IMA_MCP_CALLBACK")
        if not spec_path:
            return None
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("mcp_cb", spec_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return MCPIMAClient(mod.call_mcp)
        except Exception as e:
            if workbuddy_strict:
                raise RuntimeError(
                    f"❌ MCP callback 加载失败 (workbuddy_strict 模式不允许降级): {e}"
                ) from e
            return None

    def _load_connector() -> Optional[IMAClient]:
        # 环境变量指向 connector 脚本
        if connector := os.environ.get("IMA_CONNECTOR"):
            if Path(connector).exists():
                return ConnectorIMAClient([connector])
        # PATH 里的命令
        if cmd := shutil.which("ima-connector"):
            return ConnectorIMAClient([cmd])
        return None

    # 1. MCP 连接器 (最高优先级)
    if client := _load_mcp():
        _client = client
        _mode = f"mcp:{os.environ['IMA_MCP_CALLBACK']}"
        return _client

    # 2-3. 外部 connector
    if client := _load_connector():
        _client = client
        if os.environ.get("IMA_CONNECTOR"):
            _mode = f"connector:{os.environ['IMA_CONNECTOR']}"
        else:
            _mode = f"connector-cmd:{shutil.which('ima-connector')}"
        return _client

    # 4. WorkBuddy 严格模式: 没 connector/MCP 就报错, 禁止降级
    if workbuddy_strict:
        raise RuntimeError(
            "❌ WorkBuddy 内必须使用 IMA 连接器, 但当前没检测到任何连接器。\n"
            "请二选一:\n"
            "  1) 启用 ima-mcp MCP 服务 + 设置 IMA_MCP_CALLBACK=<wrapper_path>\n"
            "  2) 设置 IMA_CONNECTOR=<脚本路径> 或安装 ima-connector CLI\n"
            "如在非 WorkBuddy 环境运行, 取消 WORKBUDDY_REQUIRE_CONNECTOR 即可降级到 HTTPS API。"
        )

    # 5. 降级: HTTPS API (ima skills 模式)
    _client = DirectIMAClient()
    _mode = "direct"
    return _client


def get_mode() -> str:
    """返回当前使用的模式 (用于日志)"""
    if not _mode:
        try:
            detect_client()
        except: pass
    return _mode


# 便捷全局函数 (自动检测 + 缓存)
def call(api_path: str, params: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
    return detect_client().call(api_path, params, timeout)


def search_knowledge_base(query: str, limit: int = 20) -> list:
    return detect_client().search_knowledge_base(query, limit)


def get_knowledge_list(kb_id: str, folder_id: Optional[str] = None, limit: int = 50) -> list:
    return detect_client().get_knowledge_list(kb_id, folder_id, limit)


def find_or_create_year_folder(year: str) -> str:
    return detect_client().find_or_create_year_folder(year)


def get_existing_titles_in_folder(folder_id: str) -> set:
    return detect_client().get_existing_titles_in_folder(folder_id)


def check_repeated(file_name: str, media_type: int, folder_id: str) -> bool:
    return detect_client().check_repeated(file_name, media_type, folder_id)


def create_media(file_name: str, file_size: int, content_type: str, file_ext: str) -> Dict:
    return detect_client().create_media(file_name, file_size, content_type, file_ext)


def add_knowledge(media_id: str, title: str, folder_id: str, media_type: int,
                  cos_key: str, file_size: int, file_name: str) -> None:
    return detect_client().add_knowledge(media_id, title, folder_id, media_type,
                                          cos_key, file_size, file_name)


def upload_to_cos(file_path: Path, cos_credential: dict, content_type: str,
                  timeout: int = 300) -> None:
    return detect_client().upload_to_cos(file_path, cos_credential, content_type, timeout)


# 重新导出
YEAR_FOLDER_MAP = YEAR_FOLDER_MAP
KB_ID = KB_ID
TARGET_FOLDER_ID = TARGET_FOLDER_ID
PARENT_FOLDER_ID = PARENT_FOLDER_ID  # 兼容旧引用


# ============================================================
# 自测
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("IMA 客户端自测")
    print("=" * 60)
    print(f"模式: {get_mode()}")
    print(f"凭证: {'OK' if CLIENT_ID and API_KEY else '缺失'}")
    
    try:
        client = detect_client()
        print(f"客户端类型: {type(client).__name__}")
        
        # 测试查知识库
        kbs = search_knowledge_base("YTF", 5)
        print(f"✅ search_knowledge_base: 找到 {len(kbs)} 条")
        for kb in kbs[:3]:
            print(f"   - {kb.get('kb_name')}")
    except Exception as e:
        print(f"❌ {e}")
    
    # 显示当前模式
    print(f"\n最终模式: {get_mode()}")
