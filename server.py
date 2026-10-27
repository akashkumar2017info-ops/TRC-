import getpass, hashlib, hmac, json, os, re, secrets, socket, sys, threading, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "jobs.json")
LOCK = threading.Lock()
IMGDIR = os.path.join(HERE, "images")
os.makedirs(IMGDIR, exist_ok=True)
IMG = re.compile(r"^[a-f0-9]{16}\.jpg$")
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")
AUTH = os.path.join(HERE, "auth.json")
DEFAULT = {"salt": "5bd68fa1ad7da6ae4808d27d1600d06a", "hash": "f05f3069c860868bcb7c7696109e6d1c2dd4f0b6ff0144ec0cafb77c999a2cec"}  # PBKDF2 hash only, never the password
SESS, FAILS = {}, {}
SESSION_SECONDS = 8 * 3600

def hpw(pw, salt_hex):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt_hex), 200000).hex()

def creds():
    try:
        with open(AUTH, encoding="utf-8") as f:
            c = json.load(f)
            return c["salt"], c["hash"]
    except Exception:
        return DEFAULT["salt"], DEFAULT["hash"]

def set_password():
    p1 = getpass.getpass("New password (at least 4 characters): ")
    if len(p1) < 4 or p1 != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match or are too short. Nothing changed.")
    salt = secrets.token_hex(16)
    with open(AUTH, "w", encoding="utf-8") as f:
        json.dump({"salt": salt, "hash": hpw(p1, salt)}, f)
    print("Password changed. Restart the server so old sessions end.")

def load():
    try:
        with open(DATA, encoding="utf-8") as f:
            d = json.load(f)
            d.setdefault("jobs", {}); d.setdefault("counter", 1000)
            return d
    except Exception:
        return {"jobs": {}, "counter": 1000}

def save(d):
    tmp = DATA + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, DATA)

class H(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json"):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def authed(self):
        t = self.headers.get("X-Auth", "")
        return bool(t) and SESS.get(t, 0) > time.time()

    def login(self):
        ip = self.client_address[0]
        n, until = FAILS.get(ip, (0, 0))
        if until > time.time():
            return self.send(429, {"error": "Too many wrong attempts. Wait one minute."})
        try:
            ln = min(int(self.headers.get("Content-Length", 0)), 1000)
            pw = str(json.loads(self.rfile.read(ln)).get("password", ""))[:64]
        except Exception:
            return self.send(400, {"error": "bad request"})
        salt, good = creds()
        if hmac.compare_digest(hpw(pw, salt), good):
            FAILS.pop(ip, None)
            for k in [k for k, v in SESS.items() if v < time.time()]:
                SESS.pop(k, None)
            tok = secrets.token_urlsafe(32)
            SESS[tok] = time.time() + SESSION_SECONDS
            return self.send(200, {"token": tok})
        n += 1
        FAILS[ip] = (0, time.time() + 60) if n >= 5 else (n, 0)
        time.sleep(0.5)
        self.send(401, {"error": "Wrong password"})

    def do_GET(self):
        if self.path == "/api/jobs":
            with LOCK:
                self.send(200, list(load()["jobs"].values()))
        elif self.path.startswith("/images/") and IMG.match(self.path[8:]):
            try:
                with open(os.path.join(IMGDIR, self.path[8:]), "rb") as f:
                    data = f.read()
            except Exception:
                return self.send(404, {"error": "not found"})
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(data)
        elif self.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                self.send(200, f.read(), "text/html")
        else:
            self.send(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/api/login":
            return self.login()
        if self.path == "/api/upload":
            if not self.authed():
                return self.send(401, {"error": "password required"})
            try:
                n = int(self.headers.get("Content-Length", 0))
                assert 0 < n <= 6000000
                data = self.rfile.read(n)
                assert data[:3] == b"\xff\xd8\xff"
            except Exception:
                return self.send(400, {"error": "bad image"})
            name = secrets.token_hex(8) + ".jpg"
            with open(os.path.join(IMGDIR, name), "wb") as f:
                f.write(data)
            return self.send(200, {"file": name})
        if self.path == "/api/jobs":
            if not self.authed():
                return self.send(401, {"error": "password required"})
            try:
                n = min(int(self.headers.get("Content-Length", 0)), 200000)
                job = json.loads(self.rfile.read(n))
                assert isinstance(job, dict) and ID.match(str(job.get("id", "")))
            except Exception:
                return self.send(400, {"error": "bad job"})
            with LOCK:
                d = load()
                if str(job["id"]).lower() in [k.lower() for k in d["jobs"]]:
                    return self.send(409, {"error": "Job ID already exists"})
                d["jobs"][job["id"]] = job
                save(d)
            return self.send(200, {"ok": True})
        else:
            self.send(404, {"error": "not found"})

    def do_DELETE(self):
        m = re.match(r"^/api/jobs/([A-Za-z0-9][A-Za-z0-9._-]{0,39})$", self.path)
        if not m:
            return self.send(404, {"error": "not found"})
        if not self.authed():
            return self.send(401, {"error": "password required"})
        with LOCK:
            d = load()
            job = d["jobs"].pop(m.group(1), None)
            if job is None:
                return self.send(404, {"error": "not found"})
            save(d)
        for f in (job.get("imgs") or []) if isinstance(job, dict) else []:
            if isinstance(f, str) and IMG.match(f):
                try:
                    os.remove(os.path.join(IMGDIR, f))
                except OSError:
                    pass
        self.send(200, {"ok": True})

    def do_PUT(self):
        m = re.match(r"^/api/jobs/([A-Za-z0-9][A-Za-z0-9._-]{0,39})$", self.path)
        if not m:
            return self.send(404, {"error": "not found"})
        if not self.authed():
            return self.send(401, {"error": "password required"})
        try:
            n = min(int(self.headers.get("Content-Length", 0)), 200000)
            job = json.loads(self.rfile.read(n))
            assert isinstance(job, dict) and job.get("id") == m.group(1)
        except Exception:
            return self.send(400, {"error": "bad job"})
        with LOCK:
            d = load()
            d["jobs"][m.group(1)] = job
            save(d)
        self.send(200, {"ok": True})

    def log_message(self, *a):
        pass

def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "setpass":
        set_password()
        sys.exit()
    port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8000
    print("PCB repair workflow is running.")
    print("Open on this PC:        http://localhost:%d" % port)
    print("Open on other PCs/phones: http://%s:%d" % (lan_ip(), port))
    print("Jobs are saved in:      " + DATA)
    print("Press Ctrl+C to stop.")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
