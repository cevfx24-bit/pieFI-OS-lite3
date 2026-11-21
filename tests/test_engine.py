import os,tempfile,sys,unittest
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','files','usr','lib','piefi'))
import engine
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.mkdtemp();engine.DB=os.path.join(self.tmp,'db.sqlite')
 def test_credit_duplicate_and_session(self):
  self.assertFalse(engine.add_credit('AA:BB',2,'evt1')['duplicate'])
  self.assertTrue(engine.add_credit('AA:BB',2,'evt1')['duplicate'])
  s=engine.create_session('AA:BB',60);self.assertEqual(s['seconds'],120)
  rows=engine.status();self.assertEqual(rows[0]['state'],'active')
 def test_pause_resume(self):
  engine.add_credit('CC:DD',1,'evt2');s=engine.create_session('CC:DD',30)
  left=engine.pause(s['id']);self.assertGreater(left,0)
  e=engine.resume(s['id']);self.assertGreater(e,0)
if __name__=='__main__':unittest.main()
