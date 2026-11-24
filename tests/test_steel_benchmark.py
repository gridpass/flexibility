import importlib.util
from datetime import date
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("benchmark_steel",Path(__file__).resolve().parents[1]/"scripts"/"benchmark_steel.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)

def day():
    return [{"date":f"01/01/2018 {((i+1)*15%1440)//60:02d}:{((i+1)*15%1440)%60:02d}",
             "NSM":str((i+1)*900%86400),"Usage_kWh":"25"} for i in range(96)]

class SteelBenchmarkTests(unittest.TestCase):
    def test_interval_end_and_units(self):
        kwh=bench.read_intervals(day(),date(2018,1,1),1)
        self.assertEqual(sum(kwh),2400)
        self.assertEqual(kwh[0]/1000/bench.DT,0.1)

    def test_duplicate_gap_and_bad_energy_rejected(self):
        for key,value in (("date","01/01/2018 00:15"),("NSM","900"),("Usage_kWh","nan"),("Usage_kWh","-1")):
            rows=day()
            rows[1][key]=value
            with self.assertRaises(ValueError):
                bench.read_intervals(rows,date(2018,1,1),1)
        with self.assertRaises(ValueError):
            bench.read_intervals(day()[:-1],date(2018,1,1),1)

    def test_checksum_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"bad.zip"
            p.write_bytes(b"not the published archive")
            with self.assertRaisesRegex(ValueError,"checksum"):
                bench.read_archive(p)

    def test_nonideal_battery_energy_balance(self):
        kwh=[25.0]*(7*96)
        for d in range(7):
            for i in range(40,56):
                kwh[d*96+i]=50.0
        r=bench.replay(kwh)
        self.assertAlmostEqual(r["peak_mw"],0.2)
        self.assertAlmostEqual(r["no_asset_gap_mwh"],1.4)
        self.assertTrue(r["battery_feasible"])
        self.assertLess(r["battery_gap_mwh"],1e-5)
        self.assertAlmostEqual(r["terminal_soc_mwh"],0.6)
        self.assertGreater(r["battery_losses_mwh"],0)
        self.assertAlmostEqual(r["grid_mwh"],r["measured_mwh"]+r["battery_losses_mwh"],places=5)
