import importlib.util
from pathlib import Path
import tempfile
import unittest
import numpy as np

spec=importlib.util.spec_from_file_location("benchmark_aau",Path(__file__).resolve().parents[1]/"scripts"/"benchmark_aau.py")
bench=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)

def synthetic(seed):
    rng=np.random.default_rng(seed)
    a=np.zeros((720,5))
    a[:,0]=np.arange(720)*2
    a[:,1]=20
    a[:,2]=rng.uniform(15,23,720)
    a[:,3]=rng.uniform(.2,.8,720)
    a[:,4]=1+rng.uniform(0,.4,720)
    for t in range(719):
        a[t+1,1]=4+.5*a[t,1]+.25*a[t,2]+2*a[t,3]
    return a

class MeasuredBenchmarkTests(unittest.TestCase):
    def test_known_empirical_equation(self):
        r=bench.fit_holdout([synthetic(1),synthetic(2),synthetic(3)],synthetic(4))
        self.assertEqual(r["training_samples"],2157)
        self.assertEqual(r["heldout_samples"],719)
        self.assertLess(r["heldout_mae_c"],1e-10)
        self.assertGreater(r["persistence_mae_c"],.1)
    def test_holdout_cannot_change_fit(self):
        train=[synthetic(1),synthetic(2)]
        x=synthetic(3);y=x.copy();y[:,1]+=10
        self.assertEqual(bench.fit_holdout(train,x)["coefficients"],bench.fit_holdout(train,y)["coefficients"])
    def test_no_silent_gap_fill(self):
        x=synthetic(1);x[10,0]+=1
        with self.assertRaises(ValueError):bench.validate_run(x)
    def test_no_unphysical_power(self):
        x=synthetic(1);x[3,3]=x[3,4]+1
        with self.assertRaises(ValueError):bench.validate_run(x)
    def test_pinned_archive(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"bad.tar.xz";p.write_bytes(b"wrong dataset")
            with self.assertRaisesRegex(ValueError,"checksum"):bench.read_runs(p)
    def test_normalized_dispatch_balance(self):
        x=synthetic(5);bench.validate_run(x)
        r=bench.normalized_dispatch(x)
        self.assertAlmostEqual(r["no_asset_uncovered_mwh"],r["independent_uncovered_mwh"],places=6)
        self.assertTrue(r["battery_feasible"])
        self.assertAlmostEqual(r["battery_uncovered_mwh"],0,places=6)
