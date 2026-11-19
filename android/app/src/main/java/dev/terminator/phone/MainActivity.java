package dev.terminator.phone;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.*;
import android.provider.OpenableColumns;
import android.view.*;
import android.webkit.*;
import android.widget.*;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.*;
import java.util.*;

public final class MainActivity extends Activity {
    private static final int BG=0xff0b1118,CARD=0xff151e29,TEXT=0xfff1f5f9,MUTED=0xff94a3b8,MINT=0xff5eead4;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private TextView status,detail;private ProgressBar progress;private Button start,open;private LinearLayout container,dashboard;
    private WebView web;private ValueCallback<Uri[]> chooser;private PermissionRequest microphone;
    private String exportAsset,exportHash;private long exportBytes;
    private final Runnable refresh=new Runnable(){@Override public void run(){refreshState();handler.postDelayed(this,800);}};

    @Override public void onCreate(Bundle state){super.onCreate(state);getWindow().setStatusBarColor(BG);getWindow().setNavigationBarColor(BG);home();}
    @Override protected void onResume(){super.onResume();handler.post(refresh);}
    @Override protected void onPause(){handler.removeCallbacks(refresh);super.onPause();}
    @Override protected void onDestroy(){handler.removeCallbacks(refresh);if(chooser!=null)chooser.onReceiveValue(null);if(microphone!=null)microphone.deny();destroyWeb();super.onDestroy();}
    private int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
    private TextView text(String value,int size,int color){TextView t=new TextView(this);t.setText(value);t.setTextColor(color);t.setTextSize(size);t.setPadding(0,dp(6),0,dp(6));return t;}
    private Button button(String label,Runnable action){Button b=new Button(this);b.setText(label);b.setAllCaps(false);b.setTextColor(BG);b.setTextSize(15);b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(MINT));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,dp(52));p.setMargins(0,dp(6),0,dp(6));b.setLayoutParams(p);b.setOnClickListener(v->action.run());return b;}
    private boolean repair(){return "dev.terminator.phone.repair".equals(getPackageName());}
    private void home(){
        destroyWeb();container=new LinearLayout(this);container.setOrientation(1);container.setBackgroundColor(BG);setContentView(container);
        ScrollView scroll=new ScrollView(this);container.addView(scroll,new LinearLayout.LayoutParams(-1,-1));dashboard=new LinearLayout(this);dashboard.setOrientation(1);dashboard.setPadding(dp(24),dp(24),dp(24),dp(32));scroll.addView(dashboard);
        TextView eyebrow=text("PHONE-HOSTED AI WORKSPACE",11,MINT);eyebrow.setLetterSpacing(.14f);dashboard.addView(eyebrow);
        TextView title=text(repair()?"Terminator Repair":"Terminator",repair()?32:38,TEXT);title.setTypeface(Typeface.DEFAULT,Typeface.BOLD);dashboard.addView(title);
        dashboard.addView(text(repair()?"Linux installer repair · original local engine\nPurana app/data delete nahi hoga.":"Original engine. A real Android app.\nNo Termux commands.",17,MUTED));
        TextView badge=text("DEVELOPMENT BUILD  ·  NOT FULL-PARITY CERTIFIED",11,0xfffbbf24);badge.setPadding(0,dp(18),0,dp(18));dashboard.addView(badge);
        LinearLayout card=new LinearLayout(this);card.setOrientation(1);card.setPadding(dp(18),dp(14),dp(18),dp(16));GradientDrawable shape=new GradientDrawable();shape.setColor(CARD);shape.setCornerRadius(dp(18));card.setBackground(shape);dashboard.addView(card);
        status=text("Ready to prepare",22,TEXT);status.setTypeface(Typeface.DEFAULT,Typeface.BOLD);card.addView(status);detail=text("Pehli baar Start dabayein. App engine khud taiyar karegi.",14,MUTED);card.addView(detail);
        progress=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);progress.setMax(100);progress.setProgressTintList(android.content.res.ColorStateList.valueOf(MINT));card.addView(progress,new LinearLayout.LayoutParams(-1,dp(5)));progress.setVisibility(View.GONE);
        start=button("Prepare & start bot",this::consentAndStart);dashboard.addView(start);
        open=button("Open bot",this::openBot);dashboard.addView(open);
        dashboard.addView(button("Stop engine",this::stopBot));
        dashboard.addView(text("ORIGINAL ENGINE FILES",11,MINT));dashboard.addView(text("OpenMausBot 0.1.169  /  REA 6.9.0\nARM64 Node 24.22.1 + original source archive",14,MUTED));
        if(repair())dashboard.addView(text("Pehli taiyari ke liye purana Terminator Test installed rakhein. Uske signed APK se poore engine/source archives verify karke copy honge. Private chats, keys ya settings access/migrate nahi honge. Yeh alag app hai, purane app ka in-place update nahi.",13,MUTED));
        dashboard.addView(button("Connect REA tools",this::connectRea));dashboard.addView(button("Import a file",this::importFile));
        dashboard.addView(button("Feature status & important limits",()->assetDialog("Feature status","feature-status.txt")));
        dashboard.addView(button("Sources & licenses",this::sourceDialog));dashboard.addView(button("Diagnostics",this::diagnostics));
        dashboard.addView(text("Your workspace stays in this app's private storage. Uninstalling deletes it. Internet and your own AI provider account/key are needed for cloud models. This APK does not include a paid subscription or an offline AI model.",12,MUTED));refreshState();
    }
    private void refreshState(){
        if(status==null)return;RuntimeService service=RuntimeService.current;
        if(service==null){status.setText("Engine band hai");detail.setText(repair()?"Start dabayein. Purane installed APK se files copy hongi; purana app/data nahi badlega. 2 GB khaali jagah rakhein.":"Start dabayein. Pehli taiyari automatic hogi; uske baad saved workspace khulega.");progress.setVisibility(View.GONE);start.setEnabled(true);open.setEnabled(false);return;}
        status.setText(service.phase);detail.setText(service.detail);start.setEnabled(!service.active());open.setEnabled(service.ready);
        progress.setVisibility(service.active()&&!service.ready?View.VISIBLE:View.GONE);progress.setIndeterminate(service.progress<0);if(service.progress>=0)progress.setProgress(service.progress);
    }
    private void consentAndStart(){
        if(getPreferences(0).getBoolean("runtime-consent-v1",false)){startBot();return;}
        new AlertDialog.Builder(this).setTitle("Phone par original engine taiyar karein?")
            .setMessage((repair()?"Yeh alag repair app hai, purane app ka update nahi. Purana Terminator Test installed rakhein: uske public signed APK se poora engine aur original source archives copy honge. Purana private data/settings na access honge na delete; yahan naya private workspace banega. Kam-se-kam 2 GB free storage rakhein.\n\n":"Kam-se-kam 1.6 GB free storage rakhein.\n\n")+"Pehli baar lagbhag 65 MB Ubuntu environment download hoga. Aapko commands ya Termux install nahi karna hai.\n\nYeh testing APK hai: desktop VM/Docker, Android app-control aur poori feature parity abhi verified nahi hain. Original code aur approval controls retained hain; Linux environment bot ke liye security sandbox nahi hai.\n\nEngine chalte waqt visible notification aur battery usage hogi. Stop kabhi bhi daba sakte hain. Paid AI key/subscription ismein nahi hai. Play Protect ya phone security band mat karein.")
            .setNegativeButton("Abhi nahi",null).setPositiveButton("Prepare & start",(d,w)->{getPreferences(0).edit().putBoolean("runtime-consent-v1",true).apply();startBot();}).show();
    }
    private void startBot(){startForegroundService(new Intent(this,RuntimeService.class).setAction(RuntimeService.START));handler.postDelayed(this::refreshState,150);}
    private void stopBot(){destroyWeb();CookieManager.getInstance().removeAllCookies(null);CookieManager.getInstance().flush();startService(new Intent(this,RuntimeService.class).setAction(RuntimeService.STOP));home();}
    private void openBot(){
        RuntimeService service=RuntimeService.current;if(service==null||!service.ready){message("Abhi ready nahi","Pehle engine ko start hone dein.");return;}
        final String local=service.origin;CookieManager cookies=CookieManager.getInstance();cookies.setAcceptCookie(true);
        for(String cookie:service.sessionCookies())cookies.setCookie(local,cookie);cookies.flush();
        container.removeAllViews();LinearLayout toolbar=new LinearLayout(this);toolbar.setPadding(dp(8),0,dp(8),0);toolbar.setGravity(Gravity.CENTER_VERTICAL);container.addView(toolbar,new LinearLayout.LayoutParams(-1,dp(52)));
        Button back=new Button(this);back.setText("‹ Home");back.setAllCaps(false);back.setOnClickListener(v->home());toolbar.addView(back,new LinearLayout.LayoutParams(dp(110),-1));TextView label=text("LOCAL ENGINE",11,MINT);label.setGravity(Gravity.CENTER);toolbar.addView(label,new LinearLayout.LayoutParams(0,-1,1));
        web=new WebView(this);container.addView(web,new LinearLayout.LayoutParams(-1,0,1));web.setBackgroundColor(BG);
        WebSettings settings=web.getSettings();settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);settings.setAllowFileAccess(false);settings.setAllowContentAccess(true);settings.setAllowFileAccessFromFileURLs(false);settings.setAllowUniversalAccessFromFileURLs(false);settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);settings.setMediaPlaybackRequiresUserGesture(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web,false);
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){
                Uri uri=request.getUrl();if(sameOrigin(uri,local))return false;
                if(request.isForMainFrame()&&"https".equals(uri.getScheme()))external(uri);return true;
            }
            @Override public void onReceivedError(WebView view,WebResourceRequest request,WebResourceError error){if(request.isForMainFrame())Toast.makeText(MainActivity.this,"Engine connection toot gaya. Home > Diagnostics dekhein.",Toast.LENGTH_LONG).show();}
        });
        web.setWebChromeClient(new WebChromeClient(){
            @Override public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> callback,FileChooserParams params){
                if(chooser!=null)chooser.onReceiveValue(null);chooser=callback;
                Intent picker=new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*").putExtra(Intent.EXTRA_ALLOW_MULTIPLE,params.getMode()==FileChooserParams.MODE_OPEN_MULTIPLE);
                startActivityForResult(picker,41);return true;
            }
            @Override public void onPermissionRequest(PermissionRequest request){runOnUiThread(()->{
                if(!sameOrigin(request.getOrigin(),local)){request.deny();return;}
                for(String resource:request.getResources())if(!PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(resource)){request.deny();return;}
                new AlertDialog.Builder(MainActivity.this).setTitle("Microphone use karein?").setMessage("Sirf is local bot page ko, aapke OS permission ke saath. Background recording start nahi hogi.").setNegativeButton("Nahi",(d,w)->request.deny()).setPositiveButton("Allow",(d,w)->{
                    if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)==PackageManager.PERMISSION_GRANTED)request.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
                    else{if(microphone!=null)microphone.deny();microphone=request;requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},42);}
                }).show();
            });}
            @Override public void onPermissionRequestCanceled(PermissionRequest request){if(microphone==request)microphone=null;}
        });
        web.loadUrl(local+"/");
    }
    private static boolean sameOrigin(Uri uri,String origin){return uri!=null&&origin!=null&&"http".equals(uri.getScheme())&&"127.0.0.1".equals(uri.getHost())&&uri.getPort()==Uri.parse(origin).getPort()&&uri.getUserInfo()==null;}
    private void external(Uri uri){new AlertDialog.Builder(this).setTitle("Browser mein kholein?").setMessage(uri.getHost()).setNegativeButton("Cancel",null).setPositiveButton("Open browser",(d,w)->{try{startActivity(new Intent(Intent.ACTION_VIEW,uri));}catch(ActivityNotFoundException e){message("Browser nahi mila","Phone par HTTPS links kholne ke liye browser chahiye.");}}).show();}
    private void destroyWeb(){if(web!=null){web.stopLoading();web.loadUrl("about:blank");web.setWebChromeClient(null);web.destroy();web=null;}}
    @Override public void onBackPressed(){if(web!=null){if(web.canGoBack())web.goBack();else home();}else super.onBackPressed();}
    @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] result){super.onRequestPermissionsResult(code,permissions,result);if(code==42&&microphone!=null){if(result.length>0&&result[0]==PackageManager.PERMISSION_GRANTED&&web!=null)microphone.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});else microphone.deny();microphone=null;}}
    private void importFile(){startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*"),43);}
    private void sourceDialog(){new AlertDialog.Builder(this).setTitle("Original sources & licenses").setItems(repair()?new String[]{"Export all original source blobs","Export PRoot / talloc / XZ corresponding source","Read licenses & provenance","Export repair app source"}:new String[]{"Export all original source blobs","Export PRoot / talloc / XZ corresponding source","Read licenses & provenance"},(d,which)->{if(which==2)assetDialog("Licenses & provenance","license-notes.txt");else exportSource(which==0?"sourceArchive":which==1?"nativeSources":"portSources");}).show();}
    private void exportSource(String section){
        try{JSONObject info=new RuntimeInstaller(this,(a,b,c)->{}).metadata();JSONObject source=info.getJSONObject(section);exportAsset=source.getString("asset");exportHash=source.getString("sha256");exportBytes=source.getLong("bytes");
            startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType(exportAsset.endsWith(".xz")?"application/x-xz":"application/gzip").putExtra(Intent.EXTRA_TITLE,"terminator-"+exportAsset),44);
        }catch(Exception error){message("Export nahi hua",error.getMessage());}
    }
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);
        if(request==41){if(chooser!=null){Uri[] values=null;if(result==RESULT_OK&&data!=null){if(data.getClipData()!=null){values=new Uri[data.getClipData().getItemCount()];for(int i=0;i<values.length;i++)values[i]=data.getClipData().getItemAt(i).getUri();}else if(data.getData()!=null)values=new Uri[]{data.getData()};}chooser.onReceiveValue(values);chooser=null;}return;}
        if(result!=RESULT_OK||data==null||data.getData()==null)return;final Uri uri=data.getData();
        if(request==43)new Thread(()->{try{String name="imported-file";try(Cursor cursor=getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){if(cursor!=null&&cursor.moveToFirst())name=cursor.getString(0);}name=name.replaceAll("[\\p{Cntrl}/\\\\]","_");if(name.length()>100)name=name.substring(name.length()-100);if(name.equals(".")||name.equals(".."))throw new IOException("Invalid filename");
            File dir=new File(getFilesDir(),"home/files");Files.createDirectories(dir.toPath());File target=new File(dir,System.currentTimeMillis()+"-"+name);
            try(InputStream in=getContentResolver().openInputStream(uri);OutputStream out=Files.newOutputStream(target.toPath(),StandardOpenOption.CREATE_NEW)){RuntimeInstaller.copy(in,out,128L*1024*1024);}final String shown=target.getName();runOnUiThread(()->message("File import ho gayi","Bot workspace: /home/terminator/files/"+shown+"\nFile automatically execute nahi hui hai."));
        }catch(Exception e){runOnUiThread(()->message("Import nahi hua",e.getMessage()));}},"document-import").start();
        if(request==44){final String asset=exportAsset,hash=exportHash;final long expected=exportBytes;new Thread(()->{try{MessageDigest digest=MessageDigest.getInstance("SHA-256");try(InputStream input=new DigestInputStream(new RuntimeAssets(this).open(asset),digest);OutputStream output=getContentResolver().openOutputStream(uri,"w")){RuntimeInstaller.copy(input,output,expected);}if(!RuntimeInstaller.hex(digest.digest()).equals(hash))throw new IOException("Export checksum failed");runOnUiThread(()->message("Sources export ho gaye","Archive ka SHA-256 verify ho gaya. Original source files aur provenance shamil hain."));}catch(Exception e){runOnUiThread(()->message("Export nahi hua",e.getMessage()));}},"source-export").start();}
    }
    private void connectRea(){RuntimeService service=RuntimeService.current;if(service==null||!service.ready){message("Pehle bot start karein","Engine ready hone ke baad REA tools connect ho sakte hain.");return;}
        new AlertDialog.Builder(this).setTitle("Original REA MCP connect karein?").setMessage("REA software-analysis tools provide karta hai. Sirf apne ya authorised software par use karein. App pehle original MCP connection test karegi; tools ko chupke se permission nahi degi. Kuch decompilers/Frida jaise external engines alag prerequisites hain.").setNegativeButton("Cancel",null).setPositiveButton("Test & connect",(d,w)->{
            Toast.makeText(this,"REA connection test ho raha hai…",Toast.LENGTH_LONG).show();new Thread(()->{try{
                String origin=service.origin,cookie=service.cookieHeader(),name="terminator-rea";JSONArray listed=LocalApi.call(origin,"GET","/api/mcp/servers",null,null,cookie).body.getJSONArray("servers");JSONObject found=null;
                for(int i=0;i<listed.length();i++)if(name.equals(listed.getJSONObject(i).optString("name")))found=listed.getJSONObject(i);
                JSONArray args=new JSONArray().put("/opt/terminator/runtime/node_modules/rea-agents/scripts/rea.mjs").put("mcp");JSONObject config=new JSONObject().put("name",name).put("command","/opt/terminator/node/bin/node").put("args",args).put("enabled",false);
                if(found==null)LocalApi.call(origin,"POST","/api/mcp/servers",config,null,cookie);
                else if(!config.getString("command").equals(found.optString("command"))||!args.toString().equals(found.optJSONArray("args")==null?"":found.getJSONArray("args").toString()))throw new IOException("Is naam ka custom server pehle se hai. Original Plugins screen mein review karein.");
                JSONObject probe=LocalApi.call(origin,"POST","/api/mcp/servers/"+name+"/test",new JSONObject(),null,cookie).body;
                if(!probe.optBoolean("ok"))throw new IOException("Original MCP test pass nahi hua: "+probe.optString("error",probe.optString("reason","Diagnostics dekhein")));
                config.remove("name");config.put("enabled",true);LocalApi.call(origin,"PUT","/api/mcp/servers/"+name,config,null,cookie);
                runOnUiThread(()->message("REA connected","Original MCP test pass ho gaya. Bot ke Plugins/MCP settings mein iska access review karein. Har external tool ki availability alag hai."));
            }catch(Exception e){runOnUiThread(()->message("REA connect nahi hua",e.getMessage()));}},"rea-connect").start();
        }).show();
    }
    private void diagnostics(){RuntimeService s=RuntimeService.current;message("Local diagnostics",s==null?"Engine abhi band hai.\nPhone: "+Build.MANUFACTURER+" "+Build.MODEL+"\nAndroid "+Build.VERSION.RELEASE+"\nFull parity: NOT CERTIFIED":s.diagnostics());}
    private void assetDialog(String title,String asset){try(InputStream input=getAssets().open(asset)){message(title,new String(RuntimeInstaller.readBounded(input,256*1024),StandardCharsets.UTF_8));}catch(Exception e){message(title,e.getMessage());}}
    private void message(String title,String message){ScrollView scroll=new ScrollView(this);TextView view=text(message==null?"Unknown error":message,14,TEXT);view.setTextIsSelectable(true);view.setPadding(dp(20),dp(12),dp(20),dp(12));scroll.addView(view);new AlertDialog.Builder(this).setTitle(title).setView(scroll).setPositiveButton("OK",null).show();}
}
