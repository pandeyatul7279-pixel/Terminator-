import dev.terminator.phone.SafeTar;
import java.io.*;
import java.util.zip.GZIPInputStream;
import org.tukaani.xz.XZInputStream;

/** Host test harness for the exact Java extractor shipped in the APK. */
public final class SafeTarHarness {
    public static void main(String[] args) throws Exception {
        try(InputStream raw=new BufferedInputStream(new FileInputStream(args[0]));
            InputStream in=args[2].equals("xz")?new XZInputStream(raw,131072):args[2].equals("gz")?new GZIPInputStream(raw):raw){
            SafeTar.Result r=SafeTar.extract(in,new File(args[1]),null);
            System.out.println("files="+r.files+" bytes="+r.bytes+" links="+r.links+" skipped="+r.skippedSpecial);
        }
    }
}
