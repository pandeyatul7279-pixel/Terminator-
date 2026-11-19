#!/usr/bin/env python3
"""Compile and execute tests against the exact APK Java archive extractor.
Requires hash-pinned tools prepared by tools/build_apk.py, not an Android device.
"""
from pathlib import Path
import hashlib
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
    sources=[ROOT/'android/app/src/main/java/dev/terminator/phone/SafeTar.java',ROOT/'android/app/src/main/java/dev/terminator/phone/VerifiedFiles.java',ROOT/'tests/java/SafeTarHarness.java',ROOT/'tests/java/VerifiedFilesHarness.java']+list((ROOT/'.cache/apk-runtime/xz-java/src').rglob('*.java'))
    listing=CLASSES.parent/'sources.txt';listing.write_text('\n'.join(str(p) for p in sources)+'\n')
    subprocess.run([str(JAVA),'-jar',str(D/'ecj.jar'),'-8','-nowarn','-proc:none','-bootclasspath',str(D/'android.jar')+':'+str(D/'core-lambda-stubs.jar'),'-d',str(CLASSES),'@'+str(listing)],check=True,cwd=ROOT)

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
    def execute(self,success=True,hardlinks=None):
        args=[str(JAVA),'-cp',str(CLASSES),'dev.terminator.phone.SafeTarHarness',str(self.archive),str(self.dest),'tar']
        if hardlinks:args.append(hardlinks)
        p=subprocess.run(args,capture_output=True,text=True,timeout=10)
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
    def test_android_hard_link_denial_copies_complete_perl_binary(self):
        self.tar([('usr/bin/perl5.38.2','exact original bytes','755'),('usr/bin/perl','usr/bin/perl5.38.2','hardlink')])
        result=self.execute(hardlinks='denied')
        source=self.dest/'usr/bin/perl5.38.2';copied=self.dest/'usr/bin/perl'
        self.assertEqual(source.read_bytes(),copied.read_bytes());self.assertFalse(copied.is_symlink())
        self.assertNotEqual(source.stat().st_ino,copied.stat().st_ino)
        self.assertEqual(copied.stat().st_mode&0o777,0o700)
        self.assertIn('copiedHardLinks=1',result.stdout)
        self.assertIn('bytes='+str(2*len(source.read_bytes())),result.stdout)
    def test_unsupported_hard_links_use_private_copy(self):
        self.tar([('file','safe','600'),('second','file','hardlink')]);self.execute(hardlinks='unsupported')
        self.assertEqual((self.dest/'second').read_text(),'safe');self.assertEqual((self.dest/'second').stat().st_mode&0o777,0o600)
    def test_hard_link_copy_never_overwrites_a_conflict(self):
        self.tar([('file','safe',''),('second','file','hardlink')]);self.execute(False,hardlinks='conflict')
        self.assertEqual((self.dest/'second').read_text(),'keep')
    def test_hard_link_copy_rechecks_per_file_size_bound(self):
        self.tar([('file','safe',''),('second','file','hardlink')]);result=self.execute(False,hardlinks='oversize')
        self.assertIn('extraction size limit',result.stderr);self.assertFalse((self.dest/'second').exists())
    def test_hard_link_copy_cannot_escape_root(self):
        self.tar([('escape','../outside','hardlink')]);self.execute(False,hardlinks='denied');self.assertFalse((self.base/'outside').exists())
    def test_hard_link_copy_rejects_symbolic_target(self):
        self.tar([('file','safe',''),('link','file','symlink'),('second','link','hardlink')]);self.execute(False,hardlinks='denied')
    def test_hard_link_copy_chain_keeps_bytes(self):
        self.tar([('file','safe',''),('second','file','hardlink'),('third','second','hardlink')]);self.execute(hardlinks='denied')
        self.assertEqual((self.dest/'third').read_text(),'safe')
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

class ActualJavaPayloadImportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'.cache/apk-java-tests');self.base=Path(self.temp.name)
        self.source=self.base/'installed-apk-asset';self.source.write_bytes(b'complete original bytes, not a reduced engine')
        self.private=self.base/'private';self.private.mkdir();self.target=self.private/'runtime.tar.xz'
        self.digest=hashlib.sha256(self.source.read_bytes()).hexdigest()
    def tearDown(self):self.temp.cleanup()
    def execute(self,success=True,mode='copy',size=None,digest=None):
        p=subprocess.run([str(JAVA),'-cp',str(CLASSES),'dev.terminator.phone.VerifiedFilesHarness',str(self.source),str(self.target),mode,digest or self.digest,str(self.source.stat().st_size if size is None else size)],capture_output=True,text=True,timeout=10)
        if success:self.assertEqual(p.returncode,0,p.stderr)
        else:self.assertNotEqual(p.returncode,0,p.stdout)
        self.assertFalse(self.target.with_name(self.target.name+'.part').exists())
        return p
    def test_exact_bytes_and_private_permissions(self):
        before=self.source.read_bytes();self.execute();self.assertEqual(self.target.read_bytes(),before);self.assertEqual(self.source.read_bytes(),before)
        self.assertEqual(self.target.stat().st_mode&0o777,0o600)
    def test_verified_cache_does_not_need_original_apk_again(self):
        self.target.write_bytes(self.source.read_bytes());self.execute(mode='cached')
    def test_bad_digest_never_replaces_existing_file(self):
        self.target.write_bytes(b'preserve');self.execute(False,digest='0'*64);self.assertEqual(self.target.read_bytes(),b'preserve')
    def test_short_input_is_not_accepted(self):
        self.execute(False,size=self.source.stat().st_size+1);self.assertFalse(self.target.exists())
    def test_long_input_is_bounded_and_not_accepted(self):
        self.execute(False,size=3);self.assertFalse(self.target.exists())
    def test_interrupted_copy_keeps_old_file_and_can_retry(self):
        self.target.write_bytes(b'preserve');self.execute(False,mode='disconnect');self.assertEqual(self.target.read_bytes(),b'preserve')
        self.execute();self.assertEqual(self.target.read_bytes(),self.source.read_bytes())
    def test_cancel_removes_partial_and_keeps_old_file(self):
        self.target.write_bytes(b'preserve');self.execute(False,mode='cancel');self.assertEqual(self.target.read_bytes(),b'preserve')
    def test_matching_symlink_is_not_a_trusted_cache_file(self):
        self.target.symlink_to(self.source);self.execute();self.assertFalse(self.target.is_symlink());self.assertEqual(self.target.read_bytes(),self.source.read_bytes())
    def test_partial_symlink_does_not_overwrite_outside_file(self):
        outside=self.base/'outside';outside.write_bytes(b'keep');self.target.with_name(self.target.name+'.part').symlink_to(outside)
        self.execute();self.assertEqual(outside.read_bytes(),b'keep')
    def test_symlink_asset_directory_is_refused(self):
        self.private.rmdir();self.private.symlink_to(self.base, target_is_directory=True);self.execute(False);self.assertFalse(self.target.exists())


@unittest.skipUnless(os.environ.get('APK_TEST_ROOTFS'), 'Set APK_TEST_ROOTFS to the already verified pinned Ubuntu archive for the complete regression')
class CompleteUbuntuRegression(unittest.TestCase):
    def test_complete_original_rootfs_when_android_denies_every_hard_link(self):
        image=Path(os.environ['APK_TEST_ROOTFS']);lock=__import__('json').loads((ROOT/'android/app/inputs.lock.json').read_text())['rootfs']
        self.assertEqual(hashlib.sha256(image.read_bytes()).hexdigest(),lock['sha256'])
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache/apk-java-tests') as temp:
            dest=Path(temp)/'root'
            p=subprocess.run([str(JAVA),'-cp',str(CLASSES),'dev.terminator.phone.SafeTarHarness',str(image),str(dest),'xz','denied'],capture_output=True,text=True,timeout=180)
            self.assertEqual(p.returncode,0,p.stderr);self.assertIn('copiedHardLinks=2',p.stdout)
            with tarfile.open(image) as archive:
                for entry in archive:
                    if entry.isfile() or entry.islnk():
                        path=dest/entry.name
                        self.assertTrue(path.is_file(),entry.name)
                        self.assertEqual(hashlib.sha256(path.read_bytes()).digest(),hashlib.sha256(archive.extractfile(entry).read()).digest(),entry.name)
                        if entry.islnk():self.assertFalse(path.is_symlink(),entry.name)
            print('\nFull Ubuntu regression:',p.stdout.strip())


if __name__=='__main__':
    os.environ.update(LANG='C.UTF-8',LC_ALL='C.UTF-8')
    compile_tests();unittest.main()
