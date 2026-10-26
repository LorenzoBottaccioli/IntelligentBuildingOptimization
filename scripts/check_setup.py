"""Check this computer before the first build of the platform. It only reads: it changes nothing.

    python scripts/check_setup.py        (python3 on macOS and Linux; Python 3, standard library only)

It checks Docker, the memory given to Docker, the ports the platform publishes, the two files a clone needs
(.env and the Turin weather file) and, on a Mac, the two things that break the platform there: a project inside
an iCloud folder (offloaded files) and Rosetta emulation (notebook cells that never run). Exit code 1 if something
must be fixed, 0 otherwise (warnings do not count).
"""
import errno
import pathlib
import platform
import socket
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PORTS = {
    80: "frontend", 1883: "MQTT broker", 3000: "Grafana", 5001: "backend", 8080: "openHAB", 8086: "InfluxDB",
    8123: "Home Assistant", 8443: "openHAB (https)", 8889: "Jupyter surrogate", 8892: "Jupyter controller",
}
EPW = pathlib.Path("tutorials") / "ITA_Torino.160590_IWEC.epw"
MIN_MEMORY = 7e9  # bytes; the README asks for about 8 GB (Docker Desktop reports 7.6 GB for an 8 GB setting)

failed = False


def report(level, text):
    global failed
    failed = failed or level == "FAIL"
    print(f"[{level:>4}] {text}")


def run(*command, timeout=60):
    """(exit code, stdout) of a command; (None, '') if it cannot be run, (-1, '') if it does not answer in time."""
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=timeout, cwd=ROOT)
    except OSError:
        return None, ""
    except subprocess.TimeoutExpired:
        return -1, ""
    return done.returncode, done.stdout


def port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
        except OSError as e:
            if e.errno == errno.EADDRINUSE or getattr(e, "winerror", None) in (10048, 10013):
                return False
            # anything else is a privileged port for a non-root user on Linux: Docker publishes it as root
    return True


def check_docker():
    code, out = run("docker", "version", "--format", "{{.Server.Os}}/{{.Server.Arch}}", timeout=20)
    if code is None:
        report("FAIL", "docker was not found: install Docker Desktop")
        return False
    if code != 0:
        report("FAIL", "Docker is installed but not answering: start Docker Desktop and wait until it says it is running")
        return False
    report("ok", "Docker is running (" + out.strip() + ")")
    code, _ = run("docker", "compose", "version")
    report("ok" if code == 0 else "FAIL", "docker compose is available" if code == 0 else "docker compose was not found: update Docker Desktop")
    code, out = run("docker", "info", "--format", "{{.MemTotal}}")
    if code == 0 and out.strip().isdigit():
        memory = int(out)
        if memory < MIN_MEMORY:
            report("warn", f"Docker has {memory / 2**30:.1f} GiB of memory, the platform wants about 8 GB: Docker Desktop > Settings > Resources")
        else:
            report("ok", f"Docker has {memory / 2**30:.1f} GiB of memory")
    return True


def check_ports(docker_up):
    _, names = run("docker", "ps", "--format", "{{.Names}}") if docker_up else (None, "")
    if {"frontend", "backend"} <= set(names.split()):
        report("ok", "the platform is already running: the ports were not checked")
        return
    busy = [f"{port} ({what})" for port, what in PORTS.items() if not port_free(port)]
    if busy:
        report("FAIL", "ports in use by another program: " + ", ".join(busy))
    else:
        report("ok", "ports free: " + ", ".join(str(p) for p in PORTS))


def check_files():
    if (ROOT / ".env").is_file():
        report("ok", ".env is there")
    else:
        report("FAIL", ".env is missing: copy .env.example to .env (cp .env.example .env; on Windows cmd: copy .env.example .env)")
    if (ROOT / EPW).is_file():
        report("ok", "the Turin weather file is there")
    else:
        python = "python" if sys.platform == "win32" else "python3"
        report("warn", f"the Turin weather file is missing (the tutorials cannot simulate): {python} tests/tutorials/fetch_iwec.py")


def check_mac(docker_up):
    if "Mobile Documents" in ROOT.parts:
        report("FAIL", "the project is inside iCloud Drive: move it to a local folder such as ~/Projects (docs/macos.md)")
        return
    code, out = run("ls", "-lOR", ".", timeout=600)
    offloaded = out.count("dataless") if code == 0 else 0
    if offloaded:
        report("FAIL", f"{offloaded} files of the project are offloaded by iCloud: move the project out of Desktop/Documents (docs/macos.md)")
    else:
        report("ok", "no file of the project is offloaded by iCloud")
    if platform.machine() != "arm64":
        return
    if not docker_up:
        report("warn", "Rosetta was not checked because Docker is not running")
        return
    code, out = run("docker", "run", "--rm", "--platform", "linux/amd64", "alpine", "grep", "-m1", "-E", "vendor_id|implementer", "/proc/cpuinfo", timeout=600)
    if "VirtualApple" in out:
        report("FAIL", "Docker Desktop uses Rosetta: notebook cells would never run. Settings > General > untick 'Use Rosetta for x86_64/amd64 emulation', Apply & Restart (docs/macos.md)")
    elif "implementer" in out:
        report("ok", "Docker Desktop emulates x86 with QEMU, not Rosetta")
    else:
        report("warn", "could not tell whether Docker Desktop uses Rosetta: see docs/macos.md")


def main():
    print(f"Checking {ROOT} on {platform.system()} {platform.machine()}\n")
    docker_up = check_docker()
    check_ports(docker_up)
    check_files()
    if platform.system() == "Darwin":
        check_mac(docker_up)
    print("\n" + ("Fix the lines marked FAIL, then run this again." if failed else "Ready: docker compose build jupyter_image_builder, then docker compose up --build -d."))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
