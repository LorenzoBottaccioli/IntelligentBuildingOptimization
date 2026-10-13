"""Put the files of hmi_prototype.py in the live openHAB and Home Assistant of the repository folder, and restart both.

    python tests/floorplan/hmi_prototype.py --dxf ... --eio ... --out <folder>
    python tests/floorplan/install_prototype.py <folder>

What it writes (the containers are stopped while it does, because openHAB does not reload the files of a Windows bind mount
and Home Assistant keeps its dashboard in memory):

    openhab/conf/things|items|sitemaps/simbuilding.*      (REPLACED: take a copy first)
    openhab/conf/html/floorplan/plan.svg                   -> /static/floorplan/plan.svg
    openhab/jsondb/uicomponents_ui_page.json               (REPLACED: the pages `overview` = floor plan and `controls`)
    homeassistant/config/mqtt.yaml                         (REPLACED)
    homeassistant/config/www/floorplan/*.svg               -> /local/floorplan/
    homeassistant/config/.storage/lovelace.lovelace        (REPLACED: dashboard Plan, Rooms, Energy)

Nothing here is imported by the platform, and the sessions do not carry the two image folders yet.
"""

import glob
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def main():
    src = os.path.abspath(sys.argv[1])
    subprocess.run(['docker', 'stop', 'openhab', 'homeassistant'], check=True, capture_output=True)
    try:
        for name, sub in (('simbuilding.things', 'things'), ('simbuilding.items', 'items'), ('simbuilding.sitemap', 'sitemaps')):
            shutil.copy(os.path.join(src, 'openhab', name), os.path.join(ROOT, 'openhab', 'conf', sub, name))
        html = os.path.join(ROOT, 'openhab', 'conf', 'html', 'floorplan')
        os.makedirs(html, exist_ok=True)
        shutil.copy(os.path.join(src, 'plan.svg'), html)
        shutil.copy(os.path.join(src, 'openhab', 'uicomponents_ui_page.json'), os.path.join(ROOT, 'openhab', 'jsondb'))

        cfg = os.path.join(ROOT, 'homeassistant', 'config')
        www = os.path.join(cfg, 'www', 'floorplan')
        os.makedirs(www, exist_ok=True)
        for f in glob.glob(os.path.join(src, '*.svg')):
            shutil.copy(f, www)
        shutil.copy(os.path.join(src, 'homeassistant', 'mqtt.yaml'), os.path.join(cfg, 'mqtt.yaml'))
        with open(os.path.join(src, 'homeassistant', 'lovelace.json'), encoding='utf-8') as f:
            config = json.load(f)
        with open(os.path.join(cfg, '.storage', 'lovelace.lovelace'), 'w', encoding='utf-8') as f:
            json.dump({'version': 1, 'minor_version': 1, 'key': 'lovelace.lovelace', 'data': {'config': config}}, f, indent=2, ensure_ascii=False)
    finally:
        subprocess.run(['docker', 'start', 'openhab', 'homeassistant'], check=True, capture_output=True)
    print('installed; openHAB needs about a minute, Home Assistant about 30 s')


if __name__ == '__main__':
    main()
