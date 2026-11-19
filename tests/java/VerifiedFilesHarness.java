package dev.terminator.phone;

import java.io.*;

/** Exercises the production asset importer, without Android services or network. */
public final class VerifiedFilesHarness {
    public static void main(String[] args)throws Exception {
        File input=new File(args[0]),target=new File(args[1]);String mode=args[2],hash=args[3];long bytes=Long.parseLong(args[4]);
        if(mode.equals("cancel"))Thread.currentThread().interrupt();
        VerifiedFiles.importAsset(()->{
            if(mode.equals("cached"))throw new AssertionError("Verified cached asset must not reopen the original APK");
            if(mode.equals("disconnect"))return new InputStream(){
                int read;
                @Override public int read()throws IOException {if(read++<2)return 'x';throw new IOException("Fixture disconnected");}
            };
            return new FileInputStream(input);
        },target,hash,bytes);
        if(!VerifiedFiles.matches(target,hash,bytes))throw new AssertionError("Import returned without exact verification");
        System.out.println("Verified complete original asset");
    }
}
