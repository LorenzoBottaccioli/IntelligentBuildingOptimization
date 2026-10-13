"""Same seed, same environment, same PPO on two images: speed, memory, and whether the numbers are identical.

    docker run --rm --network none --hostname rtbox --add-host rtbox:127.0.0.1 --memory=1g --entrypoint /opt/conda/envs/conda_environment/bin/python \
      -e LD_LIBRARY_PATH=/opt/conda/envs/conda_environment/lib -e PYTHONPATH=/opt/gateway \
      -v <repo>/Field:/home/jovyan/field:ro -v <repo>/conda-environment/fmi_mlc:<site-packages>/fmi_mlc:ro \
      -v <repo>/Workspace/ai/AgentTraining.ipynb:/nb.ipynb:ro -v <repo>/tests/runtime/ppo_compare.py:/ppo.py:ro  <image>  /ppo.py [steps] [threads]

The environment is built by executing the code cells 1, 3, 5 and 7 of the notebook itself (imports, PARAMS, reward_fn, GymnasiumAdapter),
the PPO is the one of cell 9 (n_steps=256, batch_size=64, seed=PARAMS["seed"]). Reported as one JSON line:
  env_trace    : 12 steps with a seeded random policy (obs, reward) -> proves the FMU environment gives the same numbers
  learn_s / cpu_s / maxrss_mb : speed and resources of model.learn()
  param_sha256 : hash of the trained network weights; pred : the deterministic action for 5 fixed observations
  ep_rewards   : episode returns seen by the Monitor wrapper
"""
import hashlib
import json
import os
import resource
import shutil
import sys
import tempfile
import time

steps = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
threads = int(sys.argv[2]) if len(sys.argv) > 2 else 0

import nbformat
nb = nbformat.read("/nb.ipynb", as_version=4)
g = {"__name__": "nbrun"}
os.environ["TOTAL_TIMESTEPS"] = str(steps)
for i in (1, 3, 5, 7):
    exec(compile("".join(nb.cells[i].source), f"cell{i}", "exec"), g)

import numpy as np
import torch
if threads:
    torch.set_num_threads(threads)
PARAMS, FMU_SOURCE = g["PARAMS"], g["FMU_SOURCE"]
fmi_gym, GymnasiumAdapter, reward_fn, PPO = g["fmi_gym"], g["GymnasiumAdapter"], g["reward_fn"], g["PPO"]

workdir = tempfile.mkdtemp(prefix="ppo_cmp_")
start = os.getcwd()
out = {"python": sys.version.split()[0], "torch": torch.__version__, "threads": torch.get_num_threads(), "steps": steps}
try:
    shutil.copy(FMU_SOURCE, workdir)
    os.chdir(workdir)
    PARAMS["fmu_path"] = os.path.join(workdir, os.path.basename(FMU_SOURCE))

    # 1. environment alone, seeded random actions
    env = GymnasiumAdapter(fmi_gym(PARAMS), reward_fn=reward_fn)
    rng = np.random.default_rng(123)
    obs, _ = env.reset()
    trace = []
    for _ in range(12):
        a = rng.uniform(env.action_space.low, env.action_space.high).astype(np.float32)
        obs, r, done, _, _ = env.step(a)
        trace.append([float(obs[0]), round(r, 9)])
    env.close()
    out["env_trace"] = trace

    # 2. the PPO of the notebook
    env = GymnasiumAdapter(fmi_gym(PARAMS), reward_fn=reward_fn)
    model = PPO("MlpPolicy", env, n_steps=256, batch_size=64, verbose=0, seed=PARAMS["seed"])
    ru0 = resource.getrusage(resource.RUSAGE_SELF)
    c0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    t0 = time.time()
    model.learn(total_timesteps=steps)
    out["learn_s"] = round(time.time() - t0, 1)
    ru1 = resource.getrusage(resource.RUSAGE_SELF)
    c1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    out["cpu_s"] = round(ru1.ru_utime + ru1.ru_stime - ru0.ru_utime - ru0.ru_stime + c1.ru_utime + c1.ru_stime - c0.ru_utime - c0.ru_stime, 1)
    out["maxrss_mb"] = round(ru1.ru_maxrss / 1024, 1)
    sd = model.policy.state_dict()
    h = hashlib.sha256()
    for k in sorted(sd):
        h.update(k.encode())
        h.update(sd[k].cpu().numpy().tobytes())
    out["param_sha256"] = h.hexdigest()[:16]
    probe = np.array([[15.0], [18.0], [20.0], [22.0], [25.0]], dtype=np.float32)
    out["pred"] = [round(float(model.predict(o, deterministic=True)[0][0]), 6) for o in probe]
    out["ep_rewards"] = [round(float(e["r"]), 4) for e in model.ep_info_buffer]
    env.close()
finally:
    os.chdir(start)
    shutil.rmtree(workdir, ignore_errors=True)
print("RESULT " + json.dumps(out))
