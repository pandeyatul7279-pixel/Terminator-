package dev.terminator.phone;

import org.json.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Native-only access to the original local API. Never follows redirects or logs credentials. */
final class LocalApi {
    static final class Reply { JSONObject body; List<String> cookies=new ArrayList<>(); }
    static Reply call(String origin,String method,String path,JSONObject body,String owner,String cookie)throws Exception{
        URI base=new URI(origin);
        if(!"http".equals(base.getScheme())||!"127.0.0.1".equals(base.getHost())||base.getPort()<1024||base.getUserInfo()!=null||!path.startsWith("/api/")||path.contains(".."))throw new IOException("Non-local API request refused");
        HttpURLConnection c=(HttpURLConnection)new URL(origin+path).openConnection();
        try{
            c.setInstanceFollowRedirects(false);c.setConnectTimeout(2000);c.setReadTimeout(60000);c.setRequestMethod(method);
            c.setRequestProperty("User-Agent","Terminator-Android/0.2.0");
            if(owner!=null)c.setRequestProperty("x-openmausbot-cli-owner",owner);
            if(cookie!=null)c.setRequestProperty("Cookie",cookie);
            // The CLI bootstrap uses the private capability, never a spoofed browser marker.
            if(owner==null)c.setRequestProperty("Origin",origin);
            if(body!=null){c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");byte[] data=body.toString().getBytes(StandardCharsets.UTF_8);c.setFixedLengthStreamingMode(data.length);try(OutputStream out=c.getOutputStream()){out.write(data);}}
            int status=c.getResponseCode();
            if(status!=200&&status!=201)throw new IOException("Original server API refused "+path+" (HTTP "+status+")");
            Reply reply=new Reply();try(InputStream in=c.getInputStream()){reply.body=new JSONObject(new String(RuntimeInstaller.readBounded(in,2*1024*1024),StandardCharsets.UTF_8));}
            for(Map.Entry<String,List<String>> h:c.getHeaderFields().entrySet())if(h.getKey()!=null&&h.getKey().equalsIgnoreCase("Set-Cookie"))reply.cookies.addAll(h.getValue());
            return reply;
        }finally{c.disconnect();}
    }
    static String cookieHeader(List<String> cookies){StringBuilder out=new StringBuilder();for(String one:cookies){if(out.length()>0)out.append("; ");out.append(one.split(";",2)[0]);}return out.toString();}
}
