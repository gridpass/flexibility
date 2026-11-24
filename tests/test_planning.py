import unittest
from gridpass_flexibility.planning import size_capacity
from gridpass_flexibility.stress import build_stress_suite, test_commitment
from gridpass_flexibility.profiles import evaluate_profile

def site(**kw):
    return {"interval_hours":1,"baseline_mw":[10]*8,"normal_import_cap_mw":14,
            "price_eur_mwh":100,"resources":[],"events":[{"start":2,"end":4,"cap_mw":8,"notice_minutes":60}],**kw}
def battery(**kw):
    return {"id":"b","kind":"battery","max_power_mw":8,"max_energy_mwh":20,"cost_eur_per_mw":1000,"cost_eur_per_mwh":1000,
            "charge_efficiency":1,"discharge_efficiency":1,**kw}
def generator(**kw):
    return {"id":"g","kind":"generator","max_power_mw":8,"cost_eur_per_mw":1000,"variable_cost_eur_mwh":300,**kw}
def profile(**kw):
    return {"id":"open-test","version":"1","notice_minutes":60,"activation_hours":24,"annual_event_hours":48,
            "reduction_mw":2,"minimum_recovery_hours":24,**kw}

class Planning(unittest.TestCase):
    def test_analytical_battery_size(self):
        r=size_capacity([{"id":"one","scenario":site()}],[battery()])
        self.assertEqual(r["status"],"solved")
        self.assertAlmostEqual(r["capacities"]["b"]["power_mw"],2,places=5)
        self.assertAlmostEqual(r["capacities"]["b"]["energy_mwh"],4,places=5)
        self.assertAlmostEqual(r["allocated_capex_eur"],6000,places=4)
    def test_shared_capacity_across_two_cases(self):
        long=site(events=[{"start":2,"end":5,"cap_mw":8,"notice_minutes":60}])
        r=size_capacity([{"id":"short","scenario":site()},{"id":"long","scenario":long}],[battery()])
        self.assertTrue(r["all_cases_feasible"])
        self.assertAlmostEqual(r["capacities"]["b"]["power_mw"],2,places=5)
        self.assertAlmostEqual(r["capacities"]["b"]["energy_mwh"],6,places=5)
    def test_zero_weight_case_requires_capacity(self):
        deeper=site(events=[{"start":2,"end":4,"cap_mw":7,"notice_minutes":60}])
        r=size_capacity([{"id":"normal","scenario":site()},{"id":"stress","scenario":deeper,"weight":0}],[battery()])
        self.assertTrue(r["all_cases_feasible"])
        self.assertAlmostEqual(r["capacities"]["b"]["power_mw"],3,places=5)
        self.assertAlmostEqual(r["capacities"]["b"]["energy_mwh"],6,places=5)
    def test_outage_needs_backup(self):
        r=size_capacity([{"id":"normal","scenario":site()},{"id":"outage","scenario":site(),"weight":0,
                         "new_resource_availability":{"g":0}}],[generator(),battery()])
        self.assertTrue(r["all_cases_feasible"])
        self.assertAlmostEqual(r["capacities"]["b"]["power_mw"],2,places=5)
    def test_generator_least_cost(self):
        r=size_capacity([{"id":"one","scenario":site()}],[battery(),generator()])
        self.assertTrue(r["all_cases_feasible"])
        self.assertAlmostEqual(r["capacities"]["g"]["power_mw"],2,places=5)
        self.assertAlmostEqual(r["capacities"]["b"]["power_mw"],0,places=5)
    def test_infeasible(self):
        r=size_capacity([{"id":"one","scenario":site()}],[generator(max_power_mw=1)])
        self.assertEqual(r["status"],"infeasible")
    def test_reserve_fraction(self):
        r=size_capacity([{"id":"one","scenario":site()}],[battery(reserve_fraction=.5)])
        self.assertTrue(r["all_cases_feasible"])
        self.assertAlmostEqual(r["capacities"]["b"]["energy_mwh"],8,places=5)
    def test_annual_stress_suite(self):
        s=site(interval_hours=24,baseline_mw=[10]*365,resources=[{"id":"g","kind":"generator","power_mw":2}])
        cases=build_stress_suite(s,profile(),["g"])
        self.assertEqual([c["id"] for c in cases],["distributed","clustered","clustered-outage-g"])
        for c in cases:
            self.assertEqual(sum(e["end"]-e["start"] for e in c["scenario"]["events"]),2)
            self.assertTrue(all(e["cap_mw"]==8 for e in c["scenario"]["events"]))
        r=test_commitment(s,profile(),["g"])
        self.assertEqual(r["result"],"modeled_cases_fail")
        self.assertTrue(r["cases"][0]["feasible"])
        self.assertFalse(r["cases"][2]["feasible"])
    def test_annual_notice_not_covered(self):
        s=site(interval_hours=24,baseline_mw=[10]*365,resources=[{"id":"g","kind":"generator","power_mw":2}],
               events=[{"start":1,"end":3,"cap_mw":8,"notice_minutes":120}])
        p=profile()
        r=evaluate_profile(p,[s])
        self.assertFalse(r["coverage"]["annual_usage"])
        self.assertEqual(r["result"],"incomplete_coverage")
    def test_impossible_recovery_budget(self):
        s=site(interval_hours=24,baseline_mw=[10]*365)
        with self.assertRaises(ValueError):build_stress_suite(s,profile(annual_event_hours=8760))
