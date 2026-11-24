import unittest
from copy import deepcopy
from unittest.mock import patch
from gridpass_flexibility.causal import replay
from gridpass_flexibility.dispatch import evaluate

def site(n=8, **kw):
    return {"interval_hours":1,"baseline_mw":[10]*n,"normal_import_cap_mw":12,
            "price_eur_mwh":100,"events":[],"resources":[],**kw}

def event(start=2,end=4,notice=0,cap=8):
    return {"start":start,"end":end,"notice_minutes":notice,"cap_mw":cap}

def battery(**kw):
    return {"id":"b","kind":"battery","discrete":True,"power_mw":2,"energy_mwh":4,
            "charge_efficiency":1,"discharge_efficiency":1,**{"initial_mwh":0,**kw}}

def generator(**kw):
    return {"id":"g","kind":"generator","discrete":True,"power_mw":2,
            "minimum_output_mw":2,"startup_cost_eur":10,"variable_cost_eur_mwh":200,**kw}

def workload(**kw):
    return {"id":"w","kind":"workload","power_mw":2,"shift_budget_mwh":4,
            "max_delay_hours":3,"recovery_power_mw":2,**kw}

class Causal(unittest.TestCase):
    def test_no_anticipation_and_notice_value(self):
        surprise=site(events=[event()],resources=[battery()])
        announced=deepcopy(surprise);announced["events"][0]["notice_minutes"]=120
        a=replay(surprise,6);b=replay(announced,6)
        self.assertTrue(evaluate(surprise)["feasible"],"Perfect foresight can precharge")
        self.assertFalse(a["feasible"]);self.assertAlmostEqual(a["uncovered_mwh"],4,places=5)
        self.assertTrue(b["feasible"])
        self.assertEqual(a["observations"][0]["announced_events"],[])
        self.assertEqual(len(b["observations"][0]["announced_events"]),1)
        self.assertAlmostEqual(a["schedule"]["resources"]["b"]["soc_mwh"][1],0,places=5)
        self.assertAlmostEqual(b["schedule"]["resources"]["b"]["soc_mwh"][1],4,places=5)

    def test_future_observations_do_not_change_prefix(self):
        a=site(events=[event(4,6,0)],resources=[battery()])
        b=deepcopy(a)
        b["baseline_mw"][3:]=[11]*5
        b["price_eur_mwh"]=[100]*3+[1]*5
        b["normal_import_cap_mw"]=[12]*3+[10]*5
        b["resources"][0]["availability"]=[1]*3+[0]*5
        b["events"]=[event(5,7,0,7)]
        x=replay(a,6);y=replay(b,6)
        self.assertEqual(x["observations"][:3],y["observations"][:3])
        for key in ("grid_import_mw","import_cap_mw","uncovered_mw"):
            self.assertEqual(x["schedule"][key][:3],y["schedule"][key][:3])
        for key in ("charge_mw","discharge_mw","soc_mwh","charging_mode"):
            self.assertEqual(x["schedule"]["resources"]["b"][key][:3],y["schedule"]["resources"]["b"][key][:3])

    def test_forced_trip_and_restart_dwell(self):
        s=site(normal_import_cap_mw=10,events=[event(1,6,0)],resources=[
            generator(minimum_up_hours=3,minimum_down_hours=2,availability=[1,1,0,1,1,1,1,1])])
        r=replay(s,5)
        self.assertEqual(r["status"],"solved")
        g=r["schedule"]["resources"]["g"]
        self.assertEqual([round(x) for x in g["online"][1:6]],[1,0,0,1,1])
        self.assertEqual([x["interval"] for x in r["forced_trips"]],[2])
        self.assertAlmostEqual(r["uncovered_mwh"],4,places=5)
        self.assertAlmostEqual(g["startup"][4],1,places=5)
        self.assertFalse(r["feasible"])

    def test_fuel_carries_across_windows(self):
        r=replay(site(events=[event(1,5)],resources=[generator(fuel_budget_mwh=4)]),3)
        self.assertEqual(r["status"],"solved")
        self.assertAlmostEqual(sum(r["schedule"]["resources"]["g"]["generation_mw"]),4,places=5)
        self.assertAlmostEqual(r["terminal_state"]["g"]["fuel"],0,places=5)

    def test_dwell_carries_across_short_windows(self):
        r=replay(site(events=[event(1,2)],resources=[generator(minimum_up_hours=3)]),1)
        self.assertEqual(r["status"],"solved")
        g=r["schedule"]["resources"]["g"]["online"]
        self.assertEqual([round(x) for x in g[1:5]],[1,1,1,0])

    def test_workload_energy_and_deadline_carry(self):
        r=replay(site(events=[event(1,3,60)],resources=[workload()]),5)
        self.assertTrue(r["feasible"])
        w=r["schedule"]["resources"]["w"]
        self.assertAlmostEqual(sum(w["shift_mw"]),4,places=5)
        self.assertAlmostEqual(sum(w["recovery_mw"]),4,places=5)
        self.assertAlmostEqual(w["backlog_mwh"][2],4,places=5)
        self.assertAlmostEqual(w["backlog_mwh"][4],0,places=5)
        for t in range(8):
            self.assertGreaterEqual(sum(w["recovery_mw"][:t+1])+1e-5,sum(w["shift_mw"][:max(0,t-3+1)]))

    def test_unexpected_recovery_outage_not_silently_reset(self):
        r=replay(site(events=[event(1,3,60)],resources=[workload(availability=[1,1,1,0,0,0,0,0])]),5)
        self.assertFalse(r["feasible"])
        self.assertEqual(r["status"],"solved")
        self.assertEqual(r["executed_intervals"],8)
        self.assertAlmostEqual(r["terminal_backlog_mwh"]["w"],4,places=5)
        self.assertAlmostEqual(r["missed_deadline_mwh"],4,places=5)
        self.assertEqual([x["interval"] for x in r["missed_deadlines"]],[4,5])
        self.assertEqual([x["interval"] for x in r["fallbacks"]],list(range(3,8)))

    def test_fallback_late_recovery_and_prefix_invariance(self):
        a=site(events=[event(1,3,60)],resources=[workload(availability=[1,1,1,0,0,1,1,1])])
        b=deepcopy(a);b["resources"][0]["availability"][5:]=[0,0,0]
        r=replay(a,5);other=replay(b,5)
        self.assertEqual(r["status"],"solved")
        self.assertFalse(r["feasible"])
        self.assertAlmostEqual(r["missed_deadline_mwh"],4,places=5)
        self.assertAlmostEqual(r["terminal_backlog_mwh"]["w"],0,places=5)
        w=r["schedule"]["resources"]["w"]
        self.assertAlmostEqual(sum(w["shift_mw"]),sum(w["recovery_mw"]),places=5)
        for key in ("shift_mw","recovery_mw","backlog_mwh"):
            self.assertEqual(w[key][:5],other["schedule"]["resources"]["w"][key][:5])
        self.assertEqual(r["missed_deadlines"][:1],other["missed_deadlines"][:1])

    def test_fallback_does_not_retry_timeout(self):
        with patch("gridpass_flexibility.causal.evaluate",return_value={"status":"solver_failed","solver_status":1,"message":"timeout"}) as solve:
            r=replay(site(resources=[workload()]))
        self.assertEqual(solve.call_count,1)
        self.assertEqual(r["status"],"replay_failed")
        self.assertEqual(r["fallbacks"],[])

    def test_fallback_preserves_hard_thermal_constraint(self):
        # The real infeasible forecast and fallback must not
        # invent cooling capacity or relax the physical bound.
        thermal={"id":"c","kind":"thermal_cooling","power_mw":0,
            "initial_temp_c":24,"min_temp_c":18,"max_temp_c":24,
            "thermal_capacitance_mwh_per_k":1,"thermal_conductance_mw_per_k":0,
            "ambient_c":30,"heat_gain_mw":1,"cop":3,"baseline_cooling_mw":0}
        r=replay(site(resources=[workload(),thermal]),2)
        self.assertEqual(r["status"],"replay_failed")
        self.assertFalse(r["feasible"])
        self.assertEqual(r["executed_intervals"],0)
        self.assertEqual(r["fallbacks"][0]["status"],"solver_failed")

    def test_terminal_storage_shortfall(self):
        r=replay(site(4,events=[event(2,4,0)],resources=[battery(initial_mwh=4)]),4)
        self.assertEqual(r["status"],"solved")
        self.assertAlmostEqual(r["uncovered_mwh"],0,places=5)
        self.assertAlmostEqual(r["terminal_recovery_shortfall_mwh"]["b"],4,places=5)
        self.assertFalse(r["feasible"])

    def test_sampled_notice_rounds_down(self):
        r=replay(site(events=[event(2,3,30)],resources=[generator(response_minutes=30)]),4)
        self.assertEqual(r["observations"][1]["announced_events"],[])
        self.assertEqual(r["observations"][2]["announced_events"][0]["notice_minutes"],0)
        self.assertAlmostEqual(r["uncovered_mwh"],2,places=5)

    def test_soc_balance_and_exact_modes(self):
        b=battery(initial_mwh=4)
        r=replay(site(events=[event(1,3)],resources=[b]),4)
        self.assertTrue(r["feasible"])
        w=r["schedule"]["resources"]["b"];soc=4
        for c,d,e in zip(w["charge_mw"],w["discharge_mw"],w["soc_mwh"]):
            self.assertLess(min(c,d),1e-5)
            soc+=c-d;self.assertAlmostEqual(soc,e,places=5)

    def test_already_running_generator_not_forced_off_by_notice(self):
        r=replay(site(events=[event(0,1)],resources=[generator(initial_mw=2,initial_on=True,
            initial_state_hours=0,minimum_up_hours=2,response_minutes=120)]),3)
        self.assertEqual(r["status"],"solved")
        self.assertAlmostEqual(r["schedule"]["resources"]["g"]["generation_mw"][0],2,places=5)
        self.assertEqual(r["forced_trips"],[])

    def test_timeout_returns_partial_failure(self):
        with patch("gridpass_flexibility.causal.monotonic",side_effect=[0,61]):
            r=replay(site(),time_limit_s=60)
        self.assertEqual(r["status"],"replay_failed")
        self.assertFalse(r["feasible"])
        self.assertEqual(r["executed_intervals"],0)
        self.assertIn("time budget",r["failure"]["message"])

    def test_bounds(self):
        with self.assertRaises(ValueError):replay(site(673))
        with self.assertRaises(ValueError):replay(site(),97)
