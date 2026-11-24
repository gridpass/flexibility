import unittest
from itertools import product
from gridpass_flexibility.dispatch import evaluate
from gridpass_flexibility.planning import size_capacity

def site(resources, caps, **kw):
    n=len(caps)
    return dict(interval_hours=1,baseline_mw=[10]*n,normal_import_cap_mw=caps,
                price_eur_mwh=0,resources=resources,events=[],**kw)

def gen(**kw):
    return dict(id="g",kind="generator",power_mw=4,discrete=True,minimum_output_mw=2,
                minimum_up_hours=2,minimum_down_hours=2,startup_cost_eur=30,
                online_cost_eur_per_hour=10,variable_cost_eur_mwh=5,**kw)

class DiscreteDispatch(unittest.TestCase):
    def test_start_cost_and_minimum_up_time(self):
        r=evaluate(site([gen()],[10,8,10,10,10]))
        self.assertTrue(r["feasible"])
        self.assertIn("milp",r["evidence"]["solver"])
        g=r["schedule"]["resources"]["g"]
        self.assertEqual(sum(g["startup"]),1)
        self.assertEqual(sum(g["online"]),2)
        self.assertAlmostEqual(sum(g["generation_mw"]),4,places=5)
        self.assertAlmostEqual(r["commitment_cost_eur"],50,places=5)
        self.assertAlmostEqual(r["operating_cost_eur"],70,places=5)

    def test_minimum_down_time(self):
        g=gen();g.update(minimum_up_hours=1,minimum_down_hours=2)
        r=evaluate(site([g],[8,10,8,10,10]))
        self.assertTrue(r["feasible"])
        t=r["schedule"]["resources"]["g"]
        self.assertEqual(t["online"][:3],[1,1,1])
        self.assertEqual(sum(t["startup"]),1)

    def test_initial_lockout(self):
        r=evaluate(site([gen(initial_on=False,initial_state_hours=0)],[8,8,10,10]))
        self.assertFalse(r["feasible"])
        self.assertAlmostEqual(r["uncovered_mwh"],4,places=5)

    def test_initial_online_obligation(self):
        r=evaluate(site([gen(initial_on=True,initial_mw=2,initial_state_hours=0)],[10]*4))
        self.assertTrue(r["feasible"])
        t=r["schedule"]["resources"]["g"]
        self.assertEqual(t["online"][:2],[1,1])
        self.assertEqual(sum(t["startup"]),0)

    def test_incompatible_outage_is_not_a_pass(self):
        r=evaluate(site([gen(initial_on=True,initial_mw=2,initial_state_hours=0,availability=[0,1,1])],[10]*3))
        self.assertEqual(r["status"],"solver_failed")
        self.assertEqual(r["solver_status"],2)

    def test_battery_cannot_dissipate_through_simultaneous_modes(self):
        # A must-run 4 MW generator feeds a 0 MW load for one interval.
        # A full lossy battery could absorb energy via a fictitious charge/discharge loop.
        # With exact modes and full terminal SOC the case is physically infeasible.
        g=gen(initial_on=True,initial_mw=4,initial_state_hours=0)
        g.update(minimum_output_mw=4,minimum_up_hours=1)
        b=dict(id="b",kind="battery",power_mw=12,energy_mwh=10,initial_mwh=10,
               terminal_mwh=10,charge_efficiency=.5,discharge_efficiency=1)
        s=dict(interval_hours=1,baseline_mw=[0],normal_import_cap_mw=0,price_eur_mwh=0,events=[],resources=[g,b])
        self.assertEqual(evaluate(s)["status"],"solved")
        b["discrete"]=True
        self.assertEqual(evaluate(s)["status"],"solver_failed")

    def test_battery_exact_mode_and_recharge(self):
        b=dict(id="b",kind="battery",discrete=True,power_mw=2,energy_mwh=4,
               charge_efficiency=1,discharge_efficiency=1)
        r=evaluate(site([b],[8,8,12,12]))
        self.assertTrue(r["feasible"])
        t=r["schedule"]["resources"]["b"]
        self.assertAlmostEqual(t["soc_mwh"][-1],4,places=5)
        for c,d,m in zip(t["charge_mw"],t["discharge_mw"],t["charging_mode"]):
            self.assertLessEqual(c*d,1e-8)
            self.assertIn(m,(0,1))

    def test_sizing_does_not_silently_relax(self):
        case={"id":"one","scenario":site([gen()],[8,8,10])}
        option={"id":"new","kind":"generator","max_power_mw":5,"cost_eur_per_mw":100}
        with self.assertRaisesRegex(ValueError,"discrete"):
            size_capacity([case],[option])
        with self.assertRaisesRegex(ValueError,"discrete"):
            size_capacity([{"id":"one","scenario":site([],[8,8,10])}],[dict(option,discrete=True)])

    def test_exhaustive_commitment_cost_crosscheck(self):
        # Independent enumeration for five one-hour intervals. A 2 MW
        # minimum and 4 MW maximum, zero grid price, no ramp/fuel restriction.
        caps=[8,10,8,10,8]
        costs=[]
        for flags in product((0,1),repeat=len(caps)):
            prev=0; transitions=[]; valid=True
            for t,on in enumerate(flags):
                if 10-caps[t]>4*on:valid=False;break
                if on!=prev:
                    if any(x!=on for x in flags[t:min(t+2,len(caps))]):valid=False;break
                    transitions.append(on)
                prev=on
            if valid:
                costs.append(30*sum(transitions)+10*sum(flags)+5*sum(max(2*on,10-cap) for on,cap in zip(flags,caps)))
        r=evaluate(site([gen()],caps))
        self.assertTrue(r["feasible"])
        self.assertAlmostEqual(r["operating_cost_eur"],min(costs),places=5)

    def test_half_hour_notice_and_ramp(self):
        g=gen(response_minutes=30,ramp_mw_per_hour=4)
        g.update(minimum_up_hours=.5,minimum_down_hours=.5)
        s=site([g],[10]*6)
        s["interval_hours"]=.5
        s["events"]=[dict(start=1,end=3,notice_minutes=0,cap_mw=8)]
        r=evaluate(s)
        self.assertFalse(r["feasible"])
        self.assertAlmostEqual(r["uncovered_mwh"],1,places=5)
        self.assertAlmostEqual(r["schedule"]["resources"]["g"]["generation_mw"][2],2,places=5)

    def test_invalid_commitment_fields(self):
        g=gen();g["discrete"]=False
        with self.assertRaisesRegex(ValueError,"discrete generator"):
            evaluate(site([g],[8,8,10]))
        with self.assertRaisesRegex(ValueError,"initial generator"):
            evaluate(site([gen(initial_on=False,initial_mw=2)],[8,8,10]))
