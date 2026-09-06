import unittest
import hashlib
import json
from pathlib import Path
from scripts.blender.pimm_production.pimm_operating_motion import pose

class OperatingMotionTests(unittest.TestCase):
    def test_supplied_mold_provenance_and_dimensions(self):
        fixture=Path(__file__).parents[1]/'blender/pimm_production/fixtures/4040-single-cavity.glb'
        provenance=json.loads(fixture.with_suffix('.json').read_text())
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest().upper(),provenance['glb_sha256'])
        self.assertEqual(provenance['assembly_bounds_mm'],[80,30,49])
        self.assertEqual(provenance['mesh_count'],6)

    def test_clockwise_turn_after_unlock_and_before_relock(self):
        self.assertEqual(pose('pressure',0)['lock_lift_mm'],0)
        self.assertEqual(pose('pressure',.21)['lock_lift_mm'],3)
        self.assertEqual(pose('pressure',.21)['clockwise_degrees'],0)
        self.assertLess(pose('pressure',.5)['clockwise_degrees'],0)
        self.assertEqual(pose('pressure',1)['clockwise_degrees'],-135)
        self.assertEqual(pose('pressure',1)['lock_lift_mm'],0)

    def test_connected_plunger_stroke_holds_and_returns(self):
        for t in (0,1): self.assertEqual(pose('actuator',t)['stroke_mm'],0)
        for t in (.5,.6,.7): self.assertEqual(pose('actuator',t)['stroke_mm'],-145)

    def test_temperature_start_ramp_and_two_confirmation_blinks(self):
        self.assertFalse(pose('temperature',0)['powered'])
        self.assertEqual(pose('temperature',.1)['upper_pv'],25)
        self.assertEqual(pose('temperature',1)['upper_pv'],215)
        self.assertEqual(pose('temperature',1)['lower_pv'],220)
        for t in (.80,.88):self.assertTrue(pose('temperature',t)['blink'])
        for t in (.77,.84,.94):self.assertTrue(pose('temperature',t)['confirmed'])

    def test_mold_settles_and_pour_withdraws(self):
        self.assertEqual(pose('mounting',0)['mold_y'],-260)
        self.assertEqual(pose('mounting',1)['mold_y'],0)
        self.assertEqual(pose('pellets',.5)['pour'],1)
        self.assertEqual(pose('pellets',1)['pour'],0)

if __name__=='__main__': unittest.main()
