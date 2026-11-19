package dev.terminator.phone;

import android.app.*;
import android.content.*;
import android.os.*;
import android.util.Base64;
import org.json.*;
import java.io.*;
import java.lang.Process;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

public final class RuntimeService extends Service {
    static final String START="dev.terminator.phone.START",STOP="dev.terminator.phone.STOP";
    private static final String CHANNEL="local-engine";
    static volatile RuntimeService current;
    volatile String phase="Band hai",detail="Start dabakar phone par bot taiyar karein.",origin;
    volatile int progress=-1; volatile boolean ready=false;
    private final AtomicBoolean running=new AtomicBoolean();
    private final StringBuilder logs=new StringBuilder();
    private final List<String> cookies=new ArrayList<>();
    private volatile Process process;private volatile Thread worker;private volatile boolean stopping;
    private PowerManager.WakeLock wake;
    RuntimeInstaller.Plan plan;

    @Override public void onCreate(){
        super.onCreate();current=this;
        NotificationChannel channel=new NotificationChannel(CHANNEL,"Local bot engine",NotificationManager.IMPORTANCE_LOW);
        channel.setDescription("Visible while the phone hosts the local bot. Stop is always available.");channel.setLockscreenVisibility(Notification.VISIBILITY_PRIVATE);
        ((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).createNotificationChannel(channel);
    }
    @Override public int onStartCommand(Intent intent,int flags,int id){
        if(intent!=null&&STOP.equals(intent.getAction())){stopEngine();return START_NOT_STICKY;}
        if(intent==null||!START.equals(intent.getAction())){stopSelf();return START_NOT_STICKY;}
        startForeground(7,notification());
        if(running.compareAndSet(false,true)){
            stopping=false;PowerManager manager=(PowerManager)getSystemService(POWER_SERVICE);
            wake=manager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"Terminator:VisibleEngine");wake.acquire(6L*60*60*1000);
            worker=new Thread(this::work,"phone-engine");worker.start();
        }
        return START_NOT_STICKY;
    }
    private void work(){
        try{
            update("Taiyari shuru","Original engine app ke private folder mein rahega.",0);
            plan=new RuntimeInstaller(this,this::update).prepare();
            if(stopping)throw new InterruptedException();
            File checked=new File(plan.runtime,".phone-native-probes-passed");
            if(!checked.isFile()){
                update("Phone engine check","ARM64 Node, database aur REA check ho rahe hain.",-1);
                Process probe=builder("/opt/terminator/bootstrap/runtime-smoke.mjs","--runtime","/opt/terminator/runtime").start();process=probe;
                Thread reader=readOutput(probe,null);
                if(!probe.waitFor(120,TimeUnit.SECONDS)){probe.destroyForcibly();throw new IOException("Phone native-engine check timed out. Diagnostics dekhein.");}
                reader.join(2000);if(probe.exitValue()!=0)throw new IOException("Phone par native-engine check pass nahi hua. Diagnostics mein asli error dekhein.");
                try(FileOutputStream out=new FileOutputStream(checked)){out.write("passed; device only; not full parity\n".getBytes(StandardCharsets.UTF_8));}
            }
            if(stopping)throw new InterruptedException();
            update("Bot shuru ho raha hai","Original OpenMausBot server phone par start ho raha hai.",-1);
            int port=freePort(),webhookPort=freePort();while(webhookPort==port)webhookPort=freePort();
            origin="http://127.0.0.1:"+port;
            ProcessBuilder builder=builder("/opt/terminator/runtime/node_modules/openmausbot/dist-server/index.js");
            builder.environment().put("OMB_PORT",String.valueOf(port));builder.environment().put("OMB_WEBHOOK_PORT",String.valueOf(webhookPort));
            builder.environment().put("OMB_CLI_OWNER_STDIN","1");
            CountDownLatch listening=new CountDownLatch(1);process=builder.start();readOutput(process,listening);
            byte[] random=new byte[32];new SecureRandom().nextBytes(random);
            String owner=Base64.encodeToString(random,Base64.URL_SAFE|Base64.NO_WRAP|Base64.NO_PADDING);
            try(OutputStream input=process.getOutputStream()){input.write((owner+"\n").getBytes(StandardCharsets.US_ASCII));input.flush();}
            long deadline=SystemClock.elapsedRealtime()+120000;
            while(!listening.await(250,TimeUnit.MILLISECONDS)){
                if(!process.isAlive())throw new IOException("Original server start nahi ho paya. Diagnostics dekhein.");
                if(SystemClock.elapsedRealtime()>deadline)throw new IOException("Server readiness timeout. Phone diagnostics dekhein.");
            }
            if(stopping||!process.isAlive())throw new InterruptedException();
            JSONObject health=LocalApi.call(origin,"GET","/api/health",null,null,null).body;
            if(!"openmausbot".equals(health.optString("app"))||!"0.1.169".equals(health.optString("version")))throw new IOException("Unexpected local engine identity");
            JSONObject request=new JSONObject().put("label","Terminator Android owner").put("ttlMs",60000);
            String code=LocalApi.call(origin,"POST","/api/auth/pairing",request,owner,null).body.getString("code");
            owner=null;Arrays.fill(random,(byte)0);
            LocalApi.Reply paired=LocalApi.call(origin,"POST","/api/auth/pair",new JSONObject().put("code",code).put("cookie",true).put("label","Terminator Android"),null,null);
            code=null;if(paired.cookies.isEmpty())throw new IOException("Upstream did not issue a session cookie");
            synchronized(cookies){cookies.clear();cookies.addAll(paired.cookies);}
            // Positive session check, not merely an HTML page loading successfully.
            LocalApi.call(origin,"GET","/api/config",null,null,cookieHeader());
            ready=true;update("Bot ready hai","Open bot dabayein. AI provider apni key se configure karein. Full Android parity abhi certified nahi hai.",-1);
            int exit=process.waitFor();if(!stopping)throw new IOException("Engine band ho gaya (exit "+exit+"). Retry ya Diagnostics kholein.");
        }catch(InterruptedException|InterruptedIOException error){Thread.currentThread().interrupt();update("Band hai","Aapne engine rok diya.",-1);
        }catch(Exception error){log("ERROR: "+safe(error.getMessage()));update("Start nahi ho paya",safe(error.getMessage()),-1);
        }finally{
            ready=false;Process child=process;if(child!=null&&child.isAlive()){
                child.destroy();try{if(!child.waitFor(4,TimeUnit.SECONDS))child.destroyForcibly();}catch(InterruptedException e){child.destroyForcibly();Thread.currentThread().interrupt();}
            }
            process=null;running.set(false);releaseWake();
            // Leave the explanatory error on the dashboard, never a hidden daemon.
            stopForeground(true);
        }
    }
    private ProcessBuilder builder(String... nodeArgs)throws IOException{
        String nativeDir=getApplicationInfo().nativeLibraryDir;
        List<String> args=new ArrayList<>();Collections.addAll(args,nativeDir+"/libproot.so","--kill-on-exit","--link2symlink","--change-id=1000:1000","-r",plan.root.getAbsolutePath(),"-b","/dev","-b","/proc","-b",plan.runtime.getAbsolutePath()+":/opt/terminator","-b",plan.home.getAbsolutePath()+":/home/terminator","-b",plan.tmp.getAbsolutePath()+":/tmp","-w","/home/terminator","/opt/terminator/node/bin/node");
        Collections.addAll(args,nodeArgs);ProcessBuilder builder=new ProcessBuilder(args);builder.directory(plan.home);builder.redirectErrorStream(true);
        Map<String,String> env=builder.environment();env.clear();
        env.put("ANDROID_ROOT","/system");env.put("ANDROID_DATA","/data");env.put("PROOT_TMP_DIR",plan.tmp.getAbsolutePath());env.put("PROOT_LOADER",nativeDir+"/libproot-loader.so");env.put("PROOT_LOADER_32",nativeDir+"/libproot-loader32.so");
        env.put("PROOT_NO_SECCOMP","1");env.put("HOME","/home/terminator");env.put("USER","terminator");env.put("LOGNAME","terminator");env.put("LANG","C.UTF-8");env.put("TMPDIR","/tmp");env.put("SHELL","/bin/bash");
        env.put("PATH","/opt/terminator/node/bin:/opt/terminator/runtime/node_modules/.bin:/usr/local/bin:/usr/bin:/bin");
        env.put("NODE_OPTIONS","--max-old-space-size=1024");env.put("GLIBC_TUNABLES","glibc.pthread.rseq=0");
        env.put("OMB_DATA_DIR","/home/terminator/.openmausbot");env.put("OMB_STATIC_DIR","/opt/terminator/runtime/node_modules/openmausbot/dist");env.put("OMB_LOOPBACK_TRUST","service");
        return builder;
    }
    private Thread readOutput(Process child,CountDownLatch listening){
        Thread reader=new Thread(()->{
            try(BufferedReader input=new BufferedReader(new InputStreamReader(child.getInputStream(),StandardCharsets.UTF_8))){
                for(String line;(line=input.readLine())!=null;){log(line);if(listening!=null&&line.contains("openmausbot server on http://"))listening.countDown();}
            }catch(IOException ignored){/* process stop closes the stream */}
        },"engine-output");reader.setDaemon(true);reader.start();return reader;
    }
    private static int freePort()throws IOException{try(ServerSocket socket=new ServerSocket(0,1,InetAddress.getByName("127.0.0.1"))){return socket.getLocalPort();}}
    private Notification notification(){
        PendingIntent open=PendingIntent.getActivity(this,1,new Intent(this,MainActivity.class),PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent stop=PendingIntent.getService(this,2,new Intent(this,RuntimeService.class).setAction(STOP),PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
        Notification.Builder n=new Notification.Builder(this,CHANNEL).setSmallIcon(dev.terminator.phone.R.drawable.ic_launcher).setContentTitle("Terminator · "+phase).setContentText(detail).setContentIntent(open).setOngoing(true).setVisibility(Notification.VISIBILITY_PRIVATE).addAction(new Notification.Action.Builder(null,"Stop",stop).build());
        if(progress>=0)n.setProgress(100,progress,false);return n.build();
    }
    private void update(String title,String message,int percent){phase=title;detail=message==null?"Unknown error":message;progress=percent;if(running.get())((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).notify(7,notification());}
    private static String safe(String message){if(message==null)return "Unknown engine error";return message.replaceAll("(?i)(omb_sess_|omb_pair_|gsk_|sk-)[A-Za-z0-9_-]+","[credential redacted]");}
    private void log(String message){synchronized(logs){logs.append(safe(message)).append('\n');if(logs.length()>16000)logs.delete(0,logs.length()-16000);}}
    String diagnostics(){synchronized(logs){return "Android "+Build.VERSION.RELEASE+" · "+Build.MANUFACTURER+" "+Build.MODEL+"\nABI "+Arrays.toString(Build.SUPPORTED_ABIS)+"\nFull parity: NOT CERTIFIED\n\n"+logs;}}
    String cookieHeader(){synchronized(cookies){return LocalApi.cookieHeader(cookies);}}
    List<String> sessionCookies(){synchronized(cookies){return new ArrayList<>(cookies);}}
    boolean active(){return running.get();}
    private void releaseWake(){if(wake!=null&&wake.isHeld())wake.release();}
    private void stopEngine(){stopping=true;ready=false;Thread t=worker;if(t!=null)t.interrupt();Process child=process;if(child!=null)child.destroy();releaseWake();phase="Band hai";detail="Engine roka gaya. Aapka data phone par saved hai.";stopForeground(true);stopSelf();}
    @Override public void onDestroy(){stopping=true;Thread t=worker;if(t!=null)t.interrupt();Process child=process;if(child!=null)child.destroy();releaseWake();if(current==this)current=null;super.onDestroy();}
    @Override public IBinder onBind(Intent intent){return null;}
}
