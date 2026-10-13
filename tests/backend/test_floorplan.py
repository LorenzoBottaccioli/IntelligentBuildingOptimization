"""The floor plan of a model (backend/floorplan.py), from the DXF and EIO that EnergyPlus writes.

From the repository root (only the standard library is needed):

    python -m unittest tests.backend.test_floorplan

The fixture is the demo building (tests/fixtures/floorplan): four triangular zones that meet in the
centre of a 15 x 15 m square, with windows on the outside walls. The other cases change that data.
"""

import copy
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'backend'))
FIXTURE = os.path.join(ROOT, 'tests', 'fixtures', 'floorplan')

import floorplan  # noqa: E402


def demo():
    return (floorplan.read_dxf(os.path.join(FIXTURE, 'demo.dxf')),
            floorplan.eio_tables(os.path.join(FIXTURE, 'demo.eio')))


class DemoPlan(unittest.TestCase):
    def setUp(self):
        self.plan = floorplan.build_plan(*demo())

    def test_four_zones_each_from_its_floor_surface(self):
        zones = self.plan['zones']
        self.assertEqual(sorted(z['name'] for z in zones),
                         ['BLOCK1:ZONEEAST', 'BLOCK1:ZONENORTH', 'BLOCK1:ZONESOUTH', 'BLOCK1:ZONEWEST'])
        for z in zones:
            self.assertEqual(z['kind'], 'floor')
            self.assertTrue(z['checked'])
            self.assertAlmostEqual(z['areaFaces'], 56.25, places=1)      # 15 x 7.5 / 2

    def test_one_level_with_the_four_zones(self):
        self.assertEqual(len(self.plan['levels']), 1)
        self.assertEqual(len(self.plan['levels'][0]['zones']), 4)
        self.assertEqual(self.plan['unmatchedLayers'], [])

    def test_the_label_of_each_zone_is_inside_its_floor(self):
        for z in self.plan['zones']:
            self.assertTrue(any(floorplan._inside(tuple(z['label']), poly) for poly in z['polygons']), z['name'])

    def test_zones_lie_where_their_name_says(self):
        centre = {z['name'].split('ZONE')[1]: z['label'] for z in self.plan['zones']}
        self.assertLess(centre['WEST'][0], centre['EAST'][0])
        self.assertLess(centre['SOUTH'][1], centre['NORTH'][1])

    def test_markers_are_percentages_from_the_top_left(self):
        marks = floorplan.markers(self.plan, 0)
        self.assertEqual(len(marks), 4)
        west, east = marks['BLOCK1:ZONEWEST'], marks['BLOCK1:ZONEEAST']
        north, south = marks['BLOCK1:ZONENORTH'], marks['BLOCK1:ZONESOUTH']
        self.assertLess(west[0], east[0])
        self.assertLess(north[1], south[1])                              # north is up: smaller y from the top
        for x, y in marks.values():
            self.assertTrue(0 < x < 100 and 0 < y < 100)

    def test_svg_has_a_group_per_zone(self):
        svg = floorplan.plan_svg(self.plan, 0)
        for z in self.plan['zones']:
            self.assertIn('id="zone-{}"'.format(z['key']), svg)
        self.assertEqual(floorplan.plan_svg(self.plan, 7), '')


class Outline(unittest.TestCase):
    def test_the_shared_edge_of_two_triangles_cancels(self):
        a = [(0, 0), (4, 0), (4, 4)]
        b = [(0, 0), (4, 4), (0, 4)]
        segments = floorplan.outline([a, b])
        self.assertEqual(len(segments), 4)
        self.assertNotIn({(0, 0), (4, 4)}, [set(s) for s in segments])

    def test_a_vertex_on_the_neighbours_edge_splits_it(self):
        # a square on the left, two triangles on the right: the edge x = 4 is whole on one side and in two halves on the other
        left = [(0, 0), (4, 0), (4, 4), (0, 4)]
        low = [(4, 0), (8, 0), (4, 2)]
        high = [(4, 2), (8, 0), (8, 4), (4, 4)]
        segments = floorplan.outline([left, low, high])
        self.assertFalse(any(abs(a[0] - 4) < 1e-9 and abs(b[0] - 4) < 1e-9 for a, b in segments))

    def test_demo_triangles_have_three_sides(self):
        for z in floorplan.build_plan(*demo())['zones']:
            self.assertEqual(len(floorplan.outline(z['polygons'])), 3)


class Reading(unittest.TestCase):
    def test_a_comment_belongs_to_the_face_after_it(self):
        dxf, _ = demo()
        by_surface = {}
        for f in dxf['faces']:
            by_surface.setdefault(f['surface'], []).append(f)
        floor = by_surface['BLOCK1:ZONEWEST:BLOCK1:ZONEWEST_GROUNDFLOOR_0_0_0']
        self.assertEqual(len(floor), 1)
        self.assertEqual({round(p[2], 3) for p in floor[0]['points']}, {0.0})

    def test_layer_key(self):
        self.assertEqual(floorplan.layer_key('Block1:Zone West'), 'BLOCK1_ZONE_WEST')


class WhenTheFloorIsMissing(unittest.TestCase):
    def test_a_zone_without_a_floor_surface_uses_the_downward_horizontal_faces(self):
        dxf, tables = demo()
        tables = copy.deepcopy(tables)
        for row in tables['surfaces'].values():
            if row['Surface Class'] == 'Floor':
                row['Surface Class'] = 'Wall'                      # no surface of class Floor left
        plan = floorplan.build_plan(dxf, tables)
        for z in plan['zones']:
            self.assertEqual(z['kind'], 'derived')
            self.assertFalse(z['checked'])

    def test_a_zone_without_faces_falls_back_to_the_bounding_box_then_to_nothing(self):
        dxf, tables = demo()
        dxf = {'layers': dxf['layers'], 'faces': []}
        plan = floorplan.build_plan(dxf, tables)
        self.assertEqual({z['kind'] for z in plan['zones']}, {'bbox'})
        west = next(z for z in plan['zones'] if z['name'].endswith('WEST'))
        self.assertEqual(len(west['polygons'][0]), 4)
        tables = copy.deepcopy(tables)
        for row in tables['zones'].values():
            row['Minimum X {m}'] = row['Maximum X {m}'] = ''
        plan = floorplan.build_plan(dxf, tables)
        self.assertEqual({z['kind'] for z in plan['zones']}, {'none'})
        self.assertEqual(plan['levels'], [])

    def test_a_model_without_any_zone_gives_an_empty_plan(self):
        plan = floorplan.build_plan({'layers': [], 'faces': []}, {'zones': {}, 'surfaces': {}})
        self.assertEqual(plan, {'zones': [], 'levels': [], 'unmatchedLayers': []})

    def test_overlap_ratio_tells_a_map_from_a_stack(self):
        side = {'level': 0, 'bbox': [0, 0, 10, 10]}
        a, b = dict(side), {'level': 0, 'bbox': [10, 0, 20, 10]}
        self.assertEqual(floorplan.overlap_ratio({'zones': [a, b]}, 0), 0.0)             # neighbours
        self.assertEqual(floorplan.overlap_ratio({'zones': [a, dict(side)]}, 0), 1.0)    # one on top of the other


if __name__ == '__main__':
    unittest.main()
