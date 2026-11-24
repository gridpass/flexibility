import math
import unittest
from copy import deepcopy
from gridpass_flexibility.dispatch import evaluate
from gridpass_flexibility.causal import replay
from gridpass_flexibility.thermal import next_temperature

def zone(**kw):
    return {"id":"chiller","kind":"thermal_cooling","power_mw":4,"baseline_cooling_mw":2,
            "thermal_capacitance_mwh_per_k":2,"thermal_conductance_mw_per_k":0,
            "heat_gain_mw":4,"ambient_c":30,"cop":2,"min_temp_c":18,"max_temp_c":24,
            "initial_temp_c":22,"terminal_max_temp_c":22,**kw}
def event(start=1,end=3,cap=8,notice=0):
    return {"start":start,"end":end,"cap_mw":cap,"notice_minutes":notice}
def site(**kw):
    return {"interval_hours":1,"baseline_mw":[10]*6,"normal_import_cap_mw":14,
            "price_eur_mwh":100,"resources":[zone()],"events":[event()],**kw}
def workload(**kw):
    return {"id":"compute","kind":"workload","power_mw":10,"shift_budget_mwh":20,
            "max_delay_hours":4,"recovery_power_mw":10,**kw}
def solar(**kw):
    return {"id":"pv","kind":"renewable","power_mw":3,"availability":[0,1,1,0,0,0],**kw}

class ThermalTests(unittest.TestCase):
    def test_exact_heat_balance(self):
        # equilibrium 30 + (4 - 2*1)/0.5 = 34 C.
        expected=34+(22-34)*math.exp(-.5/2)
        self.assertAlmostEqual(next_temperature(22,30,4,1,2,2,.5,1),expected,places=10)
        self.assertAlmostEqual(next_temperature(22,30,4,0,2,2,0,1),24)
    def test_pre_cooling_and_recovery(self):
        r=evaluate(site())
        self.assertTrue(r["feasible"])
        x=r["schedule"]["resources"]["chiller"]
        self.assertLessEqual(x["temperature_c"][0],20+1e-5)
        self.assertLessEqual(x["temperature_c"][-1],22+1e-5)
        previous=22
        for t,(p,temp) in enumerate(zip(x["cooling_mw"],x["temperature_c"])):
            self.assertAlmostEqual(temp,next_temperature(previous,30,4,p,2,2,0,1),places=5)
            self.assertAlmostEqual(r["schedule"]["grid_import_mw"][t],8+p,places=5)
            previous=temp
        self.assertAlmostEqual(sum(x["cooling_mw"]),12,places=5)
    def test_thermal_limit_blocks_reduction(self):
        r=evaluate(site(resources=[zone(min_temp_c=22,max_temp_c=22)]))
        self.assertFalse(r["feasible"])
        self.assertAlmostEqual(r["uncovered_mwh"],4,places=5)
    def test_loss_of_cooling_not_feasible(self):
        r=evaluate(site(resources=[zone(availability=0)]))
        self.assertEqual(r["status"],"solver_failed")
    def test_causal_temperature_carry_and_surprise(self):
        r=replay(site(normal_import_cap_mw=[10,14,14,14,14,14]),4)
        self.assertEqual(r["status"],"solved")
        self.assertAlmostEqual(r["uncovered_mwh"],2,places=5)
        self.assertFalse(r["feasible"])
        previous=22
        for power,temp in zip(r["schedule"]["resources"]["chiller"]["cooling_mw"],r["schedule"]["resources"]["chiller"]["temperature_c"]):
            self.assertAlmostEqual(temp,next_temperature(previous,30,4,power,2,2,0,1),places=5)
            previous=temp
        self.assertAlmostEqual(r["terminal_state"]["chiller"]["temperature_c"],previous,places=5)
        self.assertAlmostEqual(r["terminal_thermal_shortfall_c"]["chiller"],0,places=5)
    def test_causal_thermal_forecast_prefix(self):
        a=site(resources=[zone(ambient_c=[30]*6,heat_gain_mw=[4]*6,cop=[2]*6),solar()])
        b=deepcopy(a)
        b["resources"][0].update(ambient_c=[30,30,40,40,40,40],heat_gain_mw=[4,4,5,5,5,5],cop=[2,2,1.8,1.8,1.8,1.8])
        b["resources"][1]["availability"][2:]=[0]*4
        x,y=replay(a,4),replay(b,4)
        self.assertEqual(x["observations"][:2],y["observations"][:2])
        self.assertEqual(x["schedule"]["resources"]["chiller"]["cooling_mw"][:2],y["schedule"]["resources"]["chiller"]["cooling_mw"][:2])
        self.assertEqual(x["schedule"]["grid_import_mw"][:2],y["schedule"]["grid_import_mw"][:2])
    def test_protected_load_no_double_counting(self):
        s=site(resources=[zone(min_temp_c=22,max_temp_c=22),workload()],protected_load_mw=7,events=[event(cap=7)])
        r=evaluate(s)
        self.assertFalse(r["feasible"])
        self.assertAlmostEqual(r["uncovered_mwh"],4,places=5)
        self.assertLessEqual(max(r["schedule"]["resources"]["compute"]["shift_mw"]),1+1e-5)
        with self.assertRaisesRegex(ValueError,"exceed total demand"):
            evaluate({**s,"protected_load_mw":9})
    def test_renewable_curtailment_and_supply(self):
        r=evaluate(site(resources=[solar()],protected_load_mw=10))
        self.assertTrue(r["feasible"])
        self.assertAlmostEqual(r["diagnostics"]["observed_limits"][0]["generated_mwh"],6,places=5)
        s=site(resources=[solar(power_mw=20)],protected_load_mw=10)
        r=evaluate(s)
        self.assertAlmostEqual(r["diagnostics"]["observed_limits"][0]["curtailed_mwh"],20,places=5)
        self.assertTrue(replay(s,3)["feasible"])
    def test_variable_cost_cooling(self):
        r=evaluate(site(events=[],resources=[zone(variable_cost_eur_mwh=5)]))
        self.assertAlmostEqual(r["operating_cost_eur"],6060,places=4)
    def test_nonzero_conductance_variable_inputs(self):
        z=zone(thermal_conductance_mw_per_k=.2,ambient_c=[25,26,27,28,29,30],
               heat_gain_mw=[2,2.5,3,3.5,4,4],cop=[3,3,2.5,2.5,2,2])
        r=evaluate(site(resources=[z],events=[]))
        self.assertTrue(r["feasible"])
        previous=z["initial_temp_c"]
        x=r["schedule"]["resources"]["chiller"]
        for t,(p,temp) in enumerate(zip(x["cooling_mw"],x["temperature_c"])):
            self.assertAlmostEqual(temp,next_temperature(previous,z["ambient_c"][t],z["heat_gain_mw"][t],p,z["cop"][t],2,.2,1),places=5)
            previous=temp
    def test_notice_does_not_allow_early_load_reduction(self):
        r=evaluate(site(resources=[zone(response_minutes=120)],events=[event(notice=0)]))
        self.assertFalse(r["feasible"])
        self.assertAlmostEqual(r["uncovered_mwh"],4,places=5)
    def test_thermal_terminal_recovery_not_reset(self):
        s=site(baseline_mw=[10]*2,normal_import_cap_mw=10,events=[event(start=1,end=2)])
        r=replay(s,2)
        self.assertFalse(r["feasible"])
        self.assertEqual(r["status"],"solved")
        self.assertAlmostEqual(r["uncovered_mwh"],0,places=5)
        self.assertAlmostEqual(r["terminal_thermal_shortfall_c"]["chiller"],2,places=5)
    def test_thermal_failure_in_causal_replay(self):
        r=replay(site(resources=[zone(availability=[1,0,0,0,0,0])]),4)
        self.assertFalse(r["feasible"])
        self.assertEqual(r["status"],"replay_failed")
        self.assertEqual(r["executed_intervals"],1)
    def test_validation(self):
        for invalid in [zone(cop=0),zone(thermal_capacitance_mwh_per_k=0),zone(ambient_c=[30]),
                        zone(initial_temp_c=25),zone(baseline_cooling_mw=5)]:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):evaluate(site(resources=[invalid]))
