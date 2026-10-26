# Running the platform on a Mac

Apple Silicon (M1 to M4) and Intel. The repository already carries what a Mac needs (backend on port 5001, the x86 services pinned
to `linux/amd64`, a file that hides `debugpy` under emulation). What it cannot carry are two settings of your computer: do these
before the first build. Based on the setup written by a student who ran the platform on a MacBook with Apple Silicon (macOS 26,
Docker Desktop 29.1.3, QEMU emulation: 12 containers up, demo session loaded, notebooks running cells).

| Symptom on a Mac | Cause | Fix |
| --- | --- | --- |
| Notebook cells stay at `[ ]` after Shift+Enter | Rosetta emulation deadlocks the x86 Python processes (Jupyter server, kernel) | Rosetta off (section 2) |
| `File Load Error ... 404 Not Found` on a notebook, Grafana restarts, `resource deadlock avoided` in the logs, the demo does not load | Project inside an iCloud-synced folder: files are offloaded and Docker cannot read them | Project outside iCloud (section 1) |
| `address already in use`, port 5000 | macOS AirPlay Receiver | Already handled: the backend is on 5001 |
| FMU created but the simulation cannot load it | `eptofmu` built for arm64 while `pyfmi` runs amd64 | Already handled: `platform: linux/amd64`. Check in section 5 |

`python scripts/check_setup.py` checks sections 1 and 2 for you.

## 0. Prerequisites

[Docker Desktop](https://www.docker.com/products/docker-desktop/), Python 3 (`brew install python3`), Git (`xcode-select --install`).
In Docker Desktop, Settings > Resources: at least 8 GB of memory and about 30 GB of free disk. The platform runs 12 containers.

## 1. Keep the project outside iCloud

If the project is in Desktop or Documents and those folders sync with iCloud Drive (with *Optimize Mac Storage*), macOS replaces
files with empty placeholders and Docker fails to read them. Clone into a local folder without spaces, for example:

```bash
mkdir -p ~/Projects && cd ~/Projects
git clone https://github.com/LorenzoBottaccioli/IntelligentBuildingOptimization.git
```

To check that no file is offloaded (it must print 0):

```bash
cd ~/Projects/IntelligentBuildingOptimization && ls -lOR . | grep -c dataless
```

If you must keep it on the Desktop, turn off System Settings > [your name] > iCloud > *Optimize Mac Storage*, then force every file
down with `find . -type f -print0 | xargs -0 cat > /dev/null`.

## 2. Docker Desktop: Rosetta off (Apple Silicon only)

EnergyPlus 9.6 exists only for x86_64, so the Jupyter, controller, bms_services, energyplus and eptofmu containers are emulated.
Rosetta is faster, but with it the Jupyter server and the kernel deadlock. QEMU is slower and stable.

Docker Desktop > Settings (gear) > General > untick *Use Rosetta for x86_64/amd64 emulation on Apple Silicon* > Apply & Restart.

Check (the output must show `CPU implementer`, not `VirtualApple`):

```bash
docker run --rm --platform linux/amd64 alpine grep -m1 -E 'vendor_id|implementer' /proc/cpuinfo
```

Intel Macs skip this section.

## 3. Build and start

As in the README quick start (`python3` on a Mac), after `python3 scripts/check_setup.py` says there is nothing to fix:

```bash
cp .env.example .env
python3 tests/tutorials/fetch_iwec.py
docker compose build jupyter_image_builder
docker compose up --build -d
```

Under emulation the first build of the Jupyter image takes tens of minutes, possibly more than an hour; later builds use the cache.
Rebuild it whenever `conda-environment/sitecustomize.py` or `Dockerfile.unified` change. Wait 1-2 minutes after `up`.

## 4. Verify

```bash
docker compose ps
docker compose logs backend | grep 'Demo session opened'
```

12 containers `Up` and the log line. Then open <http://localhost:8889>, open `tutorials/1_bdopt_overview.ipynb` and run the first
cell with Shift+Enter: it must become `[1]` within seconds. The cells that run EnergyPlus are slower than on Linux or Windows.
If you opened Jupyter before the fix, reload the page (Kernel > Restart Kernel): an old tab may be attached to a dead kernel.

## 5. Troubleshooting

**Cells stay at `[ ]` / "Kernel didn't respond".** Rosetta is still on (section 2). Or the image was built before `sitecustomize.py`
existed: rebuild it (`docker compose build jupyter_image_builder`, then `docker compose up -d`). To see that `debugpy` is hidden
under emulation, this must print `ModuleNotFoundError`: `docker exec jupyter_surrogate python -c 'import debugpy'`.

**404 on notebooks, "resource deadlock avoided", Grafana restarting.** Offloaded files (section 1). After moving the project:
`docker compose down`, then `docker compose up -d` from the new folder. If the demo still does not appear, copy it by hand:

```bash
cp -R backend/seed_sessions/bdopt-demo/state/surrogate_notebooks/* backend/surrogate_notebooks/
cp -Rn backend/seed_sessions/bdopt-demo/state/uploads/* backend/uploads/
cp -Rn backend/seed_sessions/bdopt-demo/state/originals/* backend/originals/
cp -Rn backend/seed_sessions/bdopt-demo/state/workspace/* Workspace/
```

**The FMU is exported but the simulation cannot load it.** `eptofmu` must be amd64:

```bash
docker image inspect -f '{{.Architecture}}' eptofmu:3.1.0
```

If it says `arm64`: `docker compose build eptofmu && docker compose up -d`, then export the FMU again.

**Warning "platform (linux/amd64) does not match the detected host".** Normal on Apple Silicon: those containers are emulated.

**A container keeps restarting.** `docker compose logs --tail 50 <service>`.

**Full rebuild of this project's images:**

```bash
docker compose down
docker rmi jupyter:smartbuilding-unified backend:latest frontend:latest eptofmu:3.1.0
docker compose build --no-cache jupyter_image_builder
docker compose up --build -d
```

Do not use `docker system prune -af` as a reset: it deletes the images of every Docker project on the Mac.
