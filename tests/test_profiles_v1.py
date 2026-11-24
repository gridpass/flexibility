import copy
import unittest
from gridpass_flexibility.profiles import profile_schema, validate_profile, evaluate_profile
from gridpass_flexibility.stress import build_stress_suite, test_commitment as run_commitment
from gridpass_flexibility.dispatch import _digest

def profile(**kw):
    return {"id":"independent","version":"1","reduction_mw":2,"notice_minutes":60,
            "activation_hours":4,"annual_event_hours":8,**kw}

def site(**kw):
    return {"interval_hours":1,"baseline_mw":[10]*8760,"normal_import_cap_mw":12,
            "price_eur_mwh":100,"resources":[{"id":"g","kind":"generator","power_mw":2}],
            "events":[{"start":1,"end":5,"notice_minutes":60,"cap_mw":8},
                      {"start":9,"end":13,"notice_minutes":60,"cap_mw":8}],**kw}

class ProfileConformance(unittest.TestCase):
    def test_schema_and_package_data(self):
        from jsonschema import Draft202012Validator
        Draft202012Validator.check_schema(profile_schema())
        self.assertEqual(validate_profile(profile())["schema_version"],"gridpass-profile-v1")
    def test_invalid_profiles(self):
        for update in [{"schema_version":"v2"},{"reduciton_mw":2},{"id":""},{"version":""},
                       {"reduction_mw":0},{"notice_minutes":float("nan")},{"reduction_mw":True},
                       {"minimum_recovery_hours":-1},{"maximum_interval_minutes":0},{"annual_event_hours":3}]:
            with self.subTest(update=update),self.assertRaises(ValueError):
                validate_profile(profile(**update))
    def test_recovery_coverage(self):
        r=evaluate_profile(profile(minimum_recovery_hours=2),[site()])
        self.assertEqual(r["result"],"incomplete_coverage")
        self.assertEqual(r["cases"][0]["shortest_qualifying_recovery_hours"],4)
        self.assertFalse(r["coverage"]["minimum_recovery"])
        r=evaluate_profile(profile(minimum_recovery_hours=4),[site()])
        self.assertEqual(r["result"],"modeled_cases_pass")
    def test_disjoint_coverage_not_a_pass(self):
        events=[{"start":i,"end":i+2,"notice_minutes":60,"cap_mw":8} for i in (1,5,9,13)]
        annual=site(events=events)
        short=site(baseline_mw=[10]*8,events=[{"start":1,"end":5,"notice_minutes":60,"cap_mw":8}])
        r=evaluate_profile(profile(),[annual,short])
        self.assertTrue(r["coverage"]["notice_and_duration"])
        self.assertTrue(r["coverage"]["annual_usage"])
        self.assertFalse(r["coverage"]["single_complete_annual_case"])
        self.assertEqual(r["result"],"incomplete_coverage")
    def test_resolution_not_covered(self):
        r=evaluate_profile(profile(maximum_interval_minutes=15),[site()])
        self.assertFalse(r["cases"][0]["resolution_covered"])
        self.assertEqual(r["result"],"incomplete_coverage")
        with self.assertRaises(ValueError):build_stress_suite(site(),profile(maximum_interval_minutes=15))
    def test_recovery_alignment(self):
        with self.assertRaises(ValueError):build_stress_suite(site(),profile(minimum_recovery_hours=.5))
    def test_stress_evidence_digest(self):
        # Small daily-resolution case to exercise suite evidence, not a fast response test.
        s=site(interval_hours=24,baseline_mw=[10]*365,events=[])
        p=profile(activation_hours=24,annual_event_hours=48,minimum_recovery_hours=24)
        r=run_commitment(s,p)
        self.assertEqual(r["result"],"modeled_cases_pass")
        evidence=r["evidence"].pop("result_sha256")
        self.assertEqual(evidence,_digest(r))
    def test_full_year_quarter_hour(self):
        s=site(interval_hours=.25,baseline_mw=[10]*35040,events=[
            {"start":4,"end":20,"notice_minutes":60,"cap_mw":8},
            {"start":24,"end":40,"notice_minutes":60,"cap_mw":8}])
        r=evaluate_profile(profile(minimum_recovery_hours=1,maximum_interval_minutes=15),[s])
        self.assertEqual(r["result"],"modeled_cases_pass")
        self.assertLessEqual(r["cases"][0]["uncovered_mwh"],1e-5)
