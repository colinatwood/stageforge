"""Guard the callback integration, not just the standalone overload counter."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class OverloadSafetyTests(unittest.TestCase):
    def test_callback_does_not_bypass_unclassified_effect_chain(self):
        source = (ROOT / "native/src/engine_main.cpp").read_text()
        callback = source.split("void render_audio(", 1)[1].split("template <typename T>", 1)[0]
        self.assertIn("context->effects ? &process_output_effects : nullptr", callback)
        self.assertNotIn("allow_optional()", callback)
        self.assertNotIn("note_optional_shed()", callback)
        self.assertIn("effect_delay_transaction->begin(context->delay_path",callback)
        self.assertIn("effect_delay_transaction->end(context->delay_path",callback)

    def test_runtime_declares_advisory_policy(self):
        source = (ROOT / "backend/runtime.py").read_text()
        self.assertIn('"automaticEffectSheddingEnabled":False', source)
        self.assertIn('"overloadAdvisoryOnly":True', source)

    def test_deterministic_policy_never_sheds_essential_or_unsafe_bypass(self):
        import sys
        sys.path.insert(0,str(ROOT/"backend"))
        from overload_policy import overload_shedding_plan
        effects=[{"effectId":9,"outputSlot":0,"safetyClass":"essential","bypassMode":"never","shedPriority":1000},{"effectId":3,"outputSlot":1,"safetyClass":"optional","bypassMode":"latency-preserving","shedPriority":5},{"effectId":2,"outputSlot":0,"safetyClass":"optional","bypassMode":"latency-preserving","shedPriority":10},{"effectId":4,"outputSlot":0,"safetyClass":"optional","bypassMode":"never","shedPriority":100}]
        degraded=overload_shedding_plan([{"overloadLevel":1}],effects);self.assertEqual(degraded["recommendedBypassEffectIds"],[2]);self.assertEqual(degraded["essentialEffectIds"],[9]);self.assertEqual(degraded["blockedOptionalEffectIds"],[4]);self.assertFalse(degraded["automaticApply"])
        critical=overload_shedding_plan([{"overloadLevel":2}],effects);self.assertEqual(critical["recommendedBypassEffectIds"],[2,3])
        recovered=overload_shedding_plan([{"overloadLevel":0}],effects,[2,3]);self.assertEqual(recovered["recommendedRestoreEffectIds"],[2,3]);self.assertEqual(recovered["action"],"restore")

    def test_policy_rejects_ambiguous_classification(self):
        import sys
        sys.path.insert(0,str(ROOT/"backend"))
        from overload_policy import overload_shedding_plan
        invalid=[[{"effectId":1,"outputSlot":0,"safetyClass":"optional","bypassMode":"unknown"}],[{"effectId":True,"outputSlot":0,"safetyClass":"essential","bypassMode":"never"}],[{"effectId":1,"outputSlot":4,"safetyClass":"essential","bypassMode":"never"}]]
        for effects in invalid:
            with self.subTest(effects=effects),self.assertRaises(ValueError):overload_shedding_plan([{"overloadLevel":1}],effects)
