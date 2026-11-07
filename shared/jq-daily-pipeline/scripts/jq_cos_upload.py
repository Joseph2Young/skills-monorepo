#!/usr/bin/env python3
"""COS 上传 — 两种 upload_mode 都要支持 (2026-10-04 起实测)

create_media 返回的 upload_mode 不稳定 (0 / 2 / 1 都出现过), 必须每次读响应分支:

  upload_mode == 1 (UPLOAD_MODEL_URL, 预签名直传)
      cos_credential 为 null, 没有 cos_key。直接 urllib PUT 到 presigned_url,
      原样携带 auth_headers (Content-Length 必须 == file_size), HTTP 200 即成功。
      完全绕开时钟漂移坑, 不需要 qcloud_cos SDK。

  其他 (0 / 2 / 未返回)
      走 cos_credential + qcloud_cos SDK + 冻结 time.time。
      凭证里的 start_time/expired_time 是腾讯云服务端时钟, 本机时钟有漂移
      (实测 -116s), 必须冻结时钟, 否则 SDK 签名的临时密钥窗口落在有效窗外
      → InvalidAccessKeyId。
"""
import json
import sys
import urllib.request


def _unwrap(resp: dict) -> dict:
    """兼容两种形态: create_media 的原始 JSON / MCP 完整响应 (result.content[].text)"""
    if "result" in resp:
        text = "".join(c.get("text", "") for c in resp["result"].get("content", [])
                       if c.get("type") == "text")
        return json.loads(text)
    return resp


def upload_presigned(local_path: str, resp: dict) -> str:
    """upload_mode == 1: 预签名直传"""
    url = resp["upload_url"]["presigned_url"]
    headers = resp["upload_url"]["auth_headers"]
    body = open(local_path, "rb").read()
    declared = int(headers.get("Content-Length", 0))
    if declared != len(body):
        raise ValueError(f"file size mismatch: body={len(body)} header={declared}")
    req = urllib.request.Request(url, data=body, method="PUT")
    for k, v in headers.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=120) as r:
        if r.status != 200:
            raise RuntimeError(f"presigned PUT failed: HTTP {r.status}")
    print(f"✅ presigned upload OK {len(body)} bytes -> {resp['media_id']}")
    return resp["media_id"]


def upload_credential(local_path: str, cred: dict) -> str:
    """upload_mode != 1: COS SDK + 冻结时钟"""
    from unittest.mock import patch
    from qcloud_cos import CosConfig, CosS3Client

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
    return key


def upload(local_path: str, resp_file: str) -> str:
    with open(resp_file) as f:
        resp = _unwrap(json.load(f))

    if resp.get("upload_mode") == 1:
        return upload_presigned(local_path, resp)
    cred = resp.get("cos_credential")
    if not cred:
        raise ValueError(f"no cos_credential and upload_mode != 1: {resp}")
    return upload_credential(local_path, cred)


if __name__ == "__main__":
    upload(sys.argv[1], sys.argv[2])
