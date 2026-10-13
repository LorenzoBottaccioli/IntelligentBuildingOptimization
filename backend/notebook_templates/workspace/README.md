# Your Workspace

You build the digital chain of a smart building. The building itself is simulated by
EnergyPlus (an FMU); everything between the building and your data is code you write.

| File | Edited in (menu) | What it must do | How it runs |
|---|---|---|---|
| `devices/gateway.py` | Building & devices > Gateway | Device gateway: maps the FMU outputs (sensors) to MQTT topics and payloads you design, applies commands received on your actuator topics to the FMU inputs, decides publishing rules and timing handshake. Prints the available inputs/outputs at startup. | Control room: started once per building start; exits 0 when the simulation ends |
| `iot/subscriber.py` | IoT & data > Subscriber | Subscribes to your device topics, normalises, validates, stores in InfluxDB (`base_building` for baseline, `controlled_building` for controlled), optionally republishes. | Control room service (restarts on save/crash) |
| `iot/data_access.ipynb`, `iot/energy_signature.ipynb` | IoT & data > Data notebooks | Data access (query the stored data) and energy signature (daily energy vs outdoor temperature). | Notebook |
| `ai/controller.py` | AI (optional) > Controller | Subscribes to sensor values, decides, publishes commands on your actuator command topics (controlled run only). | Control room service |
| `ai/AgentTraining.ipynb` | AI (optional) > Agent training | Train an RL agent (save models in `ai/models/`). | Notebook |
| `ai/forecasting.ipynb` | AI (optional) > Forecasting | Train a forecaster. | Notebook |

## Recommended start order (Control room)
1. Start `subscriber` (and `controller`, if any) first, so no value is lost.
2. Then start the building (baseline or controlled): this runs `devices/gateway.py`.
3. Watch the log; stop everything from the Control room.

Every `.py` file you add directly in `devices/`, `iot/` or `ai/` (other than `devices/gateway.py`, which is the building) becomes a service you can start/stop there.

## Notes
- Logs are in the `logs/` folder of the Workspace and in the Control room, named `logs/<folder>_<file>.log`, for example `logs/iot_subscriber.py.log` and `logs/devices_gateway.py.log` (a log above 5 MB is truncated).
- Topics starting with `platform/` are reserved for the platform: never publish or rely on them.
- The skeletons run but do nothing (or exit with a `TODO:` message) until you write the parts marked TODO.
- Code is written in the pages above (each opens its file in this Workspace's Jupyter) and run only from BMS > Control room; nothing starts by itself.
- Baseline run = native EnergyPlus control, no actuators. Controlled run = actuators accept your commands.
