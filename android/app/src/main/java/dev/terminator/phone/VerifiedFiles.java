package dev.terminator.phone;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.nio.file.attribute.PosixFilePermission;
import java.security.*;
import java.util.*;

/** Exact-length, hash-pinned asset copies. Failed/cancelled imports never replace a final file. */
final class VerifiedFiles {
    interface Source { InputStream open()throws Exception; }
    private VerifiedFiles(){}
    static boolean matches(File file,String expected,long bytes)throws Exception {
        if(Files.isSymbolicLink(file.toPath())||!file.isFile()||file.length()!=bytes)return false;
        MessageDigest digest=MessageDigest.getInstance("SHA-256");
        try(InputStream in=Files.newInputStream(file.toPath(),StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)) {
            long received=0;byte[] buffer=new byte[65536];for(int n;(n=in.read(buffer))!=-1;) {
                if(Thread.currentThread().isInterrupted())throw new InterruptedIOException("Cancelled");
                if(n>bytes-received)return false;
                received+=n;digest.update(buffer,0,n);
            }
            if(received!=bytes)return false;
        }
        return MessageDigest.isEqual(hex(digest.digest()).getBytes(StandardCharsets.US_ASCII),expected.getBytes(StandardCharsets.US_ASCII));
    }
    static void importAsset(Source source,File file,String expected,long bytes)throws Exception {
        if(bytes<0)throw new IOException("Invalid pinned asset size");
        if(matches(file,expected,bytes))return;
        Path target=file.toPath(),parent=target.toAbsolutePath().getParent();
        if(Files.isSymbolicLink(parent)||!Files.isDirectory(parent,LinkOption.NOFOLLOW_LINKS))throw new IOException("Asset parent is not a real private directory");
        Path partial=target.resolveSibling(target.getFileName().toString()+".part");Files.deleteIfExists(partial);
        try {
            try(InputStream in=source.open();OutputStream out=Files.newOutputStream(partial,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE)) {copy(in,out,bytes);}
            Files.setPosixFilePermissions(partial,EnumSet.of(PosixFilePermission.OWNER_READ,PosixFilePermission.OWNER_WRITE));
            if(!matches(partial.toFile(),expected,bytes))throw new IOException("Copied original asset checksum/length failed: "+file.getName());
            Files.move(partial,target,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
        } finally {Files.deleteIfExists(partial);}
    }
    static String hex(byte[] bytes) {
        StringBuilder s=new StringBuilder();for(byte b:bytes)s.append(String.format(Locale.ROOT,"%02x",b&255));return s.toString();
    }
    static void copy(InputStream in,OutputStream out,long max)throws IOException {
        long total=0;byte[] buffer=new byte[65536];for(int n;(n=in.read(buffer))!=-1;) {
            if(Thread.currentThread().isInterrupted())throw new InterruptedIOException("Cancelled");
            if(n>max-total)throw new IOException("File size limit exceeded");
            total+=n;out.write(buffer,0,n);
        }
        if(Thread.currentThread().isInterrupted())throw new InterruptedIOException("Cancelled");
    }
}
