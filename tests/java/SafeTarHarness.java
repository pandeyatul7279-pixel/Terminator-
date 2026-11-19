package dev.terminator.phone;

import java.io.*;
import java.nio.file.*;
import java.util.zip.GZIPInputStream;
import org.tukaani.xz.XZInputStream;

/** Host test harness for the exact Java extractor shipped in the APK. */
public final class SafeTarHarness {
    public static void main(String[] args) throws Exception {
        try(InputStream raw=new BufferedInputStream(new FileInputStream(args[0]));
            InputStream in=args[2].equals("xz")?new XZInputStream(raw,131072):args[2].equals("gz")?new GZIPInputStream(raw):raw){
            SafeTar.Result r;
            if(args.length>3) {
                final String mode=args[3];
                r=SafeTar.extract(in,new File(args[1]),null,(link,existing)->{
                    if(mode.equals("unsupported"))throw new UnsupportedOperationException("Fixture Android provider");
                    if(mode.equals("conflict"))Files.write(link,"keep".getBytes("UTF-8"),StandardOpenOption.CREATE_NEW);
                    if(mode.equals("oversize"))try(RandomAccessFile file=new RandomAccessFile(existing.toFile(),"rw")){file.setLength(512L*1024*1024+1);}
                    // No reason string, matching the opaque path -> target UI report.
                    throw new FileSystemException(link.toString(),existing.toString(),null);
                });
            } else r=SafeTar.extract(in,new File(args[1]),null);
            System.out.println("files="+r.files+" bytes="+r.bytes+" links="+r.links+" skipped="+r.skippedSpecial+" copiedHardLinks="+r.copiedHardLinks);
        }
    }
}
