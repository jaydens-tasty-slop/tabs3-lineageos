package org.tabs3.validation.io;

import android.content.Context;
import android.os.Looper;
import android.os.Process;
import android.os.SystemClock;
import android.util.Log;
import java.io.BufferedReader;
import java.io.FileReader;
import org.json.JSONObject;

/** Camera-service crash reproducer as the authorized ADB shell, with no Activity or saved media. */
public final class StartupCamera {
    public static void main(String[] args) throws Exception {
        JSONObject report=new JSONObject();long started=SystemClock.elapsedRealtime();
        try {
            if(Process.myUid()!=2000)throw new IllegalStateException("Camera reproducer requires shell UID 2000");
            JSONObject caps=new JSONObject();
            try(BufferedReader reader=new BufferedReader(new FileReader("/proc/self/status"))){String line;
                while((line=reader.readLine())!=null)if(line.startsWith("CapEff:")||line.startsWith("CapPrm:")||line.startsWith("CapAmb:")){
                    String[] fields=line.split(":",2);String value=fields[1].trim();caps.put(fields[0],value);
                    if(!value.matches("0+"))throw new IllegalStateException("Unexpected process capabilities "+line);
                }
            }
            report.put("process_capabilities",caps);
            if(args.length!=1 || !("0".equals(args[0])||"1".equals(args[0])))throw new IllegalArgumentException("One camera ID, 0 or 1, required");
            System.out.println("TAB_S3_CAMERA_RUNNER pid="+Process.myPid());
            Looper.prepareMainLooper();
            Class<?> activityThread=Class.forName("android.app.ActivityThread");
            Object thread=activityThread.getMethod("systemMain").invoke(null);
            Context system=(Context)activityThread.getMethod("getSystemContext").invoke(thread);
            Context shell=system.createPackageContext("com.android.shell",0);
            report.put("attribution_package",shell.getOpPackageName());
            if(!"com.android.shell".equals(shell.getOpPackageName()))throw new IllegalStateException("Unexpected shell attribution");
            MainActivity.camera(shell,report,args[0]);
        } catch(Throwable error){report.put("passed",false);report.put("error",Log.getStackTraceString(error));}
        report.put("uid",Process.myUid());report.put("elapsed_ms",SystemClock.elapsedRealtime()-started);
        report.put("scope","Authorized ADB shell camera-service reproducer, with zero capabilities. No Activity, saved media, personal storage or user unlock. Ordinary foreground app behavior requires its separate test.");
        System.out.println("TAB_S3_CAMERA_REPORT "+report.toString());
        System.exit(report.optBoolean("passed")?0:1);
    }
}
