import importlib.util,os,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location('mirror',ROOT/'scripts/mirror_personal_main.py')
mirror=importlib.util.module_from_spec(spec);spec.loader.exec_module(mirror)
class Policy(unittest.TestCase):
    def test_forward(self):self.assertEqual(mirror.decision(mirror.PERSONAL,'new','new','old',True),'FAST_FORWARD')
    def test_equal(self):self.assertEqual(mirror.decision(mirror.PERSONAL,'new','new','new',True),'ALREADY_CURRENT')
    def test_divergence(self):self.assertEqual(mirror.decision(mirror.PERSONAL,'new','new','other',False),'HOLD_UNINTEGRATED_ORGANIZATION_COMMITS')
    def test_organization_cannot_publish(self):self.assertEqual(mirror.decision(mirror.ORGANIZATION,'new','new','old',True),'SKIP_NON_AUTHORITY')
    def test_stale(self):self.assertEqual(mirror.decision(mirror.PERSONAL,'old','new','older',True),'SKIP_STALE_RUN')
    def test_org_execution_has_no_network_or_write(self):
        env=dict(os.environ,GITHUB_REPOSITORY=mirror.ORGANIZATION)
        p=subprocess.run([sys.executable,str(ROOT/'scripts/mirror_personal_main.py'),'--execute'],env=env,capture_output=True,text=True)
        self.assertEqual(p.returncode,0);self.assertIn('SKIP_NON_AUTHORITY',p.stdout)
    def test_producer_personal_only(self):
        text=(ROOT/'.github/workflows/sync-and-upload.yml').read_text(encoding='utf-8')
        self.assertIn("if: github.repository == 'HiiragiNemu/magireco-cn-patch'",text)
        self.assertNotIn('MagirecoCN-Revival-Project',text)
        self.assertNotIn('gh repo sync',text)
        self.assertNotIn('git reset --hard',text)
        self.assertIn('LAST_SYNC_COMMIT_SHA',text)
        self.assertIn('个人仓库游戏更新发布',text)
    def test_mirror_no_reverse_or_force(self):
        text=(ROOT/'scripts/mirror_personal_main.py').read_text(encoding='utf-8')
        self.assertNotIn('--force',text)
        self.assertIn("auth+['push',url,'HEAD:refs/heads/main']",text)
        workflow=(ROOT/'.github/workflows/sync-personal-to-organization.yml').read_text(encoding='utf-8')
        self.assertIn("github.repository == 'HiiragiNemu/magireco-cn-patch'",workflow)
        self.assertNotIn('schedule:',workflow)
        self.assertIn('persist-credentials: false',workflow)
if __name__=='__main__':unittest.main(verbosity=2)
