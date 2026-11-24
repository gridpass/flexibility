import unittest
from copy import deepcopy
from gridpass_flexibility.economics import compare_lifecycle
from gridpass_flexibility.interface import evaluate_request

def alternative(**kw):
    return {"id":"standard","scenario":{"interval_hours":24,"baseline_mw":[1]*365,
             "normal_import_cap_mw":2,"price_eur_mwh":100,"resources":[]},
            "capex_eur":100000,"delay_months":0,"annual_contribution_eur":2000000,
            "annual_fixed_opex_eur":10000,"tariff":{"grid_emissions_kg_mwh":400,
              "carbon_eur_tonne":50,"annual_peak_eur_mw":2000},**kw}

def request(*a,**kw):
    return {"years":2,"real_discount_rate":.1,"alternatives":list(a),**kw}

class EconomicsTests(unittest.TestCase):
    def test_annual_cost_and_npv(self):
        r=compare_lifecycle(request(alternative()))["cases"][0]["alternatives"][0]
        annual=r["annual"]
        self.assertTrue(r["eligible"])
        self.assertAlmostEqual(annual["grid_energy_mwh"],8760)
        self.assertAlmostEqual(annual["grid_emissions_tonnes"],3504)
        self.assertAlmostEqual(annual["carbon_cost_eur"],175200)
        self.assertAlmostEqual(annual["annual_operating_cost_eur"],876000+175200+2000)
        margin=2000000-10000-1053200
        self.assertAlmostEqual(r["finance"]["npv_eur"],-100000+margin/1.1+margin/1.21)
    def test_delay_replacement_residual(self):
        a=alternative(delay_months=6,replacements=[{"year":2,"cost_eur":1000}],residual_value_eur=500)
        f=compare_lifecycle(request(a))["cases"][0]["alternatives"][0]["finance"]
        m=2000000-10000-1053200
        self.assertAlmostEqual(f["npv_eur"],-100000+.5*m/1.1+(m-1000+500)/1.21)
        self.assertEqual(f["cashflows"][1]["service_fraction"],.5)
    def test_time_to_power_and_reference(self):
        slow=alternative(delay_months=12)
        fast=alternative(id="flexible",capex_eur=200000)
        r=compare_lifecycle(request(slow,fast))["cases"][0]
        self.assertEqual(r["recommended"],"flexible")
        self.assertAlmostEqual(r["alternatives"][1]["incremental_npv_eur"],(2000000-10000-1053200)/1.1-100000)
    def test_fuel_and_emissions(self):
        a=alternative(tariff={"grid_emissions_kg_mwh":400,"carbon_eur_tonne":50})
        a["scenario"]["resources"]=[{"id":"g","kind":"generator","power_mw":1,"variable_cost_eur_mwh":10}]
        a["fuel"]={"g":{"electrical_efficiency":.5,"fuel_eur_mwh":30,"fuel_emissions_kg_mwh":200}}
        x=compare_lifecycle(request(a))["cases"][0]["alternatives"][0]["annual"]
        self.assertAlmostEqual(x["fuel_mwh"],17520)
        self.assertAlmostEqual(x["fuel_emissions_tonnes"],3504)
        self.assertAlmostEqual(x["fuel_cost_eur"],525600)
        self.assertAlmostEqual(x["other_variable_cost_eur"],87600,places=4)
        self.assertAlmostEqual(x["annual_operating_cost_eur"],788400,places=4)
    def test_peak_tariff_changes_dispatch(self):
        a=alternative(tariff={"grid_emissions_kg_mwh":0,"annual_peak_eur_mw":100000})
        a["scenario"]["baseline_mw"]=[2]+[1]*364
        a["scenario"]["resources"]=[{"id":"g","kind":"generator","power_mw":1,"variable_cost_eur_mwh":200}]
        a["fuel"]={"g":{"electrical_efficiency":1,"fuel_eur_mwh":0,"fuel_emissions_kg_mwh":0}}
        x=compare_lifecycle(request(a))["cases"][0]["alternatives"][0]["annual"]
        self.assertAlmostEqual(x["peak_import_mw"],1)
        self.assertAlmostEqual(x["peak_tariff_cost_eur"],100000)
        self.assertAlmostEqual(x["other_variable_cost_eur"],4800,places=4)
    def test_monthly_peaks_reconcile_and_change_dispatch(self):
        a=alternative(tariff={"grid_emissions_kg_mwh":0,"monthly_peak_eur_mw":[6000,100]+[0]*10})
        a["scenario"]["baseline_mw"]=[2]+[1]*30+[2]+[1]*333
        a["scenario"]["resources"]=[{"id":"g","kind":"generator","power_mw":1,"variable_cost_eur_mwh":200}]
        a["fuel"]={"g":{"electrical_efficiency":1,"fuel_eur_mwh":0,"fuel_emissions_kg_mwh":0}}
        x=compare_lifecycle(request(a))["cases"][0]["alternatives"][0]["annual"]
        self.assertEqual(x["dispatch_status"],"solved")
        self.assertEqual(len(x["monthly_peak_tariffs"]),12)
        self.assertAlmostEqual(x["monthly_peak_tariffs"][0]["peak_import_mw"],1)
        self.assertAlmostEqual(x["monthly_peak_tariffs"][1]["peak_import_mw"],2,places=5)
        self.assertAlmostEqual(x["peak_tariff_cost_eur"],6200,places=2)
        self.assertAlmostEqual(x["other_variable_cost_eur"],4800)
        self.assertAlmostEqual(x["annual_operating_cost_eur"],878400+4800+6200,places=2)
        self.assertEqual(evaluate_request("economics",request(a)),compare_lifecycle(request(a)))

    def test_seasonal_commissioning_excludes_pre_service_months(self):
        a=alternative(delay_months=6,seasonal_commissioning=True,
                      tariff={"grid_emissions_kg_mwh":0,"monthly_peak_eur_mw":[12000]+[0]*11})
        a["scenario"]["price_eur_mwh"]=[100]*181+[200]*184
        r=compare_lifecycle(request(a))["cases"][0]["alternatives"][0]
        expected=184*24*200
        self.assertAlmostEqual(r["finance"]["cashflows"][1]["operating_cost_eur"],expected)
        self.assertAlmostEqual(r["finance"]["cashflows"][2]["operating_cost_eur"],expected+181*24*100+12000)
        self.assertAlmostEqual(sum(r["annual"]["monthly_operating_cost_eur"]),r["annual"]["annual_operating_cost_eur"])
        self.assertAlmostEqual(r["finance"]["npv_eur"],-100000+(995000-expected)/1.1+(1990000-expected-181*24*100-12000)/1.21)
        self.assertEqual(evaluate_request("economics",request(a)),compare_lifecycle(request(a)))

    def test_commissioning_cannot_borrow_pre_service_charge(self):
        a=alternative(delay_months=6,seasonal_commissioning=True,
                      tariff={"grid_emissions_kg_mwh":0,"monthly_peak_eur_mw":[0]*12})
        a["scenario"]["events"]=[{"start":181,"end":182,"cap_mw":0,"notice_minutes":1440}]
        a["scenario"]["resources"]=[{"id":"b","kind":"battery","power_mw":1,
             "energy_mwh":24,"initial_mwh":0,"terminal_mwh":0,
             "charge_efficiency":1,"discharge_efficiency":1}]
        result=compare_lifecycle(request(a))
        row=result["cases"][0]["alternatives"][0]
        self.assertTrue(row["annual"]["feasible"])
        self.assertFalse(row["commissioning"]["feasible"])
        self.assertAlmostEqual(row["commissioning"]["uncovered_mwh"],24)
        self.assertEqual(row["commissioning"]["first_service_month"],7)
        self.assertFalse(row["eligible"])
        self.assertIsNone(result["cases"][0]["recommended"])

    def test_commissioning_slice_clips_events_and_notice(self):
        from gridpass_flexibility.economics import _commissioning_slice
        s={"baseline_mw":[1,2,3,4],"interval_hours":1,
           "events":[{"start":0,"end":3,"cap_mw":1,"notice_minutes":120},
                     {"start":3,"end":4,"cap_mw":2,"notice_minutes":120}],
           "resources":[{"availability":[1,.5,0,1],"ambient_c":[10,11,12,13]}]}
        sliced=_commissioning_slice(s,2,1)
        self.assertEqual(sliced["baseline_mw"],[3,4])
        self.assertEqual(sliced["resources"][0]["availability"],[0,1])
        self.assertEqual(sliced["resources"][0]["ambient_c"],[12,13])
        self.assertEqual(sliced["events"],[
            {"start":0,"end":1,"cap_mw":1,"notice_minutes":0},
            {"start":1,"end":2,"cap_mw":2,"notice_minutes":60}])

    def test_seasonal_commissioning_reconciles_generator_cost(self):
        a=alternative(delay_months=12,seasonal_commissioning=True,
                      tariff={"grid_emissions_kg_mwh":0,"carbon_eur_tonne":50,"monthly_peak_eur_mw":[0]*12})
        a["scenario"]["resources"]=[{"id":"g","kind":"generator","power_mw":1,"variable_cost_eur_mwh":10}]
        a["fuel"]={"g":{"electrical_efficiency":.5,"fuel_eur_mwh":20,"fuel_emissions_kg_mwh":100}}
        r=compare_lifecycle(request(a))["cases"][0]["alternatives"][0]
        self.assertEqual(r["finance"]["cashflows"][1]["operating_cost_eur"],0)
        self.assertAlmostEqual(r["finance"]["cashflows"][2]["operating_cost_eur"],8760*60)
        self.assertAlmostEqual(r["annual"]["monthly_operating_cost_eur"][1],28*24*60)

    def test_seasonal_commissioning_rejects_ambiguous_inputs(self):
        for a in (alternative(seasonal_commissioning=True),
                  alternative(seasonal_commissioning=True,delay_months=1.5,tariff={"grid_emissions_kg_mwh":0,"monthly_peak_eur_mw":[0]*12}),
                  alternative(seasonal_commissioning="yes")):
            with self.assertRaisesRegex(ValueError,"[Ss]easonal"):
                compare_lifecycle(request(a))

    def test_monthly_tariff_rejects_invalid_rates_and_double_billing(self):
        for rates in ([1]*11,[1]*11+[-1],[1]*11+[True],1):
            a=alternative(tariff={"grid_emissions_kg_mwh":0,"monthly_peak_eur_mw":rates})
            with self.subTest(rates=rates),self.assertRaises(ValueError):
                compare_lifecycle(request(a))
        a=alternative()
        a["tariff"]["monthly_peak_eur_mw"]=[1]*12
        with self.assertRaisesRegex(ValueError,"not both"):
            compare_lifecycle(request(a))

    def test_monthly_tariff_rejects_samples_crossing_boundaries(self):
        a=alternative(tariff={"grid_emissions_kg_mwh":0,"monthly_peak_eur_mw":[1]*12})
        a["scenario"].update(interval_hours=20,baseline_mw=[1]*438)
        with self.assertRaisesRegex(ValueError,"month boundaries"):
            compare_lifecycle(request(a))

    def test_sensitivity_reoptimizes_fuel(self):
        a=alternative(tariff={"grid_emissions_kg_mwh":0})
        a["scenario"]["resources"]=[{"id":"g","kind":"generator","power_mw":1}]
        a["fuel"]={"g":{"electrical_efficiency":.5,"fuel_eur_mwh":30,"fuel_emissions_kg_mwh":200}}
        r=compare_lifecycle(request(a,sensitivities=[{"id":"expensive_fuel","fuel_multiplier":2}]))
        self.assertAlmostEqual(r["cases"][0]["alternatives"][0]["annual"]["fuel_mwh"],17520)
        self.assertAlmostEqual(r["cases"][1]["alternatives"][0]["annual"]["fuel_mwh"],0)
    def test_infeasible_not_ranked(self):
        a=alternative(id="cheap",capex_eur=0)
        a["scenario"]["normal_import_cap_mw"]=.5
        r=compare_lifecycle(request(a,alternative()))["cases"][0]
        self.assertEqual(r["recommended"],"standard")
        self.assertFalse(r["alternatives"][0]["eligible"])
        self.assertIsNone(r["alternatives"][1]["incremental_npv_eur"])
    def test_delayed_beyond_horizon_not_ranked(self):
        r=compare_lifecycle(request(alternative(delay_months=25)))["cases"][0]
        self.assertIsNone(r["recommended"])
    def test_short_year_and_missing_emissions_rejected(self):
        a=alternative();a["scenario"]["baseline_mw"]=[1]*10
        with self.assertRaisesRegex(ValueError,"8760"):compare_lifecycle(request(a))
        a=alternative(tariff={})
        with self.assertRaisesRegex(ValueError,"grid_emissions"):compare_lifecycle(request(a))
    def test_missing_generator_fuel_rejected(self):
        a=alternative();a["scenario"]["resources"]=[{"id":"g","kind":"generator","power_mw":1}]
        with self.assertRaisesRegex(ValueError,"fuel assumptions"):compare_lifecycle(request(a))
    def test_invalid_inputs(self):
        for kw in ({"years":0},{"real_discount_rate":True},{"reference_id":"bad"},{"sensitivities":[{"id":"base"}]}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):compare_lifecycle({**request(alternative()),**kw})
    def test_shared_interface_and_hash(self):
        p=request(alternative())
        self.assertEqual(evaluate_request("economics",p),compare_lifecycle(p))


    def test_failed_comparison_never_recommends_partial_winner(self):
        from unittest.mock import patch
        from gridpass_flexibility.economics import _annual
        first=alternative(id="a")
        second=alternative(id="b")
        def partial(a, modifiers, deadline):
            if a["id"]=="b":
                return {"dispatch_status":"solver_failed","feasible":False,"message":"timeout"}
            return _annual(a,modifiers,deadline)
        with patch("gridpass_flexibility.economics._annual",side_effect=partial):
            result=compare_lifecycle(request(first,second))
        self.assertEqual(result["status"],"evaluation_error")
        self.assertFalse(result["cases"][0]["comparison_complete"])
        self.assertIsNone(result["cases"][0]["recommended"])

    @unittest.skipUnless(__import__("importlib").util.find_spec("mcp"),"Install agent extra")
    def test_agent_time_limit(self):
        from gridpass_flexibility.mcp_server import _check_budget
        with self.assertRaisesRegex(ValueError,"60 seconds"):
            _check_budget("economics",request(alternative(),time_limit_s=61))

    def test_repeated_year_cannot_reuse_depleted_initial_battery(self):
        a=alternative(tariff={"grid_emissions_kg_mwh":0})
        a["scenario"]["events"]=[{"start":364,"end":365,"cap_mw":0,"notice_minutes":1440}]
        a["scenario"]["resources"]=[{"id":"b","kind":"battery","power_mw":1,
            "energy_mwh":24,"initial_mwh":24,"terminal_mwh":0,
            "charge_efficiency":1,"discharge_efficiency":1}]
        case=compare_lifecycle(request(a))["cases"][0]
        row=case["alternatives"][0]
        self.assertTrue(row["annual"]["feasible"])
        self.assertFalse(row["annual"]["repeat_boundary"]["pass"])
        self.assertTrue(row["boundary_validation"]["annual_required"])
        self.assertFalse(row["eligible"])
        self.assertIsNone(case["recommended"])
        self.assertFalse(case["comparison_complete"])
        other=compare_lifecycle(request(a,alternative(id="other")))["cases"][0]
        self.assertIsNone(other["recommended"])
        self.assertTrue(compare_lifecycle(request(a,years=1))["cases"][0]["alternatives"][0]["eligible"])

    def test_commissioning_to_full_year_checks_terminal_state(self):
        a=alternative(delay_months=6,seasonal_commissioning=True,
            tariff={"grid_emissions_kg_mwh":0,"monthly_peak_eur_mw":[0]*12})
        a["scenario"]["events"]=[{"start":364,"end":365,"cap_mw":0,"notice_minutes":1440}]
        a["scenario"]["resources"]=[{"id":"b","kind":"battery","power_mw":1,
            "energy_mwh":24,"initial_mwh":24,"terminal_mwh":0,
            "charge_efficiency":1,"discharge_efficiency":1}]
        row=compare_lifecycle(request(a))["cases"][0]["alternatives"][0]
        self.assertTrue(row["commissioning"]["feasible"])
        self.assertTrue(row["boundary_validation"]["commissioning_required"])
        self.assertFalse(row["boundary_validation"]["annual_required"])
        self.assertFalse(row["eligible"])

    def test_boundary_checks_generator_dwell_thermal_and_backlog(self):
        from gridpass_flexibility.economics import _repeat_boundary
        scenario={"interval_hours":1,"resources":[
            {"id":"g","kind":"generator","initial_mw":1,"initial_on":True,
             "initial_state_hours":3,"minimum_up_hours":3},
            {"id":"t","kind":"thermal_cooling","initial_temp_c":20},
            {"id":"w","kind":"workload"}]}
        schedule={"resources":{"g":{"generation_mw":[0,1],"online":[0,1]},
            "t":{"temperature_c":[20,21]},"w":{"backlog_mwh":[0,1]}}}
        r=_repeat_boundary(scenario,schedule)
        self.assertEqual([c["state"] for c in r["checks"] if not c["pass"]],
            ["dwell_intervals_remaining","temperature_c","backlog_mwh"])
        schedule["resources"]={"g":{"generation_mw":[1,1],"online":[1,1]},
            "t":{"temperature_c":[20,20]},"w":{"backlog_mwh":[0,0]}}
        self.assertTrue(_repeat_boundary(scenario,schedule)["pass"])

    def test_repeatable_storage_schedule_passes_boundary(self):
        a=alternative(tariff={"grid_emissions_kg_mwh":0})
        a["scenario"]["events"]=[{"start":100,"end":101,"cap_mw":0,"notice_minutes":1440}]
        a["scenario"]["resources"]=[{"id":"b","kind":"battery","power_mw":1,
            "energy_mwh":24,"initial_mwh":24,"terminal_mwh":24,
            "charge_efficiency":1,"discharge_efficiency":1}]
        case=compare_lifecycle(request(a))["cases"][0]
        self.assertTrue(case["alternatives"][0]["boundary_validation"]["pass"])
        self.assertEqual(case["recommended"],"standard")

    def test_interyear_redispatch_pays_to_recharge(self):
        a=alternative(interyear_reoptimization=True,tariff={"grid_emissions_kg_mwh":0})
        a["scenario"]["events"]=[{"start":364,"end":365,"cap_mw":0,"notice_minutes":1440}]
        a["scenario"]["resources"]=[{"id":"b","kind":"battery","power_mw":1,
            "energy_mwh":24,"initial_mwh":24,"terminal_mwh":0,
            "charge_efficiency":1,"discharge_efficiency":1}]
        case=compare_lifecycle(request(a))["cases"][0]
        row=case["alternatives"][0]
        self.assertEqual(case["recommended"],"standard")
        first,second=row["operating_years"]
        self.assertEqual(first["next_initial_state"]["b"]["initial_mwh"],0)
        self.assertEqual(second["carried_initial_state"],first["next_initial_state"])
        self.assertAlmostEqual(second["annual_operating_cost_eur"]-first["annual_operating_cost_eur"],2400)
        self.assertAlmostEqual(row["finance"]["cashflows"][2]["operating_cost_eur"],second["annual_operating_cost_eur"])
        a["scenario"]["normal_import_cap_mw"]=1
        row=compare_lifecycle(request(a))["cases"][0]["alternatives"][0]
        self.assertFalse(row["eligible"])
        self.assertAlmostEqual(row["operating_years"][1]["uncovered_mwh"],24)

    def test_interyear_commissioning_carries_actual_state(self):
        a=alternative(delay_months=6,seasonal_commissioning=True,interyear_reoptimization=True,
            tariff={"grid_emissions_kg_mwh":0,"monthly_peak_eur_mw":[0]*12})
        a["scenario"]["events"]=[{"start":364,"end":365,"cap_mw":0,"notice_minutes":1440}]
        a["scenario"]["resources"]=[{"id":"b","kind":"battery","power_mw":1,
            "energy_mwh":24,"initial_mwh":24,"terminal_mwh":0,
            "charge_efficiency":1,"discharge_efficiency":1}]
        row=compare_lifecycle(request(a))["cases"][0]["alternatives"][0]
        first,second=row["operating_years"]
        self.assertTrue(row["eligible"])
        self.assertEqual(first["first_service_month"],7)
        self.assertEqual(second["carried_initial_state"]["b"]["initial_mwh"],0)
        self.assertAlmostEqual(first["annual_operating_cost_eur"],439200)
        self.assertAlmostEqual(second["annual_operating_cost_eur"],876000)

    def test_interyear_carry_thermal_targets_and_discrete_age(self):
        from gridpass_flexibility.economics import _carry_state
        s={"interval_hours":1,"resources":[
           {"id":"g","kind":"generator","initial_on":True,"initial_mw":1,"initial_state_hours":3},
           {"id":"t","kind":"thermal_cooling","initial_temp_c":20},
           {"id":"w","kind":"workload"}]}
        trace={"resources":{"g":{"generation_mw":[1,1],"online":[1,1]},
            "t":{"temperature_c":[20,19]},"w":{"backlog_mwh":[1,0]}}}
        state=_carry_state(s,trace)
        self.assertEqual(state["g"]["initial_state_hours"],5)
        self.assertEqual(state["t"],{"initial_temp_c":19,"terminal_max_temp_c":20})
        trace["resources"]["g"]["online"]=[1,0]
        self.assertEqual(_carry_state(s,trace)["g"]["initial_state_hours"],1)
        trace["resources"]["w"]["backlog_mwh"][-1]=1
        with self.assertRaisesRegex(ValueError,"backlog"):
            _carry_state(s,trace)

    def test_interyear_budget_schema_and_fractional_guard(self):
        from gridpass_flexibility.budget import check_budget
        from gridpass_flexibility.interface_schema import validate_evaluation
        a=alternative(interyear_reoptimization=True)
        p=request(a)
        validate_evaluation("request","economics",p)
        validate_evaluation("response","economics",compare_lifecycle(p))
        check_budget("economics",p)
        a["delay_months"]=1
        with self.assertRaisesRegex(ValueError,"fractional"):
            compare_lifecycle(p)
        a["scenario"]["baseline_mw"]=[1]*35040
        with self.assertRaisesRegex(ValueError,"500,000"):
            check_budget("economics",request(a,years=50))

    def test_interyear_failed_solve_blocks_recommendation(self):
        from unittest.mock import patch
        from gridpass_flexibility.economics import _annual
        a=alternative(interyear_reoptimization=True)
        def solve(a,case,deadline,**kw):
            if kw:return {"dispatch_status":"solver_failed","feasible":False}
            return _annual(a,case,deadline)
        with patch("gridpass_flexibility.economics._annual",side_effect=solve):
            case=compare_lifecycle(request(a))["cases"][0]
        self.assertFalse(case["comparison_complete"])
        self.assertIsNone(case["recommended"])
