package dev.terminator.phone;

import android.content.Context;
import android.net.*;
import android.os.*;
import org.json.*;
import org.tukaani.xz.XZInputStream;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.security.*;
import java.util.*;
import java.util.zip.GZIPInputStream;

final class RuntimeInstaller {
    interface Status { void update(String phase,String detail,int percent); }
    static final class Plan {
        File root,runtime,home,tmp; JSONObject metadata;
    }
    private final Context context; private final Status status;
    private long lastProgress;
    RuntimeInstaller(Context c,Status s){context=c;status=s;}
    JSONObject metadata() throws Exception {
        try(InputStream in=context.getAssets().open("build-info.json")){return new JSONObject(new String(readBounded(in,1024*1024),StandardCharsets.UTF_8));}
    }
    Plan prepare() throws Exception {
        if(!Arrays.asList(Build.SUPPORTED_ABIS).contains("arm64-v8a"))throw new IOException("Yeh APK ARM64 phone ke liye hai.");
        JSONObject info=metadata(),os=info.getJSONObject("rootfs"),run=info.getJSONObject("runtime");
        File base=context.getFilesDir(); Plan p=new Plan();p.metadata=info;
        p.root=new File(base,"linux-"+os.getString("sha256").substring(0,12));
        p.runtime=new File(base,"engine-"+run.getString("sha256").substring(0,12));
        boolean needsRoot=!complete(p.root,os.getString("sha256")),needsRuntime=!complete(p.runtime,run.getString("sha256"));
        if((needsRoot||needsRuntime)&&new StatFs(base.getAbsolutePath()).getAvailableBytes()<1600L*1024*1024)throw new IOException("Phone mein kam-se-kam 1.6 GB khaali jagah chahiye.");
        if(needsRoot){
            File image=new File(context.getCacheDir(),"ubuntu-"+os.getString("sha256")+".tar.xz");
            if(!verified(image,os.getString("sha256"),os.getLong("bytes")))download(os,image);
            status.update("Linux taiyar ho raha hai","Pehli baar files khul rahi hain. App ko khula rakhein.",0);
            install(image,p.root,os.getString("sha256"),true,os.getLong("expandedBytes"),"Linux taiyar ho raha hai");
            if(!image.delete())image.deleteOnExit();
        }
        if(needsRuntime){
            status.update("Original engine taiyar ho raha hai","OpenMausBot, REA aur ARM64 Node install ho rahe hain.",0);
            String asset=run.getString("asset");File compressed=new File(context.getCacheDir(),asset);
            try(InputStream in=context.getAssets().open(asset);OutputStream out=new FileOutputStream(compressed)){copy(in,out,run.getLong("bytes"));}
            if(!verified(compressed,run.getString("sha256"),run.getLong("bytes")))throw new IOException("Bundled engine checksum galat hai. APK dobara download karein.");
            install(compressed,p.runtime,run.getString("sha256"),asset.endsWith(".xz"),run.getLong("expandedBytes"),"Original engine taiyar ho raha hai");
            if(!compressed.delete())compressed.deleteOnExit();
        }
        p.home=new File(base,"home");p.tmp=new File(context.getCacheDir(),"linux-tmp");
        Files.createDirectories(p.home.toPath());Files.createDirectories(p.tmp.toPath());
        Files.createDirectories(new File(p.home,".openmausbot").toPath());Files.createDirectories(new File(p.home,"files").toPath());
        for(String name:new String[]{"opt/terminator","home/terminator","tmp","dev","proc"})Files.createDirectories(new File(p.root,name).toPath());
        // Do not follow the distribution's resolv.conf symlink into /run.
        Path dns=new File(p.root,"etc/resolv.conf").toPath();Files.deleteIfExists(dns);
        StringBuilder resolvers=new StringBuilder();
        ConnectivityManager manager=(ConnectivityManager)context.getSystemService(Context.CONNECTIVITY_SERVICE);
        if(manager!=null){LinkProperties properties=manager.getLinkProperties(manager.getActiveNetwork());if(properties!=null)for(InetAddress address:properties.getDnsServers())resolvers.append("nameserver ").append(address.getHostAddress()).append('\n');}
        if(resolvers.length()==0)resolvers.append("nameserver 1.1.1.1\nnameserver 8.8.8.8\n");
        Files.write(dns,resolvers.toString().getBytes(StandardCharsets.UTF_8),StandardOpenOption.CREATE_NEW);
        Path passwd=new File(p.root,"etc/passwd").toPath();String existing=new String(Files.readAllBytes(passwd),StandardCharsets.UTF_8);
        if(!existing.contains("\nterminator:"))Files.write(passwd,"\nterminator:x:1000:1000:Terminator:/home/terminator:/bin/bash\n".getBytes(StandardCharsets.UTF_8),StandardOpenOption.APPEND);
        return p;
    }
    private boolean complete(File folder,String hash)throws IOException{
        File marker=new File(folder,".terminator-complete");if(!marker.isFile())return false;
        return hash.equals(new String(Files.readAllBytes(marker.toPath()),StandardCharsets.US_ASCII));
    }
    private void install(File compressed,File destination,String hash,boolean xz,long expectedExpanded,String title)throws Exception{
        File staging=new File(context.getFilesDir(),destination.getName()+".installing");removeTree(staging.toPath());Files.createDirectory(staging.toPath());
        try{
            try(InputStream file=new BufferedInputStream(new FileInputStream(compressed),65536);InputStream in=xz?new XZInputStream(file,131072):new GZIPInputStream(file,65536)){
                SafeTar.extract(in,staging,(bytes,count)->{
                    long now=SystemClock.elapsedRealtime();if(now-lastProgress>750){lastProgress=now;int percent=(int)Math.min(99,bytes*100/Math.max(1,expectedExpanded));status.update(title,count+" files • "+(bytes/1048576)+" MB",percent);}
                });
            }
            Files.write(new File(staging,".terminator-complete").toPath(),hash.getBytes(StandardCharsets.US_ASCII),StandardOpenOption.CREATE_NEW);
            removeTree(destination.toPath());Files.move(staging.toPath(),destination.toPath(),StandardCopyOption.ATOMIC_MOVE);
        }catch(Exception error){removeTree(staging.toPath());throw error;}
    }
    private void download(JSONObject os,File output)throws Exception{
        status.update("Pehli baar download","Ubuntu environment • lagbhag 65 MB. Ismein AI model shamil nahi hai.",0);
        File partial=new File(output.getPath()+".part");HttpURLConnection connection=null;
        try{
            URL url=new URL(os.getString("url"));
            if(!"https".equals(url.getProtocol())||!"api.github.com".equals(url.getHost()))throw new IOException("Untrusted runtime source");
            connection=(HttpURLConnection)url.openConnection();connection.setInstanceFollowRedirects(false);connection.setConnectTimeout(20000);connection.setReadTimeout(30000);
            connection.setRequestProperty("Accept","application/vnd.github.raw+json");connection.setRequestProperty("User-Agent","Terminator-Android/0.2.0");
            if(connection.getResponseCode()!=200)throw new IOException("Runtime download nahi hua (HTTP "+connection.getResponseCode()+"). Internet check karke Retry dabayein.");
            long expected=os.getLong("bytes"),received=0;
            try(InputStream in=connection.getInputStream();OutputStream out=new FileOutputStream(partial)){
                byte[] buffer=new byte[65536];for(int n;(n=in.read(buffer))!=-1;){
                    if(Thread.currentThread().isInterrupted())throw new InterruptedIOException("Cancelled");
                    received+=n;if(received>expected)throw new IOException("Runtime download exceeds pinned size");out.write(buffer,0,n);
                    long now=SystemClock.elapsedRealtime();if(now-lastProgress>750){lastProgress=now;status.update("Pehli baar download",(received/1048576)+" / "+(expected/1048576)+" MB",(int)(received*100/expected));}
                }
            }
            if(!verified(partial,os.getString("sha256"),expected))throw new IOException("Runtime ki integrity verify nahi hui. Download dobara karna hoga.");
            Files.move(partial.toPath(),output.toPath(),StandardCopyOption.REPLACE_EXISTING);
        }finally{if(connection!=null)connection.disconnect();if(partial.exists())partial.delete();}
    }
    static void removeTree(Path path)throws IOException{
        if(!Files.exists(path,LinkOption.NOFOLLOW_LINKS))return;
        Files.walkFileTree(path,new SimpleFileVisitor<Path>(){
            @Override public FileVisitResult visitFile(Path f,BasicFileAttributes a)throws IOException{Files.delete(f);return FileVisitResult.CONTINUE;}
            @Override public FileVisitResult postVisitDirectory(Path d,IOException e)throws IOException{if(e!=null)throw e;Files.delete(d);return FileVisitResult.CONTINUE;}
        });
    }
    static boolean verified(File file,String expected,long bytes)throws Exception{
        if(!file.isFile()||file.length()!=bytes)return false;MessageDigest digest=MessageDigest.getInstance("SHA-256");
        try(InputStream in=new FileInputStream(file)){byte[] buffer=new byte[65536];for(int n;(n=in.read(buffer))!=-1;)digest.update(buffer,0,n);}
        return MessageDigest.isEqual(hex(digest.digest()).getBytes(StandardCharsets.US_ASCII),expected.getBytes(StandardCharsets.US_ASCII));
    }
    static String hex(byte[] bytes){StringBuilder s=new StringBuilder();for(byte b:bytes)s.append(String.format(Locale.ROOT,"%02x",b&255));return s.toString();}
    static byte[] readBounded(InputStream in,int limit)throws IOException{ByteArrayOutputStream out=new ByteArrayOutputStream();copy(in,out,limit);return out.toByteArray();}
    static void copy(InputStream in,OutputStream out,long max)throws IOException{long total=0;byte[] buffer=new byte[65536];for(int n;(n=in.read(buffer))!=-1;){if(Thread.currentThread().isInterrupted())throw new InterruptedIOException("Cancelled");total+=n;if(total>max)throw new IOException("File size limit exceeded");out.write(buffer,0,n);}}
}
