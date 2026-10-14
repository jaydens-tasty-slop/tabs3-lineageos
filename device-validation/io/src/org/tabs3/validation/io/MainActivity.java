package org.tabs3.validation.io;

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

/** Bounded probes. No photographs or recorded audio are saved or exported. */
public final class MainActivity extends Activity {
    private String output;
    private TextView view;
    private volatile boolean resumed;
    @Override public void onResume(){super.onResume();resumed=true;}
    @Override public void onPause(){resumed=false;super.onPause();}
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        view=new TextView(this);view.setText("Running Tab S3 I/O diagnostic…");setContentView(view);
        Intent intent=getIntent();output=intent.getStringExtra("output");
        if(output==null || !output.matches("[a-zA-Z0-9_-]{1,80}\\.json"))output="result.json";
        new Thread(()->{
            JSONObject result=new JSONObject();long started=SystemClock.elapsedRealtime();
            try {
                long resumeDeadline=SystemClock.elapsedRealtime()+10000;
                while(!resumed && SystemClock.elapsedRealtime()<resumeDeadline)Thread.sleep(50);
                if(!resumed)throw new IllegalStateException("Diagnostic activity is not in the foreground");
                result.put("activity_resumed_at_start",resumed);
                String command=intent.getStringExtra("command");result.put("command",command);
                if("audio".equals(command))audio(result);
                else if("sensors".equals(command))sensors(result);
                else if("camera".equals(command))camera(this,result,null);
                else if("camera_sessions".equals(command)){
                    result.put("client_uid",android.os.Process.myUid());result.put("client_pid",android.os.Process.myPid());
                    int cycles=intent.getIntExtra("cycles",1);
                    if(cycles<1 || cycles>3)throw new IllegalArgumentException("Camera session cycles must be1 through3");
                    JSONArray runs=new JSONArray();boolean okay=true;
                    for(int cycle=0;cycle<cycles;cycle++){
                        if(!resumed)throw new IllegalStateException("Camera diagnostic activity left the foreground");
                        JSONObject run=new JSONObject().put("cycle",cycle+1);camera(this,run,null);
                        runs.put(run);okay &= run.optBoolean("passed");Thread.sleep(1500);
                    }
                    result.put("session_cycles",runs);result.put("passed",okay);
                }
                else throw new IllegalArgumentException("Unknown command");
            }catch(Throwable error){try{result.put("passed",false);result.put("error",Log.getStackTraceString(error));}catch(Exception ignored){}}
            try{result.put("elapsed_ms",SystemClock.elapsedRealtime()-started);
                result.put("limits","No microphone PCM or photographs are saved. Counters/statistics describe this run only.");
                File partial=new File(getFilesDir(),output+".partial");try(FileOutputStream f=new FileOutputStream(partial)){f.write(result.toString(2).getBytes("UTF-8"));f.getFD().sync();}
                if(!partial.renameTo(new File(getFilesDir(),output)))throw new IOException("Report rename failed");
                Log.i("TabS3IoProbe","REPORT "+output+" passed="+result.optBoolean("passed"));
                runOnUiThread(()->view.setText(result.toString()));
            }catch(Exception error){Log.e("TabS3IoProbe","Report failure",error);}
        },"io-probe").start();
    }

    private void audio(JSONObject result)throws Exception {
        AudioManager manager=(AudioManager)getSystemService(AUDIO_SERVICE);
        JSONArray devices=new JSONArray();for(AudioDeviceInfo d:manager.getDevices(AudioManager.GET_DEVICES_ALL))
            devices.put(new JSONObject().put("type",d.getType()).put("source",d.isSource()).put("sink",d.isSink()).put("channels",new JSONArray(d.getChannelCounts())).put("sample_rates",new JSONArray(d.getSampleRates())).put("encodings",new JSONArray(d.getEncodings())));
        result.put("devices",devices);
        AudioAttributes attrs=new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build();
        JSONArray offload=new JSONArray();
        for(int encoding:new int[]{AudioFormat.ENCODING_AAC_LC,AudioFormat.ENCODING_AAC_HE_V1,AudioFormat.ENCODING_AAC_HE_V2,AudioFormat.ENCODING_MP3,AudioFormat.ENCODING_OPUS,AudioFormat.ENCODING_AC3}){
            AudioFormat format=new AudioFormat.Builder().setSampleRate(48000).setChannelMask(AudioFormat.CHANNEL_OUT_STEREO).setEncoding(encoding).build();
            offload.put(new JSONObject().put("encoding",encoding).put("direct_support_flags",AudioManager.getDirectPlaybackSupport(format,attrs)).put("offload_supported",AudioManager.isOffloadedPlaybackSupported(format,attrs)));
        }
        result.put("compressed_playback_capabilities",offload);
        result.put("offload_limits","Capability queries only. A positive flag needs actual compressed AudioTrack/DSP playback before a hardware offload pass.");
        JSONArray inputs=new JSONArray();boolean all=true;int oldMode=manager.getMode();
        try {
            // Recorder's HighQualityRecorder uses DEFAULT, 44.1 kHz, stereo PCM16.
            // Exercise its actual opening parameters without saving microphone content.
            int[][] requests={{MediaRecorder.AudioSource.MIC,48000,AudioFormat.CHANNEL_IN_MONO},
                {MediaRecorder.AudioSource.CAMCORDER,48000,AudioFormat.CHANNEL_IN_MONO},
                {MediaRecorder.AudioSource.VOICE_RECOGNITION,48000,AudioFormat.CHANNEL_IN_MONO},
                {MediaRecorder.AudioSource.VOICE_COMMUNICATION,48000,AudioFormat.CHANNEL_IN_MONO},
                {MediaRecorder.AudioSource.DEFAULT,44100,AudioFormat.CHANNEL_IN_STEREO}};
            for(int[] request:requests){
                int source=request[0],rate=request[1],channelMask=request[2];
                int channels=channelMask==AudioFormat.CHANNEL_IN_STEREO?2:1;
                JSONObject test=new JSONObject().put("source",source).put("sample_rate",rate)
                    .put("channel_count",channels).put("recorder_high_quality_parameters",source==MediaRecorder.AudioSource.DEFAULT);
                AudioRecord record=null;
                try {
                    manager.setMode(source==MediaRecorder.AudioSource.VOICE_COMMUNICATION?AudioManager.MODE_IN_COMMUNICATION:AudioManager.MODE_NORMAL);
                    int min=AudioRecord.getMinBufferSize(rate,channelMask,AudioFormat.ENCODING_PCM_16BIT);
                    test.put("min_buffer_bytes",min);if(min<=0)throw new IllegalStateException("Invalid minimum input buffer "+min);
                    int requestedBuffer=source==MediaRecorder.AudioSource.DEFAULT?min:Math.max(min*2,8192);
                    test.put("requested_buffer_bytes",requestedBuffer);
                    record=new AudioRecord(source,rate,channelMask,AudioFormat.ENCODING_PCM_16BIT,requestedBuffer);
                    test.put("state",record.getState());if(record.getState()!=AudioRecord.STATE_INITIALIZED)throw new IllegalStateException("AudioRecord not initialized");
                    record.startRecording();test.put("recording_state",record.getRecordingState());
                    short[] buffer=new short[2048];long samples=0;double energy=0;int peak=0,empty=0;long start=SystemClock.elapsedRealtime();
                    while(SystemClock.elapsedRealtime()-start<2200){int n=record.read(buffer,0,buffer.length,AudioRecord.READ_NON_BLOCKING);if(n<0)throw new IllegalStateException("AudioRecord read "+n);if(n==0){empty++;Thread.sleep(5);continue;}for(int i=0;i<n;i++){energy+=(double)buffer[i]*buffer[i];peak=Math.max(peak,Math.abs((int)buffer[i]));}samples+=n;}
                    AudioDeviceInfo route=record.getRoutedDevice();
                    AudioRecordingConfiguration config=record.getActiveRecordingConfiguration();
                    record.stop();
                    test.put("activity_resumed",resumed);test.put("client_silenced",config==null?JSONObject.NULL:config.isClientSilenced());
                    test.put("samples",samples);test.put("captured_frames",samples/channels);
                    test.put("rms",samples>0?Math.sqrt(energy/samples):0);test.put("peak",peak);test.put("empty_reads",empty);test.put("routed_device_type",route==null?-1:route.getType());
                    test.put("passed",samples>=((long)rate*channels) && samples%channels==0 && route!=null && resumed
                        && config!=null && !config.isClientSilenced());
                    test.put("limits","Stream opens and returns frames. Nonzero PCM energy does not prove intelligible speech, independent stereo channels, saved-file validity or meeting-app call routing.");all &= test.getBoolean("passed");
                }catch(Throwable error){test.put("passed",false);test.put("error",Log.getStackTraceString(error));all=false;}
                finally{if(record!=null)record.release();}
                inputs.put(test);
            }
        }finally{manager.setMode(oldMode);}
        result.put("microphone_sources",inputs);result.put("passed",all);
    }

    private void sensors(JSONObject result)throws Exception {
        SensorManager manager=(SensorManager)getSystemService(SENSOR_SERVICE);HandlerThread thread=new HandlerThread("sensor-events");thread.start();
        Map<Integer,Integer> counts=new HashMap<>();Map<Integer,Float> maximum=new HashMap<>();Map<Integer,Boolean> registrations=new HashMap<>();JSONArray inventory=new JSONArray();
        SensorEventListener listener=new SensorEventListener(){
            @Override public void onAccuracyChanged(Sensor sensor,int accuracy){}
            @Override public void onSensorChanged(SensorEvent event){synchronized(counts){int type=event.sensor.getType();counts.put(type,counts.getOrDefault(type,0)+1);float peak=0;for(float value:event.values)peak=Math.max(peak,Math.abs(value));maximum.put(type,Math.max(maximum.getOrDefault(type,0f),peak));}}
        };
        try {
            for(Sensor sensor:manager.getSensorList(Sensor.TYPE_ALL)){
                inventory.put(new JSONObject().put("name",sensor.getName()).put("type",sensor.getType()).put("vendor",sensor.getVendor()).put("reporting_mode",sensor.getReportingMode()).put("min_delay_us",sensor.getMinDelay()));
                if(sensor.getType()==Sensor.TYPE_ACCELEROMETER || sensor.getType()==Sensor.TYPE_GYROSCOPE || sensor.getType()==Sensor.TYPE_MAGNETIC_FIELD || sensor.getType()==Sensor.TYPE_LIGHT || sensor.getType()==Sensor.TYPE_PROXIMITY || sensor.getType()==Sensor.TYPE_PRESSURE)
                    registrations.put(sensor.getType(),manager.registerListener(listener,sensor,SensorManager.SENSOR_DELAY_NORMAL,new Handler(thread.getLooper())));
            }
            Thread.sleep(10000);JSONArray events=new JSONArray();boolean okay=true;
            synchronized(counts){for(Map.Entry<Integer,Boolean> entry:registrations.entrySet()){int type=entry.getKey(), count=counts.getOrDefault(type,0);boolean passed=entry.getValue() && count>0;events.put(new JSONObject().put("type",type).put("registered",entry.getValue()).put("events",count).put("max_absolute_value",maximum.getOrDefault(type,0f)).put("passed",passed));okay &= passed;}}
            result.put("inventory",inventory);result.put("event_tests",events);result.put("passed",okay && events.length()>0);
            result.put("sensor_limits","A stationary device may produce no updates for on-change sensors. Step detectors and motion-triggered sensors require physical motion; missing events are investigation items.");
        }finally{manager.unregisterListener(listener);thread.quitSafely();}
    }

    private static void waitFor(Object lock,java.util.function.BooleanSupplier ready,long timeout)throws Exception {
        long deadline=SystemClock.elapsedRealtime()+timeout;synchronized(lock){while(!ready.getAsBoolean()){long left=deadline-SystemClock.elapsedRealtime();if(left<=0)throw new IllegalStateException("Camera callback timeout");lock.wait(left);}}
    }
    private static Size size(Size[] choices,int maxPixels){
        Size selected=null;for(Size s:choices)if(s.getWidth()*s.getHeight()<=maxPixels && (selected==null || s.getWidth()*s.getHeight()>selected.getWidth()*selected.getHeight()))selected=s;
        return selected==null?choices[0]:selected;
    }
    static void camera(Context context,JSONObject result,String selectedId)throws Exception {
        CameraManager manager=(CameraManager)context.getSystemService(CAMERA_SERVICE);String[] ids=manager.getCameraIdList();result.put("camera_ids",new JSONArray(ids));
        JSONArray tests=new JSONArray();boolean all=selectedId==null?ids.length==2:Arrays.asList(ids).contains(selectedId);
        for(String id:ids){
            if(selectedId!=null && !selectedId.equals(id))continue;
            JSONObject test=new JSONObject().put("id",id);HandlerThread thread=new HandlerThread("camera-"+id);thread.start();Handler handler=new Handler(thread.getLooper());
            final Object lock=new Object();final CameraDevice[] device={null};final CameraCaptureSession[] session={null};final String[] error={null};final int[] previews={0},jpegs={0};final JSONArray jpegStats=new JSONArray();final boolean[] jpegValid={true};final JSONObject[] planeLayout={null};
            final JSONArray callbacks=new JSONArray();final boolean[] deviceClosed={false},sessionClosed={false};
            ImageReader yuv=null,jpeg=null;
            try {
                CameraCharacteristics c=manager.getCameraCharacteristics(id);StreamConfigurationMap map=c.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP);
                test.put("lens_facing",c.get(CameraCharacteristics.LENS_FACING));test.put("hardware_level",c.get(CameraCharacteristics.INFO_SUPPORTED_HARDWARE_LEVEL));
                Size ps=size(map.getOutputSizes(ImageFormat.YUV_420_888),640*480),js=size(map.getOutputSizes(ImageFormat.JPEG),1920*1080);
                test.put("preview_size",ps.toString());test.put("jpeg_size",js.toString());
                yuv=ImageReader.newInstance(ps.getWidth(),ps.getHeight(),ImageFormat.YUV_420_888,3);jpeg=ImageReader.newInstance(js.getWidth(),js.getHeight(),ImageFormat.JPEG,3);
                yuv.setOnImageAvailableListener(reader->{try(Image image=reader.acquireNextImage()){if(image!=null){synchronized(lock){
                    if(planeLayout[0]==null){JSONArray planes=new JSONArray();Image.Plane[] entries=image.getPlanes();boolean bounds=entries.length==3;
                        for(int p=0;p<entries.length;p++){Image.Plane entry=entries[p];int w=p==0?image.getWidth():(image.getWidth()+1)/2,h=p==0?image.getHeight():(image.getHeight()+1)/2;
                            long needed=(long)(h-1)*entry.getRowStride()+(long)(w-1)*entry.getPixelStride()+1;boolean fits=needed<=entry.getBuffer().remaining();bounds &= fits;
                            planes.put(new JSONObject().put("row_stride",entry.getRowStride()).put("pixel_stride",entry.getPixelStride()).put("buffer_bytes",entry.getBuffer().remaining()).put("visible_pixels_fit",fits));}
                        planeLayout[0]=new JSONObject().put("width",image.getWidth()).put("height",image.getHeight()).put("format",image.getFormat()).put("planes",planes).put("visible_pixels_fit",bounds);
                        if(!bounds)error[0]="YUV visible pixels exceed plane buffers";
                    }
                    previews[0]++;lock.notifyAll();}}}catch(Exception e){synchronized(lock){error[0]=e.toString();lock.notifyAll();}}},handler);
                jpeg.setOnImageAvailableListener(reader->{try(Image image=reader.acquireNextImage()){if(image!=null){ByteBuffer b=image.getPlanes()[0].getBuffer();byte[] bytes=new byte[b.remaining()];b.get(bytes);MessageDigest md=MessageDigest.getInstance("SHA-256");byte[] hash=md.digest(bytes);StringBuilder hex=new StringBuilder();for(byte value:hash)hex.append(String.format("%02x",value&255));boolean markers=bytes.length>4 && (bytes[0]&255)==255 && (bytes[1]&255)==216 && (bytes[bytes.length-2]&255)==255 && (bytes[bytes.length-1]&255)==217;
                    Bitmap bitmap=BitmapFactory.decodeByteArray(bytes,0,bytes.length);int width=bitmap==null?0:bitmap.getWidth(),height=bitmap==null?0:bitmap.getHeight();if(bitmap!=null)bitmap.recycle();boolean decoded=width==js.getWidth() && height==js.getHeight();
                    synchronized(lock){jpegValid[0] &= markers && decoded;jpegStats.put(new JSONObject().put("bytes",bytes.length).put("sha256",hex.toString()).put("jpeg_markers",markers).put("decoded_width",width).put("decoded_height",height).put("decoded_dimensions_match",decoded));jpegs[0]++;lock.notifyAll();}}}catch(Exception e){synchronized(lock){error[0]=e.toString();lock.notifyAll();}}},handler);
                manager.openCamera(id,new CameraDevice.StateCallback(){
                    @Override public void onOpened(CameraDevice camera){synchronized(lock){cameraEvent(callbacks,"device_opened",id);device[0]=camera;lock.notifyAll();}}
                    @Override public void onDisconnected(CameraDevice camera){synchronized(lock){cameraEvent(callbacks,"device_disconnected",id);error[0]="Camera disconnected";lock.notifyAll();}camera.close();}
                    @Override public void onError(CameraDevice camera,int code){synchronized(lock){cameraEvent(callbacks,"device_error_"+code,id);error[0]="Camera error "+code;lock.notifyAll();}camera.close();}
                    @Override public void onClosed(CameraDevice camera){synchronized(lock){cameraEvent(callbacks,"device_closed",id);deviceClosed[0]=true;lock.notifyAll();}}
                },handler);
                waitFor(lock,()->device[0]!=null || error[0]!=null,15000);if(error[0]!=null)throw new IllegalStateException(error[0]);
                device[0].createCaptureSession(Arrays.asList(yuv.getSurface(),jpeg.getSurface()),new CameraCaptureSession.StateCallback(){
                    @Override public void onConfigured(CameraCaptureSession s){synchronized(lock){cameraEvent(callbacks,"session_configured",id);session[0]=s;lock.notifyAll();}}
                    @Override public void onConfigureFailed(CameraCaptureSession s){synchronized(lock){cameraEvent(callbacks,"session_configure_failed",id);error[0]="Session configuration failed";lock.notifyAll();}}
                    @Override public void onClosed(CameraCaptureSession s){synchronized(lock){cameraEvent(callbacks,"session_closed",id);sessionClosed[0]=true;lock.notifyAll();}}
                    @Override public void onReady(CameraCaptureSession s){synchronized(lock){cameraEvent(callbacks,"session_ready",id);lock.notifyAll();}}
                    @Override public void onActive(CameraCaptureSession s){synchronized(lock){cameraEvent(callbacks,"session_active",id);lock.notifyAll();}}
                },handler);
                waitFor(lock,()->session[0]!=null || error[0]!=null,15000);if(error[0]!=null)throw new IllegalStateException(error[0]);
                CaptureRequest.Builder preview=device[0].createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW);preview.addTarget(yuv.getSurface());session[0].setRepeatingRequest(preview.build(),null,handler);
                waitFor(lock,()->previews[0]>=10 || error[0]!=null,15000);if(error[0]!=null)throw new IllegalStateException(error[0]);
                for(int i=0;i<3;i++){
                    int goal=i+1;CaptureRequest.Builder capture=device[0].createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE);capture.addTarget(jpeg.getSurface());
                    session[0].capture(capture.build(),new CameraCaptureSession.CaptureCallback(){@Override public void onCaptureFailed(CameraCaptureSession s,CaptureRequest r,CaptureFailure fail){synchronized(lock){error[0]="Still capture failed "+fail.getReason();lock.notifyAll();}}},handler);
                    waitFor(lock,()->jpegs[0]>=goal || error[0]!=null,15000);if(error[0]!=null)throw new IllegalStateException(error[0]);
                }
                test.put("capture_passed",previews[0]>=10 && jpegs[0]==3 && jpegValid[0]);
                test.put("passed",test.getBoolean("capture_passed"));all &= test.getBoolean("passed");
            }catch(Throwable e){test.put("passed",false);test.put("error",Log.getStackTraceString(e));all=false;}
            finally{
                synchronized(lock){cameraEvent(callbacks,"close_requested",id);}
                if(session[0]!=null){try{session[0].stopRepeating();}catch(Exception closeError){test.put("stop_repeating_error",closeError.toString());}session[0].close();}
                if(device[0]!=null){device[0].close();try{waitFor(lock,()->deviceClosed[0],10000);}catch(Exception closeError){test.put("close_error",closeError.toString());test.put("passed",false);all=false;}}
                if(yuv!=null)yuv.close();if(jpeg!=null)jpeg.close();thread.quitSafely();thread.join(2000);
            }
            test.put("device_closed_callback",deviceClosed[0]);test.put("session_closed_callback",sessionClosed[0]);test.put("callbacks",callbacks);
            test.put("preview_frames",previews[0]);test.put("yuv_plane_layout",planeLayout[0]);test.put("jpeg_frames",jpegs[0]);test.put("jpeg_statistics",jpegStats);tests.put(test);
            Thread.sleep(1500);
        }
        result.put("tests",tests);result.put("passed",all);
    }
    private static void cameraEvent(JSONArray events,String event,String id){
        if(events.length()>=128)return;
        try{events.put(new JSONObject().put("event",event).put("camera_id",id).put("elapsed_realtime_ms",SystemClock.elapsedRealtime()));}catch(JSONException ignored){}
    }
}
