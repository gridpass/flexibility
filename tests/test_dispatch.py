import unittest
from gridpass_flexibility.dispatch import evaluate, compare_designs
from gridpass_flexibility.profiles import evaluate_profile

def base(**kw):
    return {"interval_hours":1,"baseline_mw":[10]*6,"normal_import_cap_mw":12,
            "price_eur_mwh":100,"events":[{"start":1,"end":3,"notice_minutes":60,"cap_mw":8}],"resources":[],**kw}

def battery(**kw):
    return {"id":"b","kind":"battery","power_mw":2,"energy_mwh":4,"charge_efficiency":1,"discharge_efficiency":1,**kw}

class Chronological(unittest.TestCase):
    def test_no_resources(self):
        r=evaluate(base());self.assertFalse(r["feasible"]);self.assertAlmostEqual(r["uncovered_mwh"],4,places=5)
    def test_battery_and_terminal_energy(self):
        r=evaluate(base(resources=[battery()]));self.assertTrue(r["feasible"])
        b=r["schedule"]["resources"]["b"];self.assertAlmostEqual(b["soc_mwh"][-1],4,places=5)
        for t in range(6):self.assertAlmostEqual(r["schedule"]["grid_import_mw"][t]+b["discharge_mw"][t]-b["charge_mw"][t],10,places=5)
    def test_recharge_constraint(self):
        r=evaluate(base(normal_import_cap_mw=10,resources=[battery()]));self.assertFalse(r["feasible"])
        self.assertAlmostEqual(r["uncovered_mwh"],4,places=5)
    def test_generation_fuel(self):
        g={"id":"g","kind":"generator","power_mw":2,"fuel_budget_mwh":2,"variable_cost_eur_mwh":200}
        r=evaluate(base(resources=[g]));self.assertAlmostEqual(r["uncovered_mwh"],2,places=5)
    def test_shift_recovered(self):
        g={"id":"compute","kind":"workload","power_mw":2,"shift_budget_mwh":4,"max_delay_hours":4}
        r=evaluate(base(resources=[g]));self.assertTrue(r["feasible"]);s=r["schedule"]["resources"]["compute"]
        self.assertAlmostEqual(sum(s["shift_mw"]),sum(s["recovery_mw"]),places=5)
        self.assertAlmostEqual(s["backlog_mwh"][-1],0,places=5)
    def test_shift_deadline(self):
        g={"id":"compute","kind":"workload","power_mw":2,"shift_budget_mwh":4,"max_delay_hours":1}
        r=evaluate(base(resources=[g]));self.assertFalse(r["feasible"])
    def test_event_notice(self):
        g={"id":"compute","kind":"workload","power_mw":2,"shift_budget_mwh":4,"max_delay_hours":4,"response_minutes":120}
        r=evaluate(base(resources=[g]));self.assertFalse(r["feasible"])
        self.assertAlmostEqual(r["uncovered_mwh"],2,places=5)
    def test_design_comparison(self):
        r=compare_designs(base(),[{"id":"battery","resources":[battery()],"fixed_cost_eur":100}])
        self.assertEqual(r["recommended"],"battery")
    def test_profile_partial(self):
        p={"id":"test","version":"1","notice_minutes":60,"activation_hours":2,"annual_event_hours":87.6,"reduction_mw":2}
        r=evaluate_profile(p,[base(resources=[battery()])]);self.assertEqual(r["result"],"incomplete_coverage")
    def test_profile_full_year(self):
        p={"id":"test","version":"1","notice_minutes":0,"activation_hours":2,"annual_event_hours":2,"reduction_mw":2}
        s=base(interval_hours=2,baseline_mw=[10]*4380,normal_import_cap_mw=12,
               events=[{"start":1,"end":2,"notice_minutes":0,"cap_mw":8}],resources=[{"id":"g","kind":"generator","power_mw":2,"variable_cost_eur_mwh":200}])
        r=evaluate_profile(p,[s]);self.assertEqual(r["result"],"modeled_cases_pass")
    def test_no_reduction_cannot_count_as_profile_coverage(self):
        p={"id":"test","version":"1","notice_minutes":0,"activation_hours":2,"annual_event_hours":2,"reduction_mw":2}
        s=base(interval_hours=2,baseline_mw=[10]*4380,normal_import_cap_mw=12,
               events=[{"start":1,"end":2,"notice_minutes":0,"cap_mw":10}])
        self.assertEqual(evaluate_profile(p,[s])["result"],"incomplete_coverage")
    def test_overlap_rejected(self):
        with self.assertRaises(ValueError):evaluate(base(events=[{"start":1,"end":3,"notice_minutes":0,"cap_mw":8},{"start":2,"end":4,"notice_minutes":0,"cap_mw":8}]))
    def test_hash(self):
        a=evaluate(base());b=evaluate(base());self.assertEqual(a["evidence"]["scenario_sha256"],b["evidence"]["scenario_sha256"])
        self.assertEqual(a["evidence"]["result_sha256"],b["evidence"]["result_sha256"])
