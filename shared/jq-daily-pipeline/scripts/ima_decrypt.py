import base64, hashlib, hmac, json, os, sys
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

USER_ID = "c627727e-90a2-46d3-ab01-a1a8c971f733"
BASE = os.path.expanduser("~/.workbuddy/connectors/" + USER_ID)


def sha256(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(p)
    return h.digest()


def load_master_key():
    raw = open(os.path.join(BASE, ".master.key"), "rb").read()
    try:
        dec = base64.b64decode(raw, validate=True)
        if len(dec) == 32:
            return dec
    except Exception:
        pass
    return raw


mk = load_master_key()
sys.stderr.write("master key len %d\n" % len(mk))


def hkdf_derive(ikm, salt, info, length=32):
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    okm = b""
    t = b""
    i = 1
    while len(okm) < length:
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        okm += t
        i += 1
    return okm[:length]


def attempt(path, label):
    d = json.load(open(path))
    enc = d.get("encryption", {})
    if not enc:
        sys.stderr.write("[%s] no encryption block\n" % label)
        return None
    salt = base64.b64decode(enc["salt"])
    key = hkdf_derive(mk + USER_ID.encode("utf-8"), salt, b"workbuddy-oauth-credentials-v1", 32)
    ck1 = base64.b64encode(sha256(USER_ID.encode("utf-8"), salt)[:16]).decode()
    ck2 = base64.b64encode(sha256(mk, salt)[:16]).decode()
    sys.stderr.write("[%s] userIdCheck=%s keyCheck=%s\n" % (
        label, ck1 == enc.get("userIdCheck"), ck2 == enc.get("keyCheck")))
    ov = d.get("headerOverrides", {})
    if "ima-mcp" not in ov:
        sys.stderr.write("[%s] no ima-mcp override\n" % label)
        return None
    env = ov["ima-mcp"]["Authorization"]
    iv = base64.b64decode(env["iv"])
    tag = base64.b64decode(env["tag"])
    ct = base64.b64decode(env["ct"])
    # AAD = `${userId}|${serverKey}|${fieldName}`
    # serverKey = `${J}:${connectorId}` where J = "connector-states:headerOverrides"
    fields = ["Authorization"]
    sks = ["connector-states:headerOverrides:ima-mcp"]
    for field in fields:
        for sk in sks:
            aad = ("%s|%s|%s" % (USER_ID, sk, field)).encode("utf-8")
            try:
                pt = AESGCM(key).decrypt(iv, ct + tag, aad).decode("utf-8")
                sys.stderr.write("[%s] OK aad=%s|%s\n" % (label, sk, field))
                return pt
            except Exception:
                continue
    sys.stderr.write("[%s] all aad combos failed\n" % label)
    return None


tok = attempt(os.path.join(BASE, "connector-states.json"), "v4")
if not tok:
    tok = attempt(os.path.join(BASE, "connector-states.v3.json"), "v3")

if tok:
    with open("/tmp/ima_token.txt", "w") as f:
        f.write(tok)
    sys.stderr.write("TOKEN len=%d prefix=%s\n" % (len(tok), tok[:40]))
else:
    sys.stderr.write("DECRYPT FAILED\n")
    sys.exit(1)
