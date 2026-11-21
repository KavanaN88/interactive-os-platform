import time
try:
    import pytest
except ImportError:
    from tests._shim import pytest
from app.engines.errors import ValidationError
from app.auth import passwords, tokens
from app.auth.store import Store

def test_password_policy():
    for bad in ["short1", "alllettersnodigit", "123456789012", "", "a1" * 70]:
        with pytest.raises(ValidationError):
            passwords.validate_password(bad)
    passwords.validate_password("Correct-horse9")

def test_hash_is_salted_and_verifies():
    h1, h2 = passwords.hash_password("Secret-pass1"), passwords.hash_password("Secret-pass1")
    assert h1 != h2 and "Secret-pass1" not in h1
    assert passwords.verify_password(h1, "Secret-pass1") and not passwords.verify_password(h1, "Secret-pass2")
    assert passwords.algorithm_of(h1) in ("argon2id", "scrypt")

def test_scrypt_path_and_garbage_hashes_never_raise():
    salt_hash = "scrypt$16384$8$1$" + __import__("base64").b64encode(b"0123456789abcdef").decode() + "$" + __import__("base64").b64encode(__import__("hashlib").scrypt(b"Abcdefg1", salt=b"0123456789abcdef", n=16384, r=8, p=1, dklen=32)).decode()
    assert passwords.verify_password(salt_hash, "Abcdefg1") and not passwords.verify_password(salt_hash, "Abcdefg2")
    for junk in ["", "plaintext", "scrypt$x", "scrypt$1$2$3$!!$!!", "$argon2id$garbage", None.__class__.__name__]:
        assert passwords.verify_password(junk, "Abcdefg1") is False

# RFC-style known-answer test: the widely published HS256 example from jwt.io
JWT_EXAMPLE = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ."
               "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c")

def test_hs256_matches_published_known_answer():
    payload = {"sub": "1234567890", "name": "John Doe", "iat": 1516239022}
    import json, base64
    head = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=").decode()
    assert f"{head}.{body}" == JWT_EXAMPLE.rsplit(".", 1)[0]            # same header/payload encoding as the reference
    assert tokens.encode(payload, b"your-256-bit-secret") == JWT_EXAMPLE      # byte-for-byte identical signature

def test_access_token_roundtrip_expiry_and_tampering():
    s = b"x" * 32
    t = tokens.create_access_token("u1", s, ttl=60, now=1000)
    assert tokens.decode(t, s, now=1030)["sub"] == "u1"
    with pytest.raises(tokens.TokenError):
        tokens.decode(t, s, now=1060)                                      # expired exactly at exp
    with pytest.raises(tokens.TokenError):
        tokens.decode(t, b"y" * 32, now=1030)                               # wrong secret
    head, body, sig = t.split(".")
    other = tokens.encode({"sub": "admin", "iat": 1000, "exp": 99999999999}, b"z" * 32).split(".")[1]
    with pytest.raises(tokens.TokenError):
        tokens.decode(f"{head}.{other}.{sig}", s, now=1030)                  # payload swapped, signature kept

def test_alg_none_and_malformed_tokens_are_rejected():
    import json, base64
    b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    forged = f"{b({'alg': 'none', 'typ': 'JWT'})}.{b({'sub': 'admin', 'exp': 99999999999})}."
    for bad in [forged, forged + "x", "", "a.b", "a.b.c.d", "not a token", "....", f"{b({'alg': 'HS512'})}.{b({'exp': 9e12})}.AAAA"]:
        with pytest.raises(tokens.TokenError):
            tokens.decode(bad, b"s" * 32)

def test_refresh_tokens_are_random_and_only_hashes_are_stored():
    a, ha = tokens.new_refresh_token()
    b, hb = tokens.new_refresh_token()
    assert a != b and ha != a and ha == tokens.hash_token(a) and len(a) >= 40 and ha != hb

def test_secret_from_env_or_generated_file(tmp_path=None):
    import tempfile, pathlib, os
    d = pathlib.Path(tempfile.mkdtemp())
    os.environ.pop("OSLAB_JWT_SECRET", None)
    s1 = tokens.load_secret(d)
    assert len(s1) == 64 and tokens.load_secret(d) == s1                    # generated once, then reused
    os.environ["OSLAB_JWT_SECRET"] = "short"
    with pytest.raises(RuntimeError):
        tokens.load_secret(d)
    os.environ["OSLAB_JWT_SECRET"] = "e" * 40
    assert tokens.load_secret(d) == b"e" * 40
    os.environ.pop("OSLAB_JWT_SECRET")

def test_store_is_parameterised_against_injection_and_enforces_constraints():
    s = Store()
    s.run("INSERT INTO users(id,email,username,password_hash,role,is_active,created_at) VALUES(?,?,?,?,?,?,?)", ("1", "a@b.co", "alice", "h", "student", 1, 1.0))
    evil = "x' OR '1'='1"
    assert s.all("SELECT * FROM users WHERE username=?", (evil,)) == []
    s.run("INSERT INTO audit_logs(ts,action,detail) VALUES(?,?,?)", (1.0, "t", "'); DROP TABLE users;--"))
    assert s.scalar("SELECT COUNT(*) FROM users") == 1
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        s.run("INSERT INTO users(id,email,username,password_hash,role,is_active,created_at) VALUES(?,?,?,?,?,?,?)", ("2", "A@B.CO", "bob", "h", "student", 1, 1.0))   # email is case-insensitive unique
    with pytest.raises(sqlite3.IntegrityError):
        s.run("INSERT INTO users(id,email,username,password_hash,role,is_active,created_at) VALUES(?,?,?,?,?,?,?)", ("3", "c@d.co", "carl", "h", "superuser", 1, 1.0))
