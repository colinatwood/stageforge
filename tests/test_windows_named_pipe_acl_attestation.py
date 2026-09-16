import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from windows_named_pipe import WindowsPipePolicy,expected_windows_pipe_sids,validate_windows_pipe_acl_facts

class WindowsNamedPipeAclAttestationTests(unittest.TestCase):
    def setUp(self):
        self.sid='S-1-5-21-1-2-3-1001'
        self.policy=WindowsPipePolicy((self.sid,))
        self.good={
            'daclProtected':True,'nullDacl':False,'unsupportedAceCount':0,
            'allowedSids':['S-1-5-18',self.sid],
            'accessMasks':{'S-1-5-18':0x10000000,self.sid:0x10000000},
        }
    def test_exact_kernel_facts_are_accepted(self):
        accepted=validate_windows_pipe_acl_facts(self.policy,self.good)
        self.assertEqual(set(accepted['allowedSids']),set(expected_windows_pipe_sids((self.sid,))))
    def test_unprotected_or_null_dacl_is_rejected(self):
        for key,value in [('daclProtected',False),('nullDacl',True)]:
            facts=dict(self.good);facts[key]=value
            with self.subTest(key=key),self.assertRaises(PermissionError):
                validate_windows_pipe_acl_facts(self.policy,facts)
    def test_extra_broad_principal_is_rejected(self):
        facts={**self.good,'allowedSids':[ *self.good['allowedSids'],'S-1-1-0'],
               'accessMasks':{**self.good['accessMasks'],'S-1-1-0':0x10000000}}
        with self.assertRaises(PermissionError):validate_windows_pipe_acl_facts(self.policy,facts)
    def test_missing_configured_principal_is_rejected(self):
        facts={**self.good,'allowedSids':['S-1-5-18'],'accessMasks':{'S-1-5-18':0x10000000}}
        with self.assertRaises(PermissionError):validate_windows_pipe_acl_facts(self.policy,facts)
    def test_deny_or_unknown_ace_is_rejected(self):
        facts={**self.good,'unsupportedAceCount':1}
        with self.assertRaises(PermissionError):validate_windows_pipe_acl_facts(self.policy,facts)
    def test_access_mask_must_be_exact_generic_all(self):
        facts={**self.good,'accessMasks':{**self.good['accessMasks'],self.sid:0x80000000}}
        with self.assertRaises(PermissionError):validate_windows_pipe_acl_facts(self.policy,facts)
    def test_administrator_presence_tracks_explicit_policy(self):
        policy=WindowsPipePolicy((self.sid,),allow_administrators=True)
        facts={**self.good,'allowedSids':['S-1-5-18','S-1-5-32-544',self.sid],
               'accessMasks':{'S-1-5-18':0x10000000,'S-1-5-32-544':0x10000000,self.sid:0x10000000}}
        validate_windows_pipe_acl_facts(policy,facts)
        with self.assertRaises(PermissionError):validate_windows_pipe_acl_facts(self.policy,facts)

if __name__=='__main__':unittest.main()
