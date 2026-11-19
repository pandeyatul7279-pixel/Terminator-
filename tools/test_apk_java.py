#!/usr/bin/env python3
"""Compile and execute tests against the exact APK Java archive extractor.
Requires hash-pinned tools prepared by tools/build_apk.py, not an Android device.
"""
from pathlib import Path
import io
import os
import subprocess
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'.cache/apk-toolchain'
JAVA=D/'jdk-wheel/jdk4py/java-runtime/bin/java'
CLASSES=ROOT/'.cache/apk-java-tests/classes'

def compile_tests():
    CLASSES.mkdir(parents=True,exist_ok=True)
    sources=[ROOT/'android/app/src/main/java/dev/terminator/phone/SafeTar.java',ROOT/'tests/java/SafeTarHarness.java']+list((ROOT/'.cache/apk-runtime/xz-java/src').rglob('*.java'))
    listing=CLASSES.parent/'sources.txt';listing.write_text('\n'.join(str(p) for p in sources)+'\n')
    subprocess.run([str(JAVA),'-jar',str(D/'ecj.jar'),'-8','-nowarn','-proc:none','-bootclasspath',str(D/'android.jar'),'-d',str(CLASSES),'@'+str(listing)],check=True,cwd=ROOT)

class ActualJavaExtractorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'.cache/apk-java-tests');self.base=Path(self.temp.name);self.dest=self.base/'root';self.archive=self.base/'fixture.tar'
    def tearDown(self):self.temp.cleanup()
    def tar(self,rows):
        with tarfile.open(self.archive,'w',format=tarfile.PAX_FORMAT) as t:
            for name,data,kind in rows:
                m=tarfile.TarInfo(name)
                if kind in ('symlink','hardlink'):
                    m.type=tarfile.SYMTYPE if kind=='symlink' else tarfile.LNKTYPE;m.linkname=data;t.addfile(m)
                else:
                    b=data.encode();m.size=len(b);m.mode=int(kind,8) if kind else 0o644;t.addfile(m,io.BytesIO(b))
    def execute(self,success=True):
        p=subprocess.run([str(JAVA),'-cp',str(CLASSES),'SafeTarHarness',str(self.archive),str(self.dest),'tar'],capture_output=True,text=True,timeout=10)
        if success:self.assertEqual(p.returncode,0,p.stderr)
        else:self.assertNotEqual(p.returncode,0,p.stdout)
        return p
    def test_regular_file(self):
        self.tar([('nested/file','safe','')]);self.execute();self.assertEqual((self.dest/'nested/file').read_text(),'safe')
    def test_executable_mode(self):
        self.tar([('script','safe','755')]);self.execute();self.assertTrue(os.access(self.dest/'script',os.X_OK));self.assertEqual((self.dest/'script').stat().st_mode&0o777,0o700)
    def test_setuid_is_never_preserved(self):
        self.tar([('script','safe','4755')]);self.execute();self.assertEqual((self.dest/'script').stat().st_mode&0o7000,0)
    def test_path_traversal(self):
        self.tar([('../outside','bad','')]);self.execute(False);self.assertFalse((self.base/'outside').exists())
    def test_absolute_file_path(self):
        self.tar([('/outside','bad','')]);self.execute(False)
    def test_backslash_is_a_literal_posix_filename(self):
        self.tar([('a\\b','safe','')]);self.execute();self.assertEqual((self.dest/'a\\b').read_text(),'safe');self.assertFalse((self.dest/'a/b').exists())
    def test_debian_multiarch_colon_is_preserved(self):
        self.tar([('var/lib/dpkg/libc6:arm64.list','safe','')]);self.execute();self.assertEqual((self.dest/'var/lib/dpkg/libc6:arm64.list').read_text(),'safe')
    def test_duplicate_files(self):
        self.tar([('same','a',''),('same','b','')]);self.execute(False)
    def test_symlink_escape(self):
        self.tar([('escape','../outside','symlink')]);self.execute(False);self.assertFalse((self.dest/'escape').exists())
    def test_symlink_write_parent(self):
        self.tar([('parent','inside','symlink'),('parent/file','bad','')]);self.execute(False);self.assertFalse((self.dest/'inside/file').exists())
    def test_absolute_guest_link_is_relocated(self):
        self.tar([('usr/file','safe',''),('link','/usr/file','symlink')]);self.execute();self.assertFalse(os.path.isabs(os.readlink(self.dest/'link')));self.assertEqual((self.dest/'link').read_text(),'safe')
    def test_hard_link(self):
        self.tar([('file','safe',''),('second','file','hardlink')]);self.execute();self.assertEqual((self.dest/'file').stat().st_ino,(self.dest/'second').stat().st_ino)
    def test_hard_link_escape(self):
        self.tar([('escape','../outside','hardlink')]);self.execute(False)
    def test_hard_link_requires_regular_target(self):
        self.tar([('file','safe',''),('link','file','symlink'),('second','link','hardlink')]);self.execute(False)
    def test_checksum_tamper(self):
        self.tar([('file','safe','')]);b=bytearray(self.archive.read_bytes());b[0]^=1;self.archive.write_bytes(b);self.execute(False)
    def test_truncated_header(self):
        self.archive.write_bytes(b'bad');self.execute(False)
    def test_truncated_payload(self):
        self.tar([('file','safe','')]);self.archive.write_bytes(self.archive.read_bytes()[:514]);self.execute(False)
    def test_fresh_directory_required(self):
        self.tar([('file','safe','')]);self.dest.mkdir();(self.dest/'existing').write_text('keep');self.execute(False);self.assertEqual((self.dest/'existing').read_text(),'keep')
    def test_pax_long_name(self):
        name='a'*120+'/file';self.tar([(name,'safe','')]);self.execute();self.assertEqual((self.dest/name).read_text(),'safe')

if __name__=='__main__':
    os.environ.update(LANG='C.UTF-8',LC_ALL='C.UTF-8')
    compile_tests();unittest.main()
