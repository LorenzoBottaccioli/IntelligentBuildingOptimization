"""Probe of a running Jupyter server on 127.0.0.1:8888 (see jupyter_startup.sh): REST API only, standard library only."""
import http.cookiejar
import json
import os
import time
import urllib.request

B = "http://127.0.0.1:8888"
jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def get(path):
    r = op.open(B + path, timeout=20)
    return r.status, r.headers, r.read()


def procs():
    """Environment of the server process and of the kernel it started (the entrypoint is a login shell: /etc/profile may rewrite PATH)."""
    for pid in sorted(p for p in os.listdir("/proc") if p.isdigit()):
        try:
            cmd = open("/proc/%s/cmdline" % pid, "rb").read().replace(b"\x00", b" ").decode()
            env = dict(x.split("=", 1) for x in open("/proc/%s/environ" % pid, "rb").read().decode().split("\x00") if "=" in x)
        except OSError:
            continue
        if "jupyter-notebook" in cmd or "ipykernel_launcher" in cmd:
            print("  proc", pid, cmd[:70], "| PATH =", env.get("PATH"), "| LD_LIBRARY_PATH =", env.get("LD_LIBRARY_PATH"))


s, h, b = get("/api")
print("version:", json.loads(b))
s, h, b = get("/api/kernelspecs")
ks = json.loads(b)
print("default kernel:", ks["default"], "| kernelspecs:", {k: v["spec"]["display_name"] for k, v in ks["kernelspecs"].items()})
s, h, b = get("/tree")
print("/tree:", s, "| Content-Security-Policy:", h.get("Content-Security-Policy"))
for name in ("conda_environment", "python3"):
    xsrf = next(c.value for c in jar if c.name == "_xsrf")
    req = urllib.request.Request(B + "/api/kernels", data=json.dumps({"name": name}).encode(),
                                 headers={"Content-Type": "application/json", "X-XSRFToken": xsrf}, method="POST")
    k = json.loads(op.open(req, timeout=60).read())
    print("kernel", name, "started:", k["id"][:8], k["execution_state"])
    time.sleep(6)
    s, h, b = get("/api/kernels/" + k["id"])
    print("  state after 6 s:", json.loads(b)["execution_state"])
    procs()
    op.open(urllib.request.Request(B + "/api/kernels/" + k["id"], method="DELETE", headers={"X-XSRFToken": xsrf}), timeout=20)
