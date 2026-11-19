package dev.terminator.phone;

import java.io.*;
import java.nio.ByteBuffer;
import java.nio.charset.*;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermission;
import java.util.*;

/** Bounded tar reader. No owners, setuid bits, device nodes, or writes through links.
 * All links are deferred until payload writes finish. Absolute guest links are made
 * relative inside the private root, never activated as absolute host paths. */
public final class SafeTar {
    public interface Progress { void update(long bytes, int files) throws IOException; }
    private static final long MAX_FILE = 512L * 1024 * 1024;
    private static final long MAX_TOTAL = 2L * 1024 * 1024 * 1024;
    private static final int MAX_ENTRIES = 60000;
    private static final Charset UTF8 = StandardCharsets.UTF_8;
    private SafeTar() {}

    private static final class Link {
        final String name, target; final boolean hard;
        Link(String n, String t, boolean h) { name=n; target=t; hard=h; }
    }
    public static final class Result {
        public long bytes; public int files, links, skippedSpecial;
    }

    public static Result extract(InputStream input, File destination, Progress progress) throws IOException {
        // Linux/Android only: ':' and literal backslashes are valid package filenames
        // (dpkg multiarch metadata and escaped systemd unit names), not separators.
        if (File.separatorChar != '/') throw new IOException("A POSIX filesystem is required");
        Path root = destination.toPath().toAbsolutePath().normalize();
        if (Files.isSymbolicLink(root)) throw new IOException("Destination is a symbolic link");
        Files.createDirectories(root);
        try (DirectoryStream<Path> ds = Files.newDirectoryStream(root)) {
            if (ds.iterator().hasNext()) throw new IOException("Extraction needs a fresh empty directory");
        }
        mode(root, true, true);
        Set<String> seen = new HashSet<>();
        List<Link> links = new ArrayList<>();
        Map<String,String> pax = new HashMap<>();
        String longName = null, longTarget = null;
        Result result = new Result(); int entries=0; long physical=0;
        byte[] header = new byte[512];
        for (;;) {
            if (Thread.currentThread().isInterrupted()) throw new InterruptedIOException("Cancelled");
            readFully(input, header);
            physical += 512;
            boolean zero=true; for (byte b:header) if(b!=0){ zero=false;break; }
            if (zero) break;
            if (++entries > MAX_ENTRIES) throw new IOException("Too many archive entries");
            if (physical > MAX_TOTAL + 128L*1024*1024) throw new IOException("Archive stream is too large");
            long storedChecksum = octal(header, 148, 8), checksum=0;
            for(int i=0;i<512;i++) checksum += (i>=148 && i<156) ? 32 : (header[i]&255);
            if(storedChecksum!=checksum) throw new IOException("Invalid tar checksum");
            long size=octal(header,124,12), permissions=octal(header,100,8);
            if(size<0 || size>MAX_FILE) throw new IOException("Archive file is too large");
            int type=header[156]&255;
            String name=text(header,0,100), prefix=text(header,345,155);
            if(!prefix.isEmpty() && text(header,257,6).startsWith("ustar")) name=prefix+"/"+name;
            String target=text(header,157,100);
            if(type=='x' || type=='g' || type=='L' || type=='K') {
                if(size>65536) throw new IOException("Archive metadata is too large");
                byte[] value=new byte[(int)size];readFully(input,value);padding(input,size);physical+=rounded(size);
                if(type=='x') pax=parsePax(value);
                else if(type=='g') { Map<String,String> global=parsePax(value); if(global.containsKey("path")||global.containsKey("linkpath")||global.containsKey("size")) throw new IOException("Global path overrides are not supported"); }
                else if(type=='L') longName=nulText(value);
                else longTarget=nulText(value);
                continue;
            }
            if(longName!=null) name=longName;
            if(longTarget!=null) target=longTarget;
            if(pax.containsKey("path")) name=pax.get("path");
            if(pax.containsKey("linkpath")) target=pax.get("linkpath");
            if(pax.containsKey("size")) {
                try { size=Long.parseLong(pax.get("size")); } catch(NumberFormatException e){throw new IOException("Invalid PAX size");}
                if(size<0||size>MAX_FILE) throw new IOException("Invalid PAX size");
            }
            pax.clear(); longName=null;longTarget=null;
            name=cleanName(name);
            if(name.isEmpty()) {
                if(type!='5') throw new IOException("Invalid empty archive path");
                skipFully(input,size);padding(input,size);physical+=rounded(size);continue;
            }
            Path path=inside(root,name);
            if(type=='5') {
                directories(root,path); mode(path,true,true);
            } else {
                if(!seen.add(name)) throw new IOException("Duplicate archive path: "+name);
                directories(root,path.getParent());
                if(Files.exists(path,LinkOption.NOFOLLOW_LINKS)) throw new IOException("Archive path conflicts: "+name);
                if(type==0 || type=='0') {
                    if(result.bytes+size>MAX_TOTAL) throw new IOException("Expanded archive exceeds size limit");
                    try(OutputStream out=Files.newOutputStream(path,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE)) {
                        byte[] buffer=new byte[65536];long left=size;
                        while(left>0) {
                            if(Thread.currentThread().isInterrupted()) throw new InterruptedIOException("Cancelled");
                            int n=input.read(buffer,0,(int)Math.min(buffer.length,left));
                            if(n<0) throw new EOFException("Truncated archive payload");
                            if(n==0)continue;out.write(buffer,0,n);left-=n;result.bytes+=n;
                            if(progress!=null)progress.update(result.bytes,result.files);
                        }
                    }
                    mode(path,false,(permissions&0111)!=0); result.files++;
                    padding(input,size);physical+=rounded(size);continue;
                } else if(type=='1' || type=='2') {
                    if(size!=0) throw new IOException("Link has an unexpected payload");
                    // Validate now, activate only after all regular files have been written.
                    linkDestination(root,path,target,type=='1');
                    links.add(new Link(name,target,type=='1'));
                } else if(type=='3'||type=='4'||type=='6') {
                    // Guest /dev is supplied by a narrowly scoped PRoot bind, never mknod.
                    result.skippedSpecial++;
                } else throw new IOException("Unsupported tar entry type: "+type);
            }
            skipFully(input,size);padding(input,size);physical+=rounded(size);
        }
        for(Link link:links) if(link.hard) {
            Path path=inside(root,link.name),target=linkDestination(root,path,link.target,true);
            noLinkParents(root,path.getParent());noLinkParents(root,target.getParent());
            if(!Files.isRegularFile(target,LinkOption.NOFOLLOW_LINKS)) throw new IOException("Hard link target is not a regular file");
            Files.createLink(path,target);result.links++;
        }
        for(Link link:links) if(!link.hard) {
            Path path=inside(root,link.name),target=linkDestination(root,path,link.target,false);
            noLinkParents(root,path.getParent());
            Files.createSymbolicLink(path,path.getParent().relativize(target));result.links++;
        }
        if(progress!=null)progress.update(result.bytes,result.files);
        return result;
    }

    private static Path linkDestination(Path root,Path path,String raw,boolean hard) throws IOException {
        if(raw==null||raw.isEmpty()||raw.indexOf('\0')>=0||raw.length()>4096) throw new IOException("Invalid archive link");
        Path target;
        if(hard) target=inside(root,cleanName(raw));
        else target=(raw.startsWith("/")?root.resolve(raw.substring(1)):path.getParent().resolve(raw)).normalize();
        if(!target.startsWith(root)) throw new IOException("Archive link escapes private root");
        return target;
    }
    private static String cleanName(String raw) throws IOException {
        if(raw==null||raw.length()>4096||raw.startsWith("/")||raw.indexOf('\0')>=0) throw new IOException("Unsafe archive path");
        while(raw.startsWith("./"))raw=raw.substring(2);
        while(raw.endsWith("/"))raw=raw.substring(0,raw.length()-1);
        if(raw.equals(".")||raw.isEmpty())return "";
        for(String part:raw.split("/",-1)) if(part.isEmpty()||part.equals("..")||part.equals(".")) throw new IOException("Unsafe archive path");
        return raw;
    }
    private static Path inside(Path root,String name) throws IOException {
        Path p=root.resolve(name).normalize();if(!p.startsWith(root))throw new IOException("Archive escaped private root");return p;
    }
    private static void directories(Path root,Path directory) throws IOException {
        if(directory==null||!directory.startsWith(root))throw new IOException("Invalid archive directory");
        Path cursor=root;
        for(Path part:root.relativize(directory)) {
            if(part.toString().isEmpty())continue;
            cursor=cursor.resolve(part);
            if(Files.exists(cursor,LinkOption.NOFOLLOW_LINKS)) {
                if(Files.isSymbolicLink(cursor)||!Files.isDirectory(cursor,LinkOption.NOFOLLOW_LINKS))throw new IOException("Archive parent is not a real directory");
            } else {Files.createDirectory(cursor);mode(cursor,true,true);}
        }
    }
    private static void noLinkParents(Path root,Path p) throws IOException {
        Path cursor=root;for(Path part:root.relativize(p)){cursor=cursor.resolve(part);if(Files.isSymbolicLink(cursor))throw new IOException("Archive parent is a link");}
    }
    private static void mode(Path p,boolean directory,boolean executable) throws IOException {
        Set<PosixFilePermission> perms=EnumSet.of(PosixFilePermission.OWNER_READ,PosixFilePermission.OWNER_WRITE);
        if(directory||executable)perms.add(PosixFilePermission.OWNER_EXECUTE);
        try{Files.setPosixFilePermissions(p,perms);}catch(UnsupportedOperationException e){
            File f=p.toFile();f.setReadable(false,false);f.setWritable(false,false);f.setExecutable(false,false);
            if(!f.setReadable(true,true)||!f.setWritable(true,true)||((directory||executable)&&!f.setExecutable(true,true)))throw new IOException("Cannot set private file permissions");
        }
    }
    private static String text(byte[] b,int offset,int length) throws IOException {
        int end=offset;while(end<offset+length&&b[end]!=0)end++;
        try{return UTF8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(b,offset,end-offset)).toString();}
        catch(CharacterCodingException e){throw new IOException("Invalid UTF-8 archive name",e);}
    }
    private static String nulText(byte[] b) throws IOException {return text(b,0,b.length);}
    private static long octal(byte[] b,int offset,int length) throws IOException {
        if((b[offset]&128)!=0)throw new IOException("Unsupported base-256 tar number");
        long value=0;boolean ended=false;
        for(int i=offset;i<offset+length;i++) {
            int c=b[i]&255;
            if(c==0||c==32){if(value>0)ended=true;continue;}
            if(c<'0'||c>'7'||ended||value>(Long.MAX_VALUE>>3))throw new IOException("Invalid tar number");
            value=(value<<3)+(c-'0');
        }
        return value;
    }
    private static Map<String,String> parsePax(byte[] data) throws IOException {
        Map<String,String> out=new HashMap<>();int at=0;
        while(at<data.length){
            int space=at;while(space<data.length&&data[space]!=' ')space++;
            if(space==data.length)throw new IOException("Invalid PAX record");
            int length;try{length=Integer.parseInt(new String(data,at,space-at,StandardCharsets.US_ASCII));}catch(NumberFormatException e){throw new IOException("Invalid PAX length");}
            if(length<=space-at+2||length>data.length-at||data[at+length-1]!='\n')throw new IOException("Invalid PAX length");
            String row=text(data,space+1,at+length-space-2);int equals=row.indexOf('=');
            if(equals<1)throw new IOException("Invalid PAX key");out.put(row.substring(0,equals),row.substring(equals+1));at+=length;
        }
        return out;
    }
    private static void readFully(InputStream in,byte[] b) throws IOException {
        int at=0;while(at<b.length){int n=in.read(b,at,b.length-at);if(n<0)throw new EOFException("Truncated tar header");if(n>0)at+=n;}
    }
    private static long rounded(long size){return size+((512-size%512)%512);}
    private static void padding(InputStream in,long size)throws IOException{skipFully(in,(512-size%512)%512);}
    private static void skipFully(InputStream in,long left)throws IOException{
        byte[] scratch=new byte[8192];while(left>0){int n=in.read(scratch,0,(int)Math.min(left,scratch.length));if(n<0)throw new EOFException("Truncated archive");if(n>0)left-=n;}
    }
}
