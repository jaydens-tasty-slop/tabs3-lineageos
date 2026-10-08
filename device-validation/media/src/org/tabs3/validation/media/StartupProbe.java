package org.tabs3.validation.media;

import android.os.Process;
import android.os.SystemClock;
import android.util.Log;
import org.json.JSONObject;
import java.io.BufferedReader;
import java.io.FileReader;

/** No Activity or user storage: graphics/codec inventory before first unlock. */
public final class StartupProbe {
    public static void main(String[] args) throws Exception {
        JSONObject report=new JSONObject();long start=SystemClock.elapsedRealtime();
        try {
            if(Process.myUid()!=2000)throw new IllegalStateException("Startup probe must run as shell UID 2000, never root");
            JSONObject caps=new JSONObject();try(BufferedReader reader=new BufferedReader(new FileReader("/proc/self/status"))){String line;
                while((line=reader.readLine())!=null)if(line.startsWith("CapEff:")||line.startsWith("CapPrm:")||line.startsWith("CapAmb:")){
                    String[] parts=line.split(":",2);String value=parts[1].trim();caps.put(parts[0],value);
                    if(!value.matches("0+"))throw new IllegalStateException("Unexpected process capabilities "+line);
                }}
            if(args.length<1)throw new IllegalArgumentException("Specify a startup diagnostic");
            report=MainActivity.startupProbe(args);
            report.put("process_capabilities",caps);
        } catch(Throwable error){report.put("passed",false);report.put("error",Log.getStackTraceString(error));}
        report.put("uid",Process.myUid());report.put("elapsed_ms",SystemClock.elapsedRealtime()-start);
        report.put("scope","Shell UID graphics/media startup check. No Activity, microphone, camera, user unlock or personal storage access. Only generated diagnostic files.");
        System.out.println("TAB_S3_STARTUP_REPORT "+report.toString());
        System.exit(report.optBoolean("passed")?0:1);
    }
}
