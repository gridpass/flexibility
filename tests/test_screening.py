import unittest
from gridpass_flexibility import assess, FIELDS

BASE = {k:v for k, (_,v) in FIELDS.items()}

class ScreeningTests(unittest.TestCase):
    def test_example(self):
        a=assess(BASE)
        self.assertTrue(a["feasible"])
        self.assertEqual(a["required"],5)
        self.assertEqual(a["importMW"],15)
        self.assertEqual(a["annualHours"],200)
        self.assertEqual(next(r for r in a["dispatch"] if r["name"]=="Battery discharge")["power"],2)
    def test_notice(self):
        self.assertEqual(assess({**BASE,"notice":0})["remaining"],3)
    def test_duration(self):
        self.assertEqual(assess({**BASE,"duration":8})["remaining"],2)
    def test_recovery(self):
        self.assertEqual(assess({**BASE,"recovery":0})["remaining"],1.5)
        self.assertTrue(assess({**BASE,"events":1,"recovery":0})["feasible"])
    def test_no_flex_needed(self):
        self.assertEqual(assess({**BASE,"limit":21})["annualCost"],0)
    def test_no_assets(self):
        r=assess({**BASE,"flex":0,"gen":0,"battery":0,"energy":0})
        self.assertFalse(r["feasible"])
        self.assertEqual(r["remaining"],5)
    def test_invalid(self):
        for update in [{"events":10000},{"duration":0},{"events":1.5},{"efficiency":0},{"load":True},{"load":float("nan")}]:
            with self.subTest(update=update):
                self.assertFalse(assess({**BASE,**update})["valid"])
    def test_conservation(self):
        r=assess(BASE)
        self.assertAlmostEqual(sum(x["power"] for x in r["dispatch"])+r["remaining"],r["required"])
        self.assertAlmostEqual(r["annualCost"],BASE["events"]*sum(x["eventCost"] for x in r["dispatch"]))
