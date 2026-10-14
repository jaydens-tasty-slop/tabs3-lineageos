package org.tabs3.validation.cameracontrols;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.graphics.ImageFormat;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.hardware.*;
import android.hardware.camera2.*;
import android.hardware.camera2.params.StreamConfigurationMap;
import android.media.*;
import android.os.*;
import android.util.*;
import android.view.*;
import android.widget.TextView;
import org.json.*;
import java.io.*;
import java.nio.*;
import java.security.MessageDigest;
import java.util.*;

/** Ordinary Camera2 lifecycle controls. No photographs are saved or exported. */
public final class MainActivity extends Activity {
    private volatile boolean resumed;
    private String output;
    private TextView view;
    @Override public void onResume(){super.onResume();resumed=true;}
    @Override public void onPause(){resumed=false;super.onPause();}
    @Override public void onCreate(Bundle saved){
        super.onCreate(saved);getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        view=new TextView(this);view.setText("Running ordinary Camera2 lifecycle control…");setContentView(view);
        Intent intent=getIntent();output=intent.getStringExtra("output");
        if(output==null || !output.matches("[a-zA-Z0-9_-]{1,80}\\.json"))output="result.json";
        new Thread(()->{
            JSONObject result=new JSONObject();JSONArray runs=new JSONArray();long started=SystemClock.elapsedRealtime();
            try{
                long deadline=started+10000;while(!resumed && SystemClock.elapsedRealtime()<deadline)Thread.sleep(50);
                if(!resumed)throw new IllegalStateException("Activity is not in foreground");
                result.put("client_uid",android.os.Process.myUid());result.put("client_pid",android.os.Process.myPid());
                result.put("activity_resumed_at_start",resumed);
                String choice=intent.getStringExtra("capture_choice"),mode=intent.getStringExtra("close_mode"),id=intent.getStringExtra("camera_id");
                if(!"preview".equals(choice) && !"jpeg".equals(choice) && !"jpeg_idle".equals(choice))throw new IllegalArgumentException("capture_choice must be preview, jpeg or jpeg_idle");
                if(!"direct".equals(mode) && !"drain".equals(mode))throw new IllegalArgumentException("close_mode must be direct or drain");
                if(!"0".equals(id) && !"1".equals(id) && !"both".equals(id))throw new IllegalArgumentException("camera_id must be0,1 or both");
                int cycles=intent.getIntExtra("cycles",1);if(cycles<1 || cycles>3)throw new IllegalArgumentException("cycles must be1 through3");
                result.put("capture_choice",choice);result.put("close_mode",mode);result.put("camera_id",id);
                boolean okay=true;
                for(int cycle=0;cycle<cycles;cycle++){
                    if(!resumed)throw new IllegalStateException("Activity left foreground");
                    JSONObject run=new JSONObject().put("cycle",cycle+1);
                    camera(this,run,"both".equals(id)?null:id,"jpeg".equals(choice),!"preview".equals(choice),"drain".equals(mode));
                    runs.put(run);okay &= run.optBoolean("passed");Thread.sleep(1500);
                }
                result.put("passed",okay);
            }catch(Throwable error){try{result.put("passed",false);result.put("error",Log.getStackTraceString(error));}catch(Exception ignored){}}
            try{
                result.put("session_cycles",runs);result.put("elapsed_ms",SystemClock.elapsedRealtime()-started);
                result.put("limits","Ordinary Camera2 API controls only; no photographs saved/exported or production ROM changes.");
                File partial=new File(getFilesDir(),output+".partial");try(FileOutputStream file=new FileOutputStream(partial)){file.write(result.toString(2).getBytes("UTF-8"));file.getFD().sync();}
                if(!partial.renameTo(new File(getFilesDir(),output)))throw new IOException("Report rename failed");
                runOnUiThread(()->view.setText(result.toString()));
            }catch(Exception error){Log.e("TabS3CameraControl","Report failure",error);}
        },"camera-control").start();
    }

    private static void waitFor(Object lock,java.util.function.BooleanSupplier ready,long timeout)throws Exception {
        long deadline=SystemClock.elapsedRealtime()+timeout;synchronized(lock){while(!ready.getAsBoolean()){long left=deadline-SystemClock.elapsedRealtime();if(left<=0)throw new IllegalStateException("Camera callback timeout");lock.wait(left);}}
    }
    private static Size size(Size[] choices,int maxPixels){
        Size selected=null;for(Size s:choices)if(s.getWidth()*s.getHeight()<=maxPixels && (selected==null || s.getWidth()*s.getHeight()>selected.getWidth()*selected.getHeight()))selected=s;
        return selected==null?choices[0]:selected;
    }
    static void camera(Context context,JSONObject result,String selectedId,boolean stills,boolean jpegOutput,boolean drain)throws Exception {
        CameraManager manager=(CameraManager)context.getSystemService(CAMERA_SERVICE);String[] ids=manager.getCameraIdList();result.put("camera_ids",new JSONArray(ids));
        JSONArray tests=new JSONArray();boolean all=selectedId==null?ids.length==2:Arrays.asList(ids).contains(selectedId);
        for(String id:ids){
            if(selectedId!=null && !selectedId.equals(id))continue;
            JSONObject test=new JSONObject().put("id",id);HandlerThread thread=new HandlerThread("camera-"+id);thread.start();Handler handler=new Handler(thread.getLooper());
            final Object lock=new Object();final CameraDevice[] device={null};final CameraCaptureSession[] session={null};final String[] error={null};final int[] previews={0},jpegs={0};final JSONArray jpegStats=new JSONArray();final boolean[] jpegValid={true};final JSONObject[] planeLayout={null};
            final JSONArray callbacks=new JSONArray();final boolean[] deviceClosed={false},sessionClosed={false},ready={false};final int[] stillCompleted={0};
            ImageReader yuv=null,jpeg=null;
            try {
                CameraCharacteristics c=manager.getCameraCharacteristics(id);StreamConfigurationMap map=c.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP);
                test.put("lens_facing",c.get(CameraCharacteristics.LENS_FACING));test.put("hardware_level",c.get(CameraCharacteristics.INFO_SUPPORTED_HARDWARE_LEVEL));
                Size ps=size(map.getOutputSizes(ImageFormat.YUV_420_888),640*480),js=jpegOutput?size(map.getOutputSizes(ImageFormat.JPEG),1920*1080):ps;
                test.put("preview_size",ps.toString());test.put("capture_choice",stills?"jpeg":(jpegOutput?"jpeg_idle":"preview"));test.put("jpeg_configured_without_still_requests",jpegOutput && !stills);test.put("close_mode",drain?"drain":"direct");if(jpegOutput)test.put("jpeg_size",js.toString());
                yuv=ImageReader.newInstance(ps.getWidth(),ps.getHeight(),ImageFormat.YUV_420_888,3);if(jpegOutput)jpeg=ImageReader.newInstance(js.getWidth(),js.getHeight(),ImageFormat.JPEG,3);
                yuv.setOnImageAvailableListener(reader->{try(Image image=reader.acquireNextImage()){if(image!=null){synchronized(lock){
                    if(planeLayout[0]==null){JSONArray planes=new JSONArray();Image.Plane[] entries=image.getPlanes();boolean bounds=entries.length==3;
                        for(int p=0;p<entries.length;p++){Image.Plane entry=entries[p];int w=p==0?image.getWidth():(image.getWidth()+1)/2,h=p==0?image.getHeight():(image.getHeight()+1)/2;
                            long needed=(long)(h-1)*entry.getRowStride()+(long)(w-1)*entry.getPixelStride()+1;boolean fits=needed<=entry.getBuffer().remaining();bounds &= fits;
                            planes.put(new JSONObject().put("row_stride",entry.getRowStride()).put("pixel_stride",entry.getPixelStride()).put("buffer_bytes",entry.getBuffer().remaining()).put("visible_pixels_fit",fits));}
                        planeLayout[0]=new JSONObject().put("width",image.getWidth()).put("height",image.getHeight()).put("format",image.getFormat()).put("planes",planes).put("visible_pixels_fit",bounds);
                        if(!bounds)error[0]="YUV visible pixels exceed plane buffers";
                    }
                    previews[0]++;lock.notifyAll();}}}catch(Exception e){synchronized(lock){error[0]=e.toString();lock.notifyAll();}}},handler);
                if(jpegOutput)jpeg.setOnImageAvailableListener(reader->{try(Image image=reader.acquireNextImage()){if(image!=null){ByteBuffer b=image.getPlanes()[0].getBuffer();byte[] bytes=new byte[b.remaining()];b.get(bytes);MessageDigest md=MessageDigest.getInstance("SHA-256");byte[] hash=md.digest(bytes);StringBuilder hex=new StringBuilder();for(byte value:hash)hex.append(String.format("%02x",value&255));boolean markers=bytes.length>4 && (bytes[0]&255)==255 && (bytes[1]&255)==216 && (bytes[bytes.length-2]&255)==255 && (bytes[bytes.length-1]&255)==217;
                    Bitmap bitmap=BitmapFactory.decodeByteArray(bytes,0,bytes.length);int width=bitmap==null?0:bitmap.getWidth(),height=bitmap==null?0:bitmap.getHeight();if(bitmap!=null)bitmap.recycle();boolean decoded=width==js.getWidth() && height==js.getHeight();
                    synchronized(lock){jpegValid[0] &= markers && decoded;jpegStats.put(new JSONObject().put("bytes",bytes.length).put("sha256",hex.toString()).put("jpeg_markers",markers).put("decoded_width",width).put("decoded_height",height).put("decoded_dimensions_match",decoded));jpegs[0]++;lock.notifyAll();}}}catch(Exception e){synchronized(lock){error[0]=e.toString();lock.notifyAll();}}},handler);
                manager.openCamera(id,new CameraDevice.StateCallback(){
                    @Override public void onOpened(CameraDevice camera){synchronized(lock){cameraEvent(callbacks,"device_opened",id);device[0]=camera;lock.notifyAll();}}
                    @Override public void onDisconnected(CameraDevice camera){synchronized(lock){cameraEvent(callbacks,"device_disconnected",id);error[0]="Camera disconnected";lock.notifyAll();}camera.close();}
                    @Override public void onError(CameraDevice camera,int code){synchronized(lock){cameraEvent(callbacks,"device_error_"+code,id);error[0]="Camera error "+code;lock.notifyAll();}camera.close();}
                    @Override public void onClosed(CameraDevice camera){synchronized(lock){cameraEvent(callbacks,"device_closed",id);deviceClosed[0]=true;lock.notifyAll();}}
                },handler);
                waitFor(lock,()->device[0]!=null || error[0]!=null,15000);if(error[0]!=null)throw new IllegalStateException(error[0]);
                device[0].createCaptureSession(jpegOutput?Arrays.asList(yuv.getSurface(),jpeg.getSurface()):Collections.singletonList(yuv.getSurface()),new CameraCaptureSession.StateCallback(){
                    @Override public void onConfigured(CameraCaptureSession s){synchronized(lock){cameraEvent(callbacks,"session_configured",id);session[0]=s;lock.notifyAll();}}
                    @Override public void onConfigureFailed(CameraCaptureSession s){synchronized(lock){cameraEvent(callbacks,"session_configure_failed",id);error[0]="Session configuration failed";lock.notifyAll();}}
                    @Override public void onClosed(CameraCaptureSession s){synchronized(lock){cameraEvent(callbacks,"session_closed",id);sessionClosed[0]=true;lock.notifyAll();}}
                    @Override public void onReady(CameraCaptureSession s){synchronized(lock){cameraEvent(callbacks,"session_ready",id);ready[0]=true;lock.notifyAll();}}
                    @Override public void onActive(CameraCaptureSession s){synchronized(lock){cameraEvent(callbacks,"session_active",id);ready[0]=false;lock.notifyAll();}}
                },handler);
                waitFor(lock,()->session[0]!=null || error[0]!=null,15000);if(error[0]!=null)throw new IllegalStateException(error[0]);
                CaptureRequest.Builder preview=device[0].createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW);preview.addTarget(yuv.getSurface());session[0].setRepeatingRequest(preview.build(),null,handler);
                waitFor(lock,()->previews[0]>=10 || error[0]!=null,15000);if(error[0]!=null)throw new IllegalStateException(error[0]);
                for(int i=0;stills && i<3;i++){
                    int goal=i+1;CaptureRequest.Builder capture=device[0].createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE);capture.addTarget(jpeg.getSurface());
                    session[0].capture(capture.build(),new CameraCaptureSession.CaptureCallback(){@Override public void onCaptureCompleted(CameraCaptureSession s,CaptureRequest r,TotalCaptureResult completed){synchronized(lock){stillCompleted[0]++;cameraEvent(callbacks,"still_capture_completed",id);lock.notifyAll();}}@Override public void onCaptureFailed(CameraCaptureSession s,CaptureRequest r,CaptureFailure fail){synchronized(lock){error[0]="Still capture failed "+fail.getReason();lock.notifyAll();}}},handler);
                    waitFor(lock,()->jpegs[0]>=goal || error[0]!=null,15000);if(error[0]!=null)throw new IllegalStateException(error[0]);
                }
                if(drain && stills){waitFor(lock,()->stillCompleted[0]==3 || error[0]!=null,15000);if(error[0]!=null)throw new IllegalStateException(error[0]);}
                test.put("capture_passed",previews[0]>=10 && (stills?(jpegs[0]==3 && jpegValid[0]):jpegs[0]==0));
                test.put("passed",test.getBoolean("capture_passed"));all &= test.getBoolean("passed");
            }catch(Throwable e){test.put("passed",false);test.put("error",Log.getStackTraceString(e));all=false;}
            finally{
                synchronized(lock){cameraEvent(callbacks,"close_requested",id);}
                if(session[0]!=null){
                    try{
                        synchronized(lock){if(drain)ready[0]=false;cameraEvent(callbacks,"stop_repeating_requested",id);}
                        session[0].stopRepeating();
                        if(drain){waitFor(lock,()->ready[0] || error[0]!=null,15000);if(error[0]!=null)throw new IllegalStateException(error[0]);test.put("ready_before_close",true);}
                    }catch(Exception closeError){test.put("stop_repeating_error",closeError.toString());test.put("passed",false);all=false;}
                    session[0].close();
                    if(drain){try{waitFor(lock,()->sessionClosed[0] || error[0]!=null,10000);if(error[0]!=null)throw new IllegalStateException(error[0]);}catch(Exception closeError){test.put("session_close_error",closeError.toString());test.put("passed",false);all=false;}}
                }
                if(device[0]!=null){device[0].close();try{waitFor(lock,()->deviceClosed[0],10000);}catch(Exception closeError){test.put("close_error",closeError.toString());test.put("passed",false);all=false;}}
                if(yuv!=null)yuv.close();if(jpeg!=null)jpeg.close();thread.quitSafely();thread.join(2000);
            }
            test.put("device_closed_callback",deviceClosed[0]);test.put("session_closed_callback",sessionClosed[0]);test.put("callbacks",callbacks);
            test.put("preview_frames",previews[0]);test.put("yuv_plane_layout",planeLayout[0]);test.put("jpeg_frames",jpegs[0]);test.put("still_capture_completed_callbacks",stillCompleted[0]);test.put("jpeg_statistics",jpegStats);tests.put(test);
            Thread.sleep(1500);
        }
        result.put("tests",tests);result.put("passed",all);
    }
    private static void cameraEvent(JSONArray events,String event,String id){
        if(events.length()>=128)return;
        try{events.put(new JSONObject().put("event",event).put("camera_id",id).put("elapsed_realtime_ms",SystemClock.elapsedRealtime()));}catch(JSONException ignored){}
    }
}
