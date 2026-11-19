package dev.terminator.phone;

import android.content.Context;
import android.content.pm.*;
import android.os.Build;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermission;
import java.security.MessageDigest;
import java.util.*;

/** Public, signed APK assets only. Never opens another app's private workspace or loads its code. */
final class RuntimeAssets {
    private final Context context;
    private final JSONObject info;
    private final File directory;
    RuntimeAssets(Context c)throws Exception {
        context=c;
        try(InputStream in=c.getAssets().open("build-info.json")) {
            info=new JSONObject(new String(RuntimeInstaller.readBounded(in,1024*1024),StandardCharsets.UTF_8));
        }
        directory=new File(c.getFilesDir(),"verified-payloads");
    }
    JSONObject metadata(){return info;}
    boolean imported(){return info.has("importFromInstalled");}
    private File assetFile(String name)throws IOException {
        if(!name.matches("[A-Za-z0-9][A-Za-z0-9._-]{0,127}"))throw new IOException("Invalid asset name");
        return new File(directory,name);
    }
    private boolean valid(File file,JSONObject spec)throws Exception {
        return !Files.isSymbolicLink(file.toPath())&&RuntimeInstaller.verified(file,spec.getString("sha256"),spec.getLong("bytes"));
    }
    void prepare(RuntimeInstaller.Status status)throws Exception {
        if(!imported())return;
        String[] sections={"runtime","sourceArchive","nativeSources"};
        boolean missing=false;
        status.update("Original files check","Installed APK ke poore engine aur source archives verify ho rahe hain.",-1);
        for(String section:sections) {
            JSONObject spec=info.getJSONObject(section);
            if(!valid(assetFile(spec.getString("asset")),spec))missing=true;
        }
        if(!missing)return;
        JSONObject source=info.getJSONObject("importFromInstalled");
        String pkg=source.getString("packageName");
        if(pkg.equals(context.getPackageName()))throw new IOException("Repair package cannot import itself");
        PackageManager pm=context.getPackageManager();PackageInfo installed;
        try {
            installed=pm.getPackageInfo(pkg,Build.VERSION.SDK_INT>=28?PackageManager.GET_SIGNING_CERTIFICATES:PackageManager.GET_SIGNATURES);
        } catch(PackageManager.NameNotFoundException absent) {
            throw new IOException("Purana Terminator Test app installed rehna chahiye. Use uninstall ya clear mat karein; phir Retry dabayein.",absent);
        }
        long version=Build.VERSION.SDK_INT>=28?installed.getLongVersionCode():installed.versionCode;
        Signature[] signatures=Build.VERSION.SDK_INT>=28&&installed.signingInfo!=null?installed.signingInfo.getApkContentsSigners():installed.signatures;
        String signer=signatures!=null&&signatures.length==1?RuntimeInstaller.hex(MessageDigest.getInstance("SHA-256").digest(signatures[0].toByteArray())):"";
        if(version!=source.getLong("versionCode")||!source.getString("signerSha256").equals(signer))
            throw new IOException("Installed original APK ki identity match nahi hui. App data na mitayein; Diagnostics share karein.");
        if(installed.applicationInfo==null||!RuntimeInstaller.verified(new File(installed.applicationInfo.sourceDir),source.getString("apkSha256"),source.getLong("apkBytes")))
            throw new IOException("Installed original APK ka checksum match nahi hua. App data na mitayein.");
        // flags=0: resources/assets access, expressly no CONTEXT_INCLUDE_CODE or private data access.
        Context original=context.createPackageContext(pkg,0);
        Files.createDirectories(directory.toPath());
        Files.setPosixFilePermissions(directory.toPath(),EnumSet.of(PosixFilePermission.OWNER_READ,PosixFilePermission.OWNER_WRITE,PosixFilePermission.OWNER_EXECUTE));
        for(String section:sections) {
            if(Thread.currentThread().isInterrupted())throw new InterruptedIOException("Cancelled");
            JSONObject spec=info.getJSONObject(section);String name=spec.getString("asset");File target=assetFile(name);
            if(valid(target,spec))continue;
            status.update("Original files copy",name+" • poori file copy hogi; purana app aur uska data nahi badlega.",-1);
            VerifiedFiles.importAsset(()->original.getAssets().open(name),target,spec.getString("sha256"),spec.getLong("bytes"));
        }
        status.update("Original files copied","Poora engine aur dono original source archives verify ho gaye. Purana app/data untouched hai.",100);
    }
    InputStream open(String name)throws Exception {
        if(!imported()||(info.has("portSources")&&name.equals(info.getJSONObject("portSources").getString("asset"))))return context.getAssets().open(name);
        JSONObject spec=null;
        for(String section:new String[]{"runtime","sourceArchive","nativeSources"}) {
            JSONObject candidate=info.getJSONObject(section);
            if(name.equals(candidate.getString("asset")))spec=candidate;
        }
        if(spec==null)throw new IOException("Asset is not in the pinned import inventory");
        File file=assetFile(name);
        if(!valid(file,spec))throw new IOException("Pehle Prepare & start dabayein; original archives automatic copy honge. Purana app installed rakhein.");
        return Files.newInputStream(file.toPath(),StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS);
    }
}
