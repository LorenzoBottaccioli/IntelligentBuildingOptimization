# Gateway: building.py and the emergency gateway

The building is an EnergyPlus model exported as an FMU. Two pieces of platform
code (read-only, mounted at `/opt/gateway`) sit between it and the MQTT broker:

- `building.py`: a thin library. **You use it in your own `devices/gateway.py`**: it
  loads and steps the FMU, checks that EnergyPlus is alive and reports the run
  state. What you publish and which commands you accept is your design.
- `emergency_gateway.py`: the platform's own ready-made gateway, driven by
  `Field/points.yaml`. It runs only when the teacher enables it for a stuck group.

## Files

| File | Written by | Purpose |
|---|---|---|
| `Field/<model>.fmu` | FMU export | controlled run |
| `Field/<model>_baseline.fmu` | FMU export | baseline run (platform inputs removed; `To:Variable` inputs of the EMS programs stay at their initial value) |
| `Field/parameters.py` | FMU export | `fmu_step_size`, `fmu_start_time`, `fmu_final_time` (seconds) |
| `Field/points.generated.yaml` | FMU export | the FMU interface (fmu names and types, every other field TODO), regenerated every export |
| `Field/points.yaml` | **you** | the points of your building; read only by the emergency gateway |

## building.py

```python
from building import Building
b = Building(run='controlled', field_dir='/home/jovyan/field', publish_status=True, year=None)
```

`run` is `'controlled'` (the FMU you export) or `'baseline'` (the same building with its
native control, whose platform inputs are removed). `publish_status=False` turns off the
status on the broker (notebooks, training). `year` is the calendar year of the timestamps
(default: the current year).

| Member | Meaning |
|---|---|
| `inputs`, `outputs` | FMU variable names by causality (from `modelDescription.xml`) |
| `step_size`, `start_time`, `stop_time` | seconds, from `parameters.py` |
| `steps_total` | `ceil((stop - start) / step_size)` |
| `year`, `timestamp` | year used for timestamps; ISO timestamp of the current simulated instant |
| `done` | `True` when all steps are done |
| `start(initial=None)` | work in a fresh temporary directory, load the FMU, set `initial` (`{input: value}`) and initialise it |
| `read()` | outputs at the current time: `{'step', 'time', 'ts', 'values': {output: float}}` (use it for step 0, before the first `step()`) |
| `set(name, value)`, `set_many({...})` | queue input values in FMU units; applied at the next `step()`. An unknown name raises `KeyError` |
| `step()` | apply the queued values, advance one step, return the same dict as `read()` |
| `close()` | terminate the FMU, restore the working directory, remove the temporary directory. `Building` is also a context manager |

`step()` raises `BuildingStopped` (a `RuntimeError`) when `do_step` fails or when the
EnergyPlus log says the simulation terminated. The log is checked every 12 steps, at
the last step, and whenever all outputs stay exactly constant for 12 steps (constant
outputs alone are not an error: a building can sit at its setpoint for days). Without
the check a dead EnergyPlus keeps returning the last values as if nothing happened.

The FMU starts EnergyPlus in the process working directory, so `start()` changes it to
the temporary directory until `close()`; do not rely on relative paths meanwhile.

Status: at start, at every step, at the end and on a fault `Building` publishes, best
effort (it never raises if the broker is down), retained, QoS 1, on
`platform/building/status`:

```json
{"state": "running|finished|fault", "run": "controlled", "step": 12, "steps_total": 1008,
 "sim_time": "2026-01-01T02:00:00", "message": ""}
```

The broker is `MQTT_BROKER_URL` (default `mosquitto`) and `MQTT_BROKER_PORT` (1883).

### Example gateway loop

```python
import json, os
import paho.mqtt.client as mqtt
from building import Building

commands = {}                                    # input name -> last value from the controller
c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="my_gateway")
c.on_message = lambda cl, u, m: commands.update({m.topic.split("/")[-1]: json.loads(m.payload)["value"]})
c.connect(os.environ.get("MQTT_BROKER_URL", "mosquitto"), int(os.environ.get("MQTT_BROKER_PORT", 1883)))
c.subscribe("mybuilding/command/+"); c.loop_start()

with Building("controlled") as b:
    b.start({name: 20.0 for name in b.inputs})            # initial values, FMU units
    out = b.read()                                        # step 0
    while True:
        for name, value in out["values"].items():
            c.publish(f"mybuilding/{name}", json.dumps({"value": value, "ts": out["ts"]}))
        if b.done:
            break
        b.set_many({k: v for k, v in commands.items() if k in b.inputs})
        out = b.step()
```

## emergency_gateway.py

The platform's own gateway, built on `building.py`. It turns `Field/points.yaml` into the
MQTT contract below, with a priority array for the commands, deadbands, a tick/ack
handshake and the controller summary. It exists so that a group blocked on its own
gateway can still work on the controller and the subscriber.

One-shot, as the supervisor runs it (exit code 0 when the run finished, non-zero on
`fault` or `config_error`):

```
python emergency_gateway.py --once --run baseline|controlled --mode fast|scaled|sync --step-seconds 0.2 [--field-dir ...]
```

- `fast`: as fast as possible, no waiting. For the baseline anything but `scaled` is `fast`.
- `scaled`: one step every `--step-seconds`, no waiting for the ack.
- `sync`: waits for the controller's ack at every step (controlled run only).

Without `--once` it idles as a service and waits for a start command on
`building/<run>/sim/control`. From a notebook: `from emergency_gateway import run;
run("controlled", mode="sync")`. It also publishes `platform/building/status` through
`Building`.

### Teacher

The teacher enables the emergency gateway for a group by creating the flag file
`Workspace/.emergency` from a terminal, for example:

```
docker exec bms_services touch /home/jovyan/work/.emergency
```

From then on, when the Control room starts the building the supervisor runs
`emergency_gateway.py --once ...` instead of the students' `devices/gateway.py`. Remove the
file to go back to the students' gateway:

```
docker exec bms_services rm /home/jovyan/work/.emergency
```

## points.yaml

```yaml
site: {name: lab_optimal, year: 2026}
gateway: {sync_timeout_s: 5, command_timeout_steps: 3, heartbeat_steps: 6}
points:
  - id: kitchen_air_temp                 # your name; becomes the MQTT topic
    fmu: Zone_Mean_Air_Temperature_KITCHEN   # name in the FMU, do not change
    type: measurement
    role: observation                    # observation | reward (informative)
    unit: degC
    scale: 1                             # value = raw * scale + offset
    offset: 0
    deadband: 0.1                        # publish only if it moved more than this
  - id: kitchen_heating_sp
    fmu: KITCHEN_Heating_Setpoint_FMU
    type: command
    unit: degC
    min: 12
    max: 24
    default: 20                          # used when nobody commands the point
```

- `id`: letters, digits, `_` and `-`. It is the topic name.
- The export writes only `fmu`, `type` and `role`; `id`, `unit`, `deadband`,
  `min`, `max` and `default` are left as `# TODO` and the emergency gateway refuses to
  start until they are filled in.
- Measurements: `deadband` (>= 0) is required; `scale` (not 0) and `offset` are optional.
- Commands: `min`, `max` and `default` are required.
- Commands are given in the point unit; the gateway converts back to the FMU unit
  as `(value - offset) / scale`. Values outside `[min, max]` are clamped, and the
  gateway logs it.
- `site.year` is the calendar year used for the timestamps (the weather file
  decides whether it is a leap year).
- `gateway.sync_timeout_s`: how long a step waits for the controller's ack.
  `command_timeout_steps`: validity of a controller command. `heartbeat_steps`:
  a value is re-published at least this often even if it did not change.

The emergency gateway refuses to start (state `config_error`, message on `sim/log`) when:

| Cause | Message (shortened) |
|---|---|
| `fmu` name not in the FMU's `modelDescription.xml` | `fmu name 'X' is not in modelDescription.xml` |
| an FMU input has no command point (controlled run) | `FMU input 'X' has no command point in points.yaml` |
| `default` missing or outside `[min, max]` | `default 30 is outside [12, 24]` |
| `id`, `deadband`, `min` or `max` missing | `point fmu=X: id None is missing ...`, `deadband is missing` |
| `unit` missing | `unit is missing` |
| duplicate id, bad type, bad number, command on an output, measurement on an input | one message per problem |

Fix the file and start again: it is re-read on every start. In the baseline
run, command points that do not exist in the baseline FMU are not checked, and
measurements that do not exist in it are skipped (with a warning).

## MQTT contract

`<run>` is `baseline` or `controlled`. Payloads are JSON. Only the emergency gateway
publishes this contract; your own gateway may use any topics.

| Topic | Direction | Payload |
|---|---|---|
| `building/<run>/sim/control` | to gateway | `{"cmd":"start","mode":"sync"\|"scaled"\|"fast","step_seconds":1}` (baseline: anything but `scaled` runs flat out) or `{"cmd":"stop"}` (service mode only) |
| `building/<run>/sim/status` | gateway, **retained** | `{"state":"idle\|starting\|running\|finished\|fault\|config_error","sim_time","step","steps_total","mode","message","controller"}` (`controller`: see below) |
| `building/<run>/sim/log` | gateway, not retained | `{"ts","level":"info\|warning\|error","msg"}` |
| `building/<run>/<id>/value` | gateway | `{"value","unit","ts","quality":"good\|stale\|fault"}` |
| `building/controlled/<id>/command/operator` | to gateway | `{"value": x}`; empty payload releases |
| `building/controlled/<id>/command/controller` | to gateway | `{"value": x}`; empty payload releases |
| `building/controlled/<id>/active` | gateway | `{"value","source":"operator\|controller\|default","ts"}` |
| `building/<run>/sim/tick` | gateway | `{"step","ts"}`, after the values of that step (both runs) |
| `building/controlled/sim/ack` | to gateway | `{"step"}` |
| `platform/building/status` | `Building`, **retained** | see building.py above |

Notes:

- `ts` is an ISO 8601 date-time of the **simulated** instant, in `site.year`,
  timezone-naive (for example `2026-02-01T00:30:00`). `sim_time` in the status is
  the same kind of string. The `sim/log` `ts` is the wall clock.
- A value is published when it changed by more than its deadband, or after
  `heartbeat_steps` steps; the first value of a run is always published.
  `quality` is `good` while running; after a fault the measurements are published
  once more with `quality: fault`.
- In service mode `status.state` returns to `idle` after a stop and stays at
  `finished` or `fault` until the next start. A new start is accepted in `idle`,
  `finished`, `fault` and `config_error`.
- The baseline accepts no commands and waits for nobody: it runs as fast as
  possible, or in `scaled` mode one step every `step_seconds` so that a live
  subscriber or dashboard can follow it.

### Command priority

For each command point the gateway applies, at every step:

1. `operator` command, if present. It stays until it is released.
2. `controller` command, if present and not expired.
3. `default` from `points.yaml`.

A command is released by publishing an empty payload on its topic. A controller
command that was received in step `n` is valid until step `n + command_timeout_steps`;
if the controller does not refresh it, the point goes back to the next level
(normally `default`). This is the watchdog: a dead controller cannot freeze the
building at its last command. Publish the controller commands again at every tick.
The result, with its source, is on `.../<id>/active`.

### Who controlled the run

In the controlled run the status carries `controller`: `{ticks, acks, timeouts,
commands, last_command_step, points, sources: {operator, controller, default}}`:
how many ticks were acknowledged, how many controller commands arrived and on which
points, and which source drove the command points over the run (counted per point
and step). `sources.default` equal to every point-step means nobody controlled the
building.

### Time modes

- **sync** (default): after the values of step `n` the gateway publishes
  `sim/tick {step: n}` and waits for `sim/ack {step: n}`, up to `sync_timeout_s`.
  Then it applies the active commands and advances one step. On timeout it logs a
  warning and goes on with what it has. The simulation therefore never runs ahead of
  your controller.
- **scaled**: the gateway sleeps `step_seconds` between steps and does not wait for
  the ack. Ticks are still published.
- **fast**: no waiting at all (the only mode of the baseline besides `scaled`).

### Controller loop with tick/ack

```python
import json, os
import paho.mqtt.client as mqtt

values = {}

def on_message(client, userdata, msg):
    parts = msg.topic.split("/")
    if parts[-1] == "value":                      # building/controlled/<id>/value
        values[parts[2]] = json.loads(msg.payload)["value"]
    elif msg.topic == "building/controlled/sim/tick":
        step = json.loads(msg.payload)["step"]
        t = values.get("kitchen_air_temp")
        if t is not None:
            sp = 21.0 if t < 20.0 else 17.0       # your control law
            client.publish("building/controlled/kitchen_heating_sp/command/controller",
                           json.dumps({"value": sp}))
        client.publish("building/controlled/sim/ack", json.dumps({"step": step}))

c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="my_controller")
c.on_connect = lambda cl, *a: cl.subscribe([("building/controlled/#", 0)])
c.on_message = on_message
c.connect(os.environ.get("MQTT_BROKER_URL", "mosquitto"), int(os.environ.get("MQTT_BROKER_PORT", 1883)))
c.loop_forever()
```

Publish the commands before the ack: the gateway applies what it has when the ack
arrives. Values of a step arrive before its tick.

Try an operator override from a shell:

```
mosquitto_pub -t building/controlled/kitchen_heating_sp/command/operator -m '{"value": 16}'
mosquitto_pub -t building/controlled/kitchen_heating_sp/command/operator -n   # release
```

## Faults

The run stops and the state becomes `fault` with a message when EnergyPlus terminates
with a fatal error inside the FMU (the EnergyPlus log is checked with
`fmi_mlc.eplus_health.check_slave`), or when `do_step` raises. The emergency gateway
then publishes its measurements once more with `quality: fault`.

### Logs

- Emergency gateway: its standard output (kept by the supervisor) and the `sim/log` topic.
- Your own gateway, controller and subscriber: their log files in the workspace.
