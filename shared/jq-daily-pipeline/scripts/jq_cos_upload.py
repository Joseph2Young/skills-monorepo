#!/usr/bin/env python3
"""COS 上传 — qcloud_cos SDK + 冻结 time.time (2026-10-23 验证的唯一可行解)

凭证里的 start_time/expired_time 是腾讯云服务端时钟, 本机时钟有漂移 (实测 -116s),
必须冻结时钟, 否则 SDK 签名的临时密钥窗口落在有效窗外 → InvalidAccessKeyId。
"""
import json
import sys
from unittest.mock import patch

from qcloud_cos import CosConfig, CosS3Client


def upload(local_path: str, resp_file: str) -> str:
    with open(resp_file) as f:
        resp = json.load(f)
    # resp 是 create_media 的完整 MCP 响应, 内层 text 是 JSON 字符串
    if "result" in resp:
        text = "".join(c.get("text", "") for c in resp["result"].get("content", [])
                       if c.get("type") == "text")
        cred = json.loads(text)["cos_credential"]
    else:
        cred = resp["cos_credential"]

    key = cred["cos_key"]
    print(f"cos_key len={len(key)} bucket={cred['bucket_name']} region={cred['region']}")

    client = CosS3Client(CosConfig(
        Region=cred["region"],
        SecretId=cred["secret_id"],
        SecretKey=cred["secret_key"],
        Token=cred["token"],
        Scheme="https",
    ))
    body = open(local_path, "rb").read()
    with patch("time.time", return_value=int(cred["start_time"]) + 60):
        client.put_object(
            Bucket=cred["bucket_name"],
            Key=key,
            Body=body,
            ContentType="text/markdown",
        )
    print(f"✅ uploaded {len(body)} bytes -> {key}")
    return cred


if __name__ == "__main__":
    upload(sys.argv[1], sys.argv[2])
