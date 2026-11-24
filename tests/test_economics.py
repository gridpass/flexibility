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
