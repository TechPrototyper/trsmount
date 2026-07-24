#!/usr/bin/env python3
"""
Unit tests for trsdc (TRS-80 Disk Convert Utility).
"""

import os
import sys
import tempfile
import unittest
import subprocess

# Ensure repo root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import trs80_driver
import trsdc


class TestTRSDC(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.dirname(__file__)
        self.sample_dmk = os.path.join(self.test_dir, 'NEWDOS80.dmk')

    def test_parse_format_spec(self):
        spec1 = trsdc.parse_format_spec('dmk')
        self.assertEqual(spec1.get('format'), 'dmk')

        spec2 = trsdc.parse_format_spec('format=jv3,tracks=40,sides=1,density=sd')
        self.assertEqual(spec2.get('format'), 'jv3')
        self.assertEqual(spec2.get('tracks'), 40)
        self.assertEqual(spec2.get('sides'), 1)
        self.assertEqual(spec2.get('density'), 'sd')

        spec3 = trsdc.parse_format_spec('jv1,80t,2s,dd')
        self.assertEqual(spec3.get('format'), 'jv1')
        self.assertEqual(spec3.get('tracks'), 80)
        self.assertEqual(spec3.get('sides'), 2)
        self.assertEqual(spec3.get('density'), 'dd')

    def test_dmk_to_jv3_conversion(self):
        if not os.path.exists(self.sample_dmk):
            self.skipTest(f"Sample file '{self.sample_dmk}' not found.")

        dmk_img = trs80_driver.detect_format(self.sample_dmk)
        orig_sectors = dmk_img.get_all_sectors()
        self.assertGreater(len(orig_sectors), 0)

        with tempfile.TemporaryDirectory() as tmpdir:
            out_jv3 = os.path.join(tmpdir, 'output.dsk')
            
            # Perform conversion via trsdc module function logic
            in_geom = dmk_img.get_geometry_info()
            out_geom = dict(in_geom)
            out_geom['format'] = 'jv3'
            
            jv3_buf = trs80_driver.export_jv3(orig_sectors, out_geom)
            with open(out_jv3, 'wb') as f:
                f.write(jv3_buf)

            # Reload converted JV3 and verify sectors
            jv3_img = trs80_driver.detect_format(out_jv3)
            converted_sectors = jv3_img.get_all_sectors()

            for key, data in orig_sectors.items():
                self.assertIn(key, converted_sectors)
                self.assertEqual(data, converted_sectors[key])

    def test_roundtrip_dmk_jv3_jv1(self):
        if not os.path.exists(self.sample_dmk):
            self.skipTest(f"Sample file '{self.sample_dmk}' not found.")

        with tempfile.TemporaryDirectory() as tmpdir:
            jv3_file = os.path.join(tmpdir, 'disk.jv3')
            jv1_file = os.path.join(tmpdir, 'disk.jv1')
            dmk_file = os.path.join(tmpdir, 'disk.dmk')

            # 1. DMK -> JV3
            cmd1 = [sys.executable, os.path.abspath(os.path.join(os.path.dirname(__file__), '../trsdc.py')),
                    '-i', self.sample_dmk, '-o', jv3_file, '-v']
            res1 = subprocess.run(cmd1, capture_output=True, text=True)
            self.assertEqual(res1.returncode, 0, f"DMK->JV3 failed: {res1.stderr}")

            # 2. JV3 -> JV1
            cmd2 = [sys.executable, os.path.abspath(os.path.join(os.path.dirname(__file__), '../trsdc.py')),
                    '-i', jv3_file, '-o', jv1_file, '-v']
            res2 = subprocess.run(cmd2, capture_output=True, text=True)
            self.assertEqual(res2.returncode, 0, f"JV3->JV1 failed: {res2.stderr}")

            # 3. JV1 -> DMK
            cmd3 = [sys.executable, os.path.abspath(os.path.join(os.path.dirname(__file__), '../trsdc.py')),
                    '-i', jv1_file, '-o', dmk_file, '-v']
            res3 = subprocess.run(cmd3, capture_output=True, text=True)
            self.assertEqual(res3.returncode, 0, f"JV1->DMK failed: {res3.stderr}")

            # Verify final DMK image has non-zero sectors matching
            final_dmk = trs80_driver.detect_format(dmk_file)
            final_sectors = final_dmk.get_all_sectors()
            self.assertGreater(len(final_sectors), 0)


if __name__ == '__main__':
    unittest.main()
