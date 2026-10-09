package org.tabs3.validation.media;

import android.app.Activity;
import android.content.Intent;
import android.graphics.SurfaceTexture;
import android.media.*;
import android.opengl.*;
import android.os.*;
import android.util.Log;
import android.view.Surface;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.TextView;
import org.json.*;
import java.io.*;
import java.nio.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

/** Ordinary, separately signed app. Each invocation produces a bounded JSON report. */
public final class MainActivity extends Activity {
    private TextView status;
    private String output;
    private WebView web;
    private static final String TAG = "TabS3MediaProbe";

    static JSONObject startupProbe(String[] args) throws Exception {
        String command=args[0];
        JSONObject result=new JSONObject().put("command",command).put("sdk",Build.VERSION.SDK_INT);
        try {
        if("inventory".equals(command))inventory(result);
        else if("gpu".equals(command))gpu(result);
        else if("audio_route".equals(command))audioRoute(result,null);
        else if("offload_caps".equals(command))offloadCapabilities(result);
        else if("audio_input_caps".equals(command))audioInputCapabilities(result);
        else if("offload".equals(command) && args.length==3)audioOffload(result,args[1],Long.parseLong(args[2]));
        else if("decode".equals(command) && (args.length==3 || args.length==4))
            decode(result,new Intent().putExtra("input",args[1]).putExtra("codec",args[2])
                    .putExtra("diagnostic_color_override",args.length==4?args[3]:""));
        else if("encode".equals(command) && args.length==4){
            File target=new File(args[3]);String path=target.getCanonicalPath();
            if(!path.matches("/data/local/tmp/tabs3-media-[a-f0-9]{12}/encoded/[a-zA-Z0-9_-]+\\.(mp4|webm)"))
                throw new IllegalArgumentException("Encoder startup output must be in its new diagnostic directory");
            encodeToFile(result,new Intent().putExtra("codec",args[1]).putExtra("mime",args[2]),target);
        }
        else throw new IllegalArgumentException("Unknown or incomplete startup command");
        } catch(Throwable error){result.put("passed",false);result.put("error",Log.getStackTraceString(error));}
        return result;
    }

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        status = new TextView(this);
        status.setText("Running Tab S3 hardware diagnostic…");
        setContentView(status);
        Intent intent = getIntent();
        output = intent.getStringExtra("output");
        if (output == null || !output.matches("[a-zA-Z0-9_-]{1,80}\\.json")) output = "result.json";
        final String command = intent.getStringExtra("command");
        if ("webview".equals(command)) { webViewProbe(); return; }
        new Thread(() -> {
            JSONObject result = new JSONObject();
            long started = SystemClock.elapsedRealtime();
            try {
                result.put("command", command);
                result.put("sdk", Build.VERSION.SDK_INT);
                result.put("fingerprint", Build.FINGERPRINT);
                if ("inventory".equals(command)) inventory(result);
                else if ("gpu".equals(command)) gpu(result);
                else if ("decode".equals(command)) decode(result, intent);
                else if ("encode".equals(command)) encode(result, intent);
                else if ("audio_route".equals(command)) audioRoute(result, intent);
                else if ("offload_caps".equals(command)) offloadCapabilities(result);
                else if ("audio_input_caps".equals(command)) audioInputCapabilities(result);
                else if ("offload".equals(command)) audioOffload(result,intent.getStringExtra("input"),intent.getLongExtra("reference_pcm_frames",0));
                else throw new IllegalArgumentException("Unknown command");
            } catch (Throwable error) {
                try { result.put("passed", false); result.put("error", Log.getStackTraceString(error)); } catch (Exception ignored) {}
                Log.e(TAG, "Diagnostic failed", error);
            }
            try { result.put("elapsed_ms", SystemClock.elapsedRealtime() - started); } catch (Exception ignored) {}
            save(result);
        }, "hardware-probe").start();
    }

    private synchronized void save(JSONObject result) {
        try {
            File partial = new File(getFilesDir(), output + ".partial");
            try (FileOutputStream stream = new FileOutputStream(partial)) {
                stream.write(result.toString(2).getBytes("UTF-8")); stream.getFD().sync();
            }
            if (!partial.renameTo(new File(getFilesDir(), output))) throw new IOException("Report rename failed");
            Log.i(TAG, "REPORT " + output + " passed=" + result.optBoolean("passed", false));
            runOnUiThread(() -> status.setText("Diagnostic finished: " + output + "\n" + result.toString()));
        } catch (Exception error) { Log.e(TAG, "Cannot write report", error); }
    }

    private void webViewProbe() {
        final boolean[] done = { false };
        try {
            web = new WebView(this); setContentView(web);
            web.getSettings().setJavaScriptEnabled(true);
            web.setWebViewClient(new WebViewClient() {
                @Override public void onPageFinished(WebView view, String url) {
                    view.evaluateJavascript("document.getElementById('probe').textContent", value -> {
                        if (done[0]) return; done[0] = true;
                        JSONObject result = new JSONObject();
                        try { result.put("command", "webview"); result.put("javascript_result", value);
                              result.put("passed", "\"rendered\"".equals(value)); } catch (Exception ignored) {}
                        save(result);
                    });
                }
            });
            web.loadDataWithBaseURL("https://tabs3.invalid/", "<html><body><p id='probe'>initial</p><script>document.getElementById('probe').textContent='rendered';</script></body></html>", "text/html", "UTF-8", null);
            new Handler(Looper.getMainLooper()).postDelayed(() -> {
                if (done[0]) return; done[0] = true;
                JSONObject result = new JSONObject();
                try { result.put("command", "webview"); result.put("passed", false); result.put("error", "Renderer timeout"); } catch (Exception ignored) {}
                save(result);
            }, 20000);
        } catch (Throwable error) {
            JSONObject result = new JSONObject();
            try { result.put("passed", false); result.put("error", Log.getStackTraceString(error)); } catch (Exception ignored) {}
            save(result);
        }
    }

    private static void inventory(JSONObject result) throws Exception {
        JSONArray codecs = new JSONArray();
        for (MediaCodecInfo info : new MediaCodecList(MediaCodecList.ALL_CODECS).getCodecInfos()) {
            JSONObject codec = new JSONObject();
            codec.put("name", info.getName()); codec.put("canonical_name", info.getCanonicalName());
            codec.put("encoder", info.isEncoder()); codec.put("hardware_accelerated", info.isHardwareAccelerated());
            codec.put("software_only", info.isSoftwareOnly()); codec.put("vendor", info.isVendor());
            JSONArray types = new JSONArray();
            for (String type : info.getSupportedTypes()) {
                JSONObject item = new JSONObject(); item.put("mime", type);
                try {
                    MediaCodecInfo.CodecCapabilities cap = info.getCapabilitiesForType(type);
                    JSONArray profiles = new JSONArray();
                    for (MediaCodecInfo.CodecProfileLevel p : cap.profileLevels)
                        profiles.put(new JSONObject().put("profile", p.profile).put("level", p.level));
                    item.put("profiles", profiles); item.put("colors", new JSONArray(cap.colorFormats));
                    item.put("max_instances", cap.getMaxSupportedInstances());
                    for (String feature : new String[] { "secure-playback", "tunneled-playback", "adaptive-playback" })
                        item.put(feature, new JSONObject().put("supported", cap.isFeatureSupported(feature)).put("required", cap.isFeatureRequired(feature)));
                    if (cap.getVideoCapabilities() != null) {
                        MediaCodecInfo.VideoCapabilities v = cap.getVideoCapabilities();
                        item.put("widths", v.getSupportedWidths().toString()); item.put("heights", v.getSupportedHeights().toString());
                        item.put("frame_rates", v.getSupportedFrameRates().toString()); item.put("bitrates", v.getBitrateRange().toString());
                        JSONArray sizes = new JSONArray();
                        for (int[] pair : new int[][] {{320,240},{640,480},{1280,720},{1920,1080},{3840,2160}})
                            for (double fps : new double[] {24,30,60}) sizes.put(new JSONObject().put("width",pair[0]).put("height",pair[1]).put("fps",fps).put("supported",v.areSizeAndRateSupported(pair[0],pair[1],fps)));
                        item.put("sizes", sizes);
                    }
                    if (cap.getAudioCapabilities() != null) {
                        MediaCodecInfo.AudioCapabilities a = cap.getAudioCapabilities();
                        item.put("max_channels", a.getMaxInputChannelCount());
                        item.put("sample_rates", Arrays.toString(a.getSupportedSampleRateRanges()));
                        item.put("bitrates", a.getBitrateRange().toString());
                    }
                } catch (Throwable error) { item.put("error", Log.getStackTraceString(error)); }
                types.put(item);
            }
            codec.put("types", types); codecs.put(codec);
        }
        result.put("codecs", codecs); result.put("passed", codecs.length() > 0);
        result.put("limits", "Inventory describes advertised support; it does not prove decoding or hardware execution.");
    }

    private static FloatBuffer floats(float[] values) {
        FloatBuffer b = ByteBuffer.allocateDirect(values.length * 4).order(ByteOrder.nativeOrder()).asFloatBuffer();
        b.put(values).position(0); return b;
    }

    private static final class GL implements AutoCloseable {
        EGLDisplay display; EGLContext context; EGLSurface surface; EGLConfig config;
        final FloatBuffer vertices = floats(new float[]{-1,-1,1,-1,-1,1,1,1});
        GL(int version) { this(version,false); }
        GL(int version,boolean recordable) {
            display = EGL14.eglGetDisplay(EGL14.EGL_DEFAULT_DISPLAY);
            int[] values = new int[2];
            if (!EGL14.eglInitialize(display, values, 0, values, 1)) throw new IllegalStateException("eglInitialize " + EGL14.eglGetError());
            EGLConfig[] configs = new EGLConfig[1]; int[] count = new int[1];
            int render = version == 3 ? 0x40 : EGL14.EGL_OPENGL_ES2_BIT;
            int[] attrs = {EGL14.EGL_RED_SIZE,8,EGL14.EGL_GREEN_SIZE,8,EGL14.EGL_BLUE_SIZE,8,EGL14.EGL_ALPHA_SIZE,8,EGL14.EGL_RENDERABLE_TYPE,render,EGL14.EGL_SURFACE_TYPE,EGL14.EGL_PBUFFER_BIT,EGL14.EGL_NONE};
            if(recordable)attrs=new int[]{EGL14.EGL_RED_SIZE,8,EGL14.EGL_GREEN_SIZE,8,EGL14.EGL_BLUE_SIZE,8,EGL14.EGL_ALPHA_SIZE,8,EGL14.EGL_RENDERABLE_TYPE,render,EGL14.EGL_SURFACE_TYPE,EGL14.EGL_PBUFFER_BIT|EGL14.EGL_WINDOW_BIT,0x3142,1,EGL14.EGL_NONE};
            if (!EGL14.eglChooseConfig(display,attrs,0,configs,0,1,count,0) || count[0] == 0) throw new IllegalStateException("No EGL config for ES" + version);
            config=configs[0];
            context = EGL14.eglCreateContext(display,configs[0],EGL14.EGL_NO_CONTEXT,new int[]{EGL14.EGL_CONTEXT_CLIENT_VERSION,version,EGL14.EGL_NONE},0);
            surface = EGL14.eglCreatePbufferSurface(display,configs[0],new int[]{EGL14.EGL_WIDTH,128,EGL14.EGL_HEIGHT,128,EGL14.EGL_NONE},0);
            if (!EGL14.eglMakeCurrent(display,surface,surface,context)) throw new IllegalStateException("eglMakeCurrent " + EGL14.eglGetError());
            GLES20.glViewport(0,0,128,128); check("init");
        }
        static int shader(int type, String source) {
            int shader = GLES20.glCreateShader(type); GLES20.glShaderSource(shader,source); GLES20.glCompileShader(shader);
            int[] ok = new int[1]; GLES20.glGetShaderiv(shader,GLES20.GL_COMPILE_STATUS,ok,0);
            if (ok[0] == 0) throw new IllegalStateException(GLES20.glGetShaderInfoLog(shader)); return shader;
        }
        int program(String fragment) {
            int vs = shader(GLES20.GL_VERTEX_SHADER,"attribute vec2 a; varying vec2 uv; void main(){ gl_Position=vec4(a,0.,1.); uv=(a+1.)*.5; }");
            int fs = shader(GLES20.GL_FRAGMENT_SHADER,fragment);
            int p = GLES20.glCreateProgram(); GLES20.glAttachShader(p,vs); GLES20.glAttachShader(p,fs); GLES20.glLinkProgram(p);
            int[] ok=new int[1]; GLES20.glGetProgramiv(p,GLES20.GL_LINK_STATUS,ok,0);
            if (ok[0] == 0) throw new IllegalStateException(GLES20.glGetProgramInfoLog(p));
            GLES20.glDeleteShader(vs); GLES20.glDeleteShader(fs); return p;
        }
        void draw(int p) {
            GLES20.glUseProgram(p); int a=GLES20.glGetAttribLocation(p,"a");
            vertices.position(0); GLES20.glEnableVertexAttribArray(a); GLES20.glVertexAttribPointer(a,2,GLES20.GL_FLOAT,false,0,vertices);
            GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP,0,4); GLES20.glFinish(); check("draw");
        }
        JSONArray pixels() throws Exception {
            JSONArray pixels=new JSONArray(); ByteBuffer rgba=ByteBuffer.allocateDirect(4);
            for(int[] xy:new int[][]{{32,32},{96,32},{32,96},{96,96}}){
                rgba.clear(); GLES20.glReadPixels(xy[0],xy[1],1,1,GLES20.GL_RGBA,GLES20.GL_UNSIGNED_BYTE,rgba);
                pixels.put(new JSONArray(new int[]{rgba.get(0)&255,rgba.get(1)&255,rgba.get(2)&255,rgba.get(3)&255}));
            }
            check("readback"); return pixels;
        }
        JSONArray centerPixel() throws Exception {
            ByteBuffer rgba=ByteBuffer.allocateDirect(4);
            GLES20.glReadPixels(64,64,1,1,GLES20.GL_RGBA,GLES20.GL_UNSIGNED_BYTE,rgba);
            check("center readback");
            return new JSONArray(new int[]{rgba.get(0)&255,rgba.get(1)&255,rgba.get(2)&255,rgba.get(3)&255});
        }
        static void check(String stage){int error=GLES20.glGetError(); if(error!=GLES20.GL_NO_ERROR)throw new IllegalStateException(stage+" GL error "+error);}
        @Override public void close(){
            if(display!=null){ EGL14.eglMakeCurrent(display,EGL14.EGL_NO_SURFACE,EGL14.EGL_NO_SURFACE,EGL14.EGL_NO_CONTEXT);
                if(surface!=null) EGL14.eglDestroySurface(display,surface); if(context!=null) EGL14.eglDestroyContext(display,context); EGL14.eglTerminate(display); }
        }
    }

    private static void gpu(JSONObject result) throws Exception {
        JSONArray tests=new JSONArray(); boolean all=true;
        for(int version:new int[]{2,3}){
            JSONObject test=new JSONObject().put("requested_es",version);
            try(GL gl=new GL(version)){
                test.put("vendor",GLES20.glGetString(GLES20.GL_VENDOR)); test.put("renderer",GLES20.glGetString(GLES20.GL_RENDERER));
                test.put("version",GLES20.glGetString(GLES20.GL_VERSION)); test.put("extensions",GLES20.glGetString(GLES20.GL_EXTENSIONS));
                int p=gl.program("precision highp float; varying vec2 uv; void main(){gl_FragColor=vec4(step(.5,uv.x),step(.5,uv.y),.25,1.);}");
                long start=SystemClock.elapsedRealtime(); for(int i=0;i<120;i++)gl.draw(p);
                test.put("draws",120); test.put("draw_ms",SystemClock.elapsedRealtime()-start);
                JSONArray pixels=gl.pixels(); test.put("pixels",pixels);
                boolean okay=true; int[][] expected={{0,0,64,255},{255,0,64,255},{0,255,64,255},{255,255,64,255}};
                for(int i=0;i<4;i++)for(int j=0;j<4;j++)okay &= Math.abs(pixels.getJSONArray(i).getInt(j)-expected[i][j])<=2;
                GLES20.glDeleteProgram(p); test.put("passed",okay); all &= okay;
                if(version==3){
                    int[] ids=new int[2]; GLES30.glGenFramebuffers(1,ids,0); GLES30.glGenRenderbuffers(1,ids,1);
                    GLES30.glBindFramebuffer(GLES30.GL_READ_FRAMEBUFFER,ids[0]); GLES30.glBindRenderbuffer(GLES30.GL_RENDERBUFFER,ids[1]);
                    GLES30.glRenderbufferStorage(GLES30.GL_RENDERBUFFER,GLES30.GL_RGBA8,128,128);
                    GLES30.glFramebufferRenderbuffer(GLES30.GL_READ_FRAMEBUFFER,GLES30.GL_COLOR_ATTACHMENT0,GLES30.GL_RENDERBUFFER,ids[1]);
                    if(GLES30.glCheckFramebufferStatus(GLES30.GL_READ_FRAMEBUFFER)!=GLES30.GL_FRAMEBUFFER_COMPLETE)throw new IllegalStateException("ES3 framebuffer incomplete");
                    GLES30.glBindFramebuffer(GLES30.GL_FRAMEBUFFER,ids[0]); GLES30.glClearColor(.25f,.5f,.75f,1); GLES30.glClear(GLES30.GL_COLOR_BUFFER_BIT);
                    GLES30.glBindFramebuffer(GLES30.GL_DRAW_FRAMEBUFFER,0); GLES30.glBlitFramebuffer(0,0,128,128,0,0,128,128,GLES30.GL_COLOR_BUFFER_BIT,GLES30.GL_NEAREST);
                    GLES30.glBindFramebuffer(GLES30.GL_FRAMEBUFFER,0); JSONArray blit=gl.pixels(); test.put("es3_blit_pixels",blit);
                    boolean correct=true; int[] want={64,128,191,255}; for(int i=0;i<4;i++)for(int j=0;j<4;j++)correct &= Math.abs(blit.getJSONArray(i).getInt(j)-want[j])<=2;
                    test.put("es3_blit_passed",correct); all &= correct;
                    GLES30.glDeleteFramebuffers(1,ids,0); GLES30.glDeleteRenderbuffers(1,ids,1); GL.check("ES3 blit");
                    // Execute a compute shader and read every SSBO result back.
                    // A reported GLES version alone is not a compute pass.
                    int shader=GL.shader(GLES31.GL_COMPUTE_SHADER,
                        "#version 310 es\nlayout(local_size_x=64) in; layout(std430,binding=0) buffer Output { uint values[]; }; void main(){uint i=gl_GlobalInvocationID.x; values[i]=i*i+7u;}");
                    int compute=GLES20.glCreateProgram();GLES20.glAttachShader(compute,shader);GLES20.glLinkProgram(compute);
                    int[] linked=new int[1];GLES20.glGetProgramiv(compute,GLES20.GL_LINK_STATUS,linked,0);
                    if(linked[0]==0)throw new IllegalStateException("Compute link: "+GLES20.glGetProgramInfoLog(compute));
                    int[] storage=new int[1];GLES30.glGenBuffers(1,storage,0);
                    GLES30.glBindBuffer(GLES31.GL_SHADER_STORAGE_BUFFER,storage[0]);
                    GLES30.glBufferData(GLES31.GL_SHADER_STORAGE_BUFFER,128*4,null,GLES30.GL_DYNAMIC_READ);
                    GLES30.glBindBufferBase(GLES31.GL_SHADER_STORAGE_BUFFER,0,storage[0]);
                    GLES20.glUseProgram(compute);GLES31.glDispatchCompute(2,1,1);
                    GLES31.glMemoryBarrier(GLES31.GL_BUFFER_UPDATE_BARRIER_BIT|GLES31.GL_SHADER_STORAGE_BARRIER_BIT);GLES20.glFinish();
                    Buffer mapped=GLES30.glMapBufferRange(GLES31.GL_SHADER_STORAGE_BUFFER,0,128*4,GLES30.GL_MAP_READ_BIT);
                    if(!(mapped instanceof ByteBuffer))throw new IllegalStateException("Compute readback mapping failed");
                    IntBuffer values=((ByteBuffer)mapped).order(ByteOrder.nativeOrder()).asIntBuffer();boolean computeOkay=true;
                    for(int i=0;i<128;i++)computeOkay &= values.get(i)==i*i+7;
                    if(!GLES30.glUnmapBuffer(GLES31.GL_SHADER_STORAGE_BUFFER))throw new IllegalStateException("Compute buffer contents lost");
                    GLES30.glDeleteBuffers(1,storage,0);GLES20.glDeleteProgram(compute);GLES20.glDeleteShader(shader);GL.check("ES3.1 compute");
                    test.put("es31_compute_values_checked",128);test.put("es31_compute_passed",computeOkay);all &= computeOkay;
                }
            }catch(Throwable error){test.put("passed",false);test.put("error",Log.getStackTraceString(error));all=false;}
            tests.put(test);
        }
        result.put("tests",tests); result.put("passed",all);
        result.put("limits","Pixel checks and short draw loops; no claim about long gaming workloads or thermal limits.");
    }

    private static final class VideoSurface implements AutoCloseable {
        final GL gl = new GL(2);
        final HandlerThread callbacks=new HandlerThread("surface-callback");
        final Object lock=new Object(); boolean available;
        final int texture, program; final SurfaceTexture st; final Surface surface;
        VideoSurface(int width,int height){
            int[] ids=new int[1]; GLES20.glGenTextures(1,ids,0); texture=ids[0]; GLES20.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,texture);
            GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,GLES20.GL_TEXTURE_MIN_FILTER,GLES20.GL_NEAREST);
            GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,GLES20.GL_TEXTURE_MAG_FILTER,GLES20.GL_NEAREST);
            GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,GLES20.GL_TEXTURE_WRAP_S,GLES20.GL_CLAMP_TO_EDGE);
            GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,GLES20.GL_TEXTURE_WRAP_T,GLES20.GL_CLAMP_TO_EDGE);
            st=new SurfaceTexture(texture); st.setDefaultBufferSize(width,height); callbacks.start();
            st.setOnFrameAvailableListener(t->{synchronized(lock){available=true;lock.notifyAll();}},new Handler(callbacks.getLooper()));
            surface=new Surface(st);
            program=gl.program("#extension GL_OES_EGL_image_external : require\nprecision highp float; varying vec2 uv; uniform samplerExternalOES tex; uniform mat4 transform; void main(){gl_FragColor=texture2D(tex,(transform*vec4(uv,0.,1.)).xy);}");
        }
        JSONArray consume(boolean read) throws Exception {
            long deadline=SystemClock.elapsedRealtime()+3000;
            synchronized(lock){while(!available){long left=deadline-SystemClock.elapsedRealtime(); if(left<=0)throw new IllegalStateException("Decoded surface frame timeout"); lock.wait(left);}available=false;}
            st.updateTexImage(); float[] transform=new float[16]; st.getTransformMatrix(transform);
            GLES20.glUseProgram(program); GLES20.glUniformMatrix4fv(GLES20.glGetUniformLocation(program,"transform"),1,false,transform,0);
            GLES20.glActiveTexture(GLES20.GL_TEXTURE0); GLES20.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,texture); GLES20.glUniform1i(GLES20.glGetUniformLocation(program,"tex"),0);
            gl.draw(program); return read ? gl.pixels() : null;
        }
        @Override public void close(){surface.release();st.release();callbacks.quitSafely(); GLES20.glDeleteProgram(program);GLES20.glDeleteTextures(1,new int[]{texture},0);gl.close();}
    }

    private void encode(JSONObject result,Intent intent) throws Exception {
        encodeToFile(result,intent,new File(getFilesDir(),output.replace(".json",".mp4")));
    }
    private static void encodeToFile(JSONObject result,Intent intent,File encoded) throws Exception {
        String name=intent.getStringExtra("codec"), mime=intent.getStringExtra("mime");
        if(name==null || mime==null || !mime.startsWith("video/"))throw new IllegalArgumentException("Specify a video encoder and MIME");
        final int width="video/3gpp".equals(mime)?352:640;
        final int height="video/3gpp".equals(mime)?288:480,fps=30,total=30;
        MediaCodec codec=null; MediaMuxer muxer=null; Surface input=null; GL gl=null; EGLSurface window=null;
        boolean muxStarted=false,codecStarted=false;
        try {
            MediaFormat format=MediaFormat.createVideoFormat(mime,width,height);
            format.setInteger(MediaFormat.KEY_COLOR_FORMAT,MediaCodecInfo.CodecCapabilities.COLOR_FormatSurface);
            format.setInteger(MediaFormat.KEY_BIT_RATE,"video/3gpp".equals(mime)?128000:2000000);format.setInteger(MediaFormat.KEY_FRAME_RATE,fps);format.setInteger(MediaFormat.KEY_I_FRAME_INTERVAL,1);
            format.setInteger(MediaFormat.KEY_COLOR_STANDARD,MediaFormat.COLOR_STANDARD_BT709);
            format.setInteger(MediaFormat.KEY_COLOR_TRANSFER,MediaFormat.COLOR_TRANSFER_SDR_VIDEO);
            format.setInteger(MediaFormat.KEY_COLOR_RANGE,MediaFormat.COLOR_RANGE_LIMITED);
            codec=MediaCodec.createByCodecName(name);MediaCodecInfo info=codec.getCodecInfo();
            result.put("component",codec.getName());result.put("hardware_accelerated",info.isHardwareAccelerated());result.put("vendor",info.isVendor());result.put("mime",mime);
            codec.configure(format,null,null,MediaCodec.CONFIGURE_FLAG_ENCODE); input=codec.createInputSurface();codec.start();codecStarted=true;
            muxer=new MediaMuxer(encoded.getPath(),"video/x-vnd.on2.vp8".equals(mime)?MediaMuxer.OutputFormat.MUXER_OUTPUT_WEBM:MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4);
            gl=new GL(2,true);
            window=EGL14.eglCreateWindowSurface(gl.display,gl.config,input,new int[]{EGL14.EGL_NONE},0);
            if(!EGL14.eglMakeCurrent(gl.display,window,window,gl.context))throw new IllegalStateException("Encoder EGL binding failed "+EGL14.eglGetError());
            MediaCodec.BufferInfo bi=new MediaCodec.BufferInfo();int sent=0,frames=0,track=-1;boolean signalled=false,eos=false;long started=SystemClock.elapsedRealtime(),bytes=0;
            while(!eos){
                if(SystemClock.elapsedRealtime()-started>90000)throw new IllegalStateException("Encode exceeded 90 seconds");
                if(sent<total){
                    GLES20.glViewport(0,0,width,height);GLES20.glEnable(GLES20.GL_SCISSOR_TEST);
                    int[][] colors={{0,0,1},{1,1,1},{1,0,0},{0,1,0}};
                    for(int i=0;i<4;i++){GLES20.glScissor((i%2)*width/2,(i/2)*height/2,width/2,height/2);GLES20.glClearColor(colors[i][0],colors[i][1],colors[i][2],1);GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT);}
                    // Frame-dependent marker lets the independent decoder detect duplication/order errors.
                    float marker=sent<10?1.f:sent<20?.5f:0.f;
                    GLES20.glScissor(width*2/5,height*2/5,width/5,height/5);
                    GLES20.glClearColor(marker,marker,marker,1);GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT);
                    GLES20.glDisable(GLES20.GL_SCISSOR_TEST);GL.check("encoder draw");
                    EGLExt.eglPresentationTimeANDROID(gl.display,window,sent*1000000000L/fps);
                    if(!EGL14.eglSwapBuffers(gl.display,window))throw new IllegalStateException("Encoder swap failed");sent++;
                }else if(!signalled){codec.signalEndOfInputStream();signalled=true;}
                // Drain every available packet before generating another frame.
                while(true){int idx=codec.dequeueOutputBuffer(bi,10000);
                    if(idx==MediaCodec.INFO_TRY_AGAIN_LATER)break;
                    if(idx==MediaCodec.INFO_OUTPUT_FORMAT_CHANGED){if(muxStarted)throw new IllegalStateException("Second output format");MediaFormat out=codec.getOutputFormat();result.put("output_format",out.toString());track=muxer.addTrack(out);muxer.start();muxStarted=true;}
                    else if(idx>=0){if(bi.size>0 && (bi.flags&MediaCodec.BUFFER_FLAG_CODEC_CONFIG)==0){if(!muxStarted)throw new IllegalStateException("Output before muxer format");ByteBuffer b=codec.getOutputBuffer(idx);b.position(bi.offset);b.limit(bi.offset+bi.size);muxer.writeSampleData(track,b,bi);frames++;bytes+=bi.size;}codec.releaseOutputBuffer(idx,false);if((bi.flags&MediaCodec.BUFFER_FLAG_END_OF_STREAM)!=0){eos=true;break;}}
                }
            }
            muxer.stop();muxStarted=false;codec.stop();codecStarted=false;
            result.put("input_frames",sent);result.put("encoded_frames",frames);result.put("encoded_bytes",bytes);result.put("encoded_file",encoded.getName());result.put("output_eos",eos);result.put("encode_ms",SystemClock.elapsedRealtime()-started);
            result.put("passed",sent==total && frames==total && bytes>0 && eos);
            result.put("limits","Host must independently demux and decode this file, checking every frame and reference pixels. Short encoding does not establish sustained recording performance.");
        }finally{
            if(gl!=null && window!=null){EGL14.eglMakeCurrent(gl.display,gl.surface,gl.surface,gl.context);EGL14.eglDestroySurface(gl.display,window);}
            if(gl!=null)gl.close();if(input!=null)input.release();
            if(codec!=null){if(codecStarted)try{codec.stop();}catch(Exception ignored){}codec.release();}
            if(muxer!=null){if(muxStarted)try{muxer.stop();}catch(Exception ignored){}muxer.release();}
        }
    }

    private static void decode(JSONObject result,Intent intent) throws Exception {
        String path=intent.getStringExtra("input"), name=intent.getStringExtra("codec");
        File file=new File(path);String canonical=file.getCanonicalPath();
        if((!canonical.startsWith("/data/local/tmp/tabs3-media/") && !canonical.matches("/data/local/tmp/tabs3-media-[a-f0-9]{12}/[a-zA-Z0-9_.-]+")) || !file.isFile())throw new IllegalArgumentException("Input must be a staged diagnostic fixture");
        MediaExtractor extractor=new MediaExtractor(); MediaCodec codec=null; VideoSurface video=null;
        try{
            extractor.setDataSource(path); MediaFormat format=null; int track=-1;
            for(int i=0;i<extractor.getTrackCount();i++){MediaFormat f=extractor.getTrackFormat(i);String mime=f.getString(MediaFormat.KEY_MIME);if(mime.startsWith("video/") || mime.startsWith("audio/")){format=f;track=i;break;}}
            if(format==null)throw new IllegalStateException("No media track"); extractor.selectTrack(track);
            String mime=format.getString(MediaFormat.KEY_MIME); boolean isVideo=mime.startsWith("video/");
            result.put("input",file.getName());result.put("format",format.toString());result.put("mime",mime);
            String override=intent.getStringExtra("diagnostic_color_override");
            if(override!=null && !override.isEmpty()){
                if(!"bt709".equals(override) || !"video/mpeg2".equals(mime))
                    throw new IllegalArgumentException("The explicit diagnostic override is only for MPEG-2 BT.709");
                format.setInteger(MediaFormat.KEY_COLOR_STANDARD,MediaFormat.COLOR_STANDARD_BT709);
                format.setInteger(MediaFormat.KEY_COLOR_TRANSFER,MediaFormat.COLOR_TRANSFER_SDR_VIDEO);
                format.setInteger(MediaFormat.KEY_COLOR_RANGE,MediaFormat.COLOR_RANGE_LIMITED);
                result.put("diagnostic_color_override",override);result.put("overridden_input_format",format.toString());
                result.put("default_metadata_handling_tested",false);
            }
            codec = name == null || "default".equals(name) ? MediaCodec.createDecoderByType(mime) : MediaCodec.createByCodecName(name);
            MediaCodecInfo ci=codec.getCodecInfo();result.put("component",codec.getName()); result.put("hardware_accelerated",ci.isHardwareAccelerated());result.put("software_only",ci.isSoftwareOnly());result.put("vendor",ci.isVendor());
            if(isVideo)video=new VideoSurface(format.getInteger(MediaFormat.KEY_WIDTH),format.getInteger(MediaFormat.KEY_HEIGHT));
            codec.configure(format,video==null?null:video.surface,null,0);codec.start();
            if(isVideo && ci.isHardwareAccelerated() && android.os.Process.myUid()==2000){
                System.out.println("TAB_S3_CODEC_READY "+codec.getName()+" pid="+android.os.Process.myPid()+" mode=decode");
                System.out.flush();
            }
            boolean inputEOS=false,outputEOS=false;int inputSamples=0,frames=0;long bytes=0,pcmSamples=0,lastPTS=-1,firstPTS=-1;
            boolean monotonic=true;double squares=0;int peak=0,signChanges=0,lastSign=0,channels=1,sampleRate=0;
            int encoding=AudioFormat.ENCODING_PCM_16BIT; JSONArray rendered=new JSONArray();JSONArray outputFormats=new JSONArray();
            MediaCodec.BufferInfo bi=new MediaCodec.BufferInfo();long started=SystemClock.elapsedRealtime();
            while(!outputEOS){
                if(SystemClock.elapsedRealtime()-started>90000)throw new IllegalStateException("Decode exceeded 90 seconds");
                if(!inputEOS){int idx=codec.dequeueInputBuffer(1000);if(idx>=0){ByteBuffer b=codec.getInputBuffer(idx);int n=extractor.readSampleData(b,0);if(n<0){codec.queueInputBuffer(idx,0,0,0,MediaCodec.BUFFER_FLAG_END_OF_STREAM);inputEOS=true;}else{codec.queueInputBuffer(idx,0,n,extractor.getSampleTime(),0);extractor.advance();inputSamples++;}}}
                int idx=codec.dequeueOutputBuffer(bi,1000);
                if(idx==MediaCodec.INFO_OUTPUT_FORMAT_CHANGED){MediaFormat f=codec.getOutputFormat();outputFormats.put(f.toString()); if(!isVideo){channels=f.getInteger(MediaFormat.KEY_CHANNEL_COUNT);sampleRate=f.getInteger(MediaFormat.KEY_SAMPLE_RATE);if(f.containsKey(MediaFormat.KEY_PCM_ENCODING))encoding=f.getInteger(MediaFormat.KEY_PCM_ENCODING);}}
                else if(idx>=0){
                    boolean data=bi.size>0 && (bi.flags&MediaCodec.BUFFER_FLAG_CODEC_CONFIG)==0;
                    if(data){ if(firstPTS<0)firstPTS=bi.presentationTimeUs; if(lastPTS>bi.presentationTimeUs)monotonic=false;lastPTS=bi.presentationTimeUs;
                        if(isVideo){frames++;codec.releaseOutputBuffer(idx,true);JSONArray pixels=video.consume(frames<=3 || frames%30==0);if(pixels!=null)rendered.put(new JSONObject().put("frame",frames).put("pts_us",bi.presentationTimeUs).put("pixels",pixels).put("center_pixel",video.gl.centerPixel()));}
                        else {ByteBuffer b=codec.getOutputBuffer(idx).duplicate().order(ByteOrder.LITTLE_ENDIAN);b.position(bi.offset);b.limit(bi.offset+bi.size);bytes+=bi.size;
                            int index=0; while(b.remaining()>=(encoding==AudioFormat.ENCODING_PCM_FLOAT?4:2)){int sample=encoding==AudioFormat.ENCODING_PCM_FLOAT?(int)(b.getFloat()*32767):b.getShort();squares+=(double)sample*sample;peak=Math.max(peak,Math.abs(sample));pcmSamples++;if(index++%channels==0){int sign=sample>0?1:sample<0?-1:0;if(sign!=0){if(lastSign!=0 && sign!=lastSign)signChanges++;lastSign=sign;}}}codec.releaseOutputBuffer(idx,false);}
                    }else codec.releaseOutputBuffer(idx,false);
                    outputEOS=(bi.flags&MediaCodec.BUFFER_FLAG_END_OF_STREAM)!=0;
                }
            }
            result.put("input_samples",inputSamples);result.put("output_frames",frames);result.put("first_pts_us",firstPTS);result.put("last_pts_us",lastPTS);result.put("monotonic_pts",monotonic);
            result.put("decode_ms",SystemClock.elapsedRealtime()-started);result.put("output_eos",outputEOS);result.put("output_formats",outputFormats);
            result.put("rendered_samples",rendered);result.put("pcm_bytes",bytes);result.put("pcm_samples",pcmSamples);result.put("pcm_encoding",encoding);result.put("channels",channels);result.put("sample_rate",sampleRate);
            result.put("rms",pcmSamples>0?Math.sqrt(squares/pcmSamples):0);result.put("peak",peak);
            result.put("estimated_frequency_hz",pcmSamples>0 && channels>0 ? signChanges*sampleRate/(2.0*(pcmSamples/channels)):0);
            result.put("passed",outputEOS && monotonic && (isVideo?frames>0 && frames==inputSamples:pcmSamples>0 && peak>0));
            result.put("limits",isVideo?"Surface output rendered through external OES texture. Host compares sampled pixels and fixture frame count; flags alone are not proof of hardware execution.":"PCM decoding is separate from speaker routing and microphone recording. DSP offload is not proven by decoder metadata.");
            codec.stop();
        }finally{if(codec!=null)codec.release();if(video!=null)video.close();extractor.release();}
    }

    private static void offloadCapabilities(JSONObject result) throws Exception {
        int[] encodings={AudioFormat.ENCODING_MP3,AudioFormat.ENCODING_AAC_LC,
                AudioFormat.ENCODING_AAC_HE_V1,AudioFormat.ENCODING_AAC_HE_V2,
                AudioFormat.ENCODING_OPUS,AudioFormat.ENCODING_AC3,AudioFormat.ENCODING_E_AC3};
        String[] names={"MP3","AAC-LC","HE-AAC-v1","HE-AAC-v2","Opus","AC3","E-AC3"};
        AudioAttributes attributes=new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build();
        JSONArray formats=new JSONArray();int supported=0;boolean consistent=true;
        for(int i=0;i<encodings.length;i++)for(int rate:new int[]{44100,48000})
            for(int channels:new int[]{AudioFormat.CHANNEL_OUT_MONO,AudioFormat.CHANNEL_OUT_STEREO}){
                AudioFormat format=new AudioFormat.Builder().setEncoding(encodings[i])
                        .setSampleRate(rate).setChannelMask(channels).build();
                int mode=AudioManager.getPlaybackOffloadSupport(format,attributes);
                boolean available=AudioManager.isOffloadedPlaybackSupported(format,attributes);
                formats.put(new JSONObject().put("encoding",names[i]).put("sample_rate",rate)
                        .put("channel_mask",channels).put("offload_support",mode)
                        .put("offload_supported",available));
                consistent &= mode>=0 && mode<=2 && available==(mode!=0);
                if(available)supported++;
            }
        result.put("formats",formats);result.put("supported_format_count",supported);
        result.put("passed",consistent);result.put("hardware_offload_tested",false);
        result.put("limits","Capability queries only. A supported format still requires forced offloaded playback, stream completion and actual DSP/compressed-device evidence.");
    }

    private static void audioInputCapabilities(JSONObject result) throws Exception {
        JSONArray formats=new JSONArray();boolean required=true;
        for(int rate:new int[]{8000,16000,44100,48000})
            for(int mask:new int[]{AudioFormat.CHANNEL_IN_MONO,AudioFormat.CHANNEL_IN_STEREO}){
                int bytes=AudioRecord.getMinBufferSize(rate,mask,AudioFormat.ENCODING_PCM_16BIT);
                formats.put(new JSONObject().put("sample_rate",rate).put("channel_mask",mask).put("minimum_buffer_bytes",bytes));
                if(rate==48000)required &= bytes>0;
            }
        result.put("formats",formats);result.put("passed",required);result.put("microphone_opened",false);
        result.put("limits","Read-only HAL input-buffer queries. Does not open a microphone or establish capture, intelligibility or voice routing. Only advertised 48 kHz mono/stereo is required here.");
    }

    private static void audioOffload(JSONObject result,String path,long referenceFrames) throws Exception {
        File file=new File(path);
        if(!file.getCanonicalPath().matches("/data/local/tmp/tabs3-media-[a-f0-9]{12}/[a-zA-Z0-9_.-]+") || !file.isFile())
            throw new IllegalArgumentException("Offload input must be its staged generated fixture");
        MediaExtractor extractor=new MediaExtractor();AudioTrack track=null;
        ExecutorService callbacks=Executors.newSingleThreadExecutor();
        CountDownLatch completed=new CountDownLatch(1);
        AtomicInteger ended=new AtomicInteger(),tornDown=new AtomicInteger(),requests=new AtomicInteger();
        AudioTrack.StreamEventCallback callback=new AudioTrack.StreamEventCallback(){
            @Override public void onPresentationEnded(AudioTrack ignored){ended.incrementAndGet();completed.countDown();}
            @Override public void onTearDown(AudioTrack ignored){tornDown.incrementAndGet();completed.countDown();}
            @Override public void onDataRequest(AudioTrack ignored,int size){requests.incrementAndGet();}
        };
        boolean registered=false;
        try {
            extractor.setDataSource(path);
            if(extractor.getTrackCount()!=1)throw new IllegalArgumentException("One generated audio track required");
            MediaFormat media=extractor.getTrackFormat(0);String mime=media.getString(MediaFormat.KEY_MIME);
            int encoding="audio/mpeg".equals(mime)?AudioFormat.ENCODING_MP3:
                    "audio/mp4a-latm".equals(mime)?AudioFormat.ENCODING_AAC_LC:0;
            if(encoding==0)throw new IllegalArgumentException("Only MP3 and AAC-LC offload are tested");
            int rate=media.getInteger(MediaFormat.KEY_SAMPLE_RATE),channels=media.getInteger(MediaFormat.KEY_CHANNEL_COUNT);
            if(channels!=1 && channels!=2)throw new IllegalArgumentException("Mono/stereo fixture required");
            long duration=media.getLong(MediaFormat.KEY_DURATION);
            if(duration<=0 || duration>10000000)throw new IllegalArgumentException("Generated fixture exceeds ten seconds");
            if(referenceFrames<=0 || referenceFrames>10L*rate)
                throw new IllegalArgumentException("Independent decoded PCM frame count required");
            AudioFormat format=new AudioFormat.Builder().setEncoding(encoding).setSampleRate(rate)
                    .setChannelMask(channels==1?AudioFormat.CHANNEL_OUT_MONO:AudioFormat.CHANNEL_OUT_STEREO).build();
            AudioAttributes attributes=new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build();
            int support=AudioManager.getDirectPlaybackSupport(format,attributes);
            result.put("input",file.getName());result.put("mime",mime);result.put("format",media.toString());
            result.put("sample_rate",rate);result.put("channels",channels);result.put("duration_us",duration);
            result.put("reference_pcm_frames",referenceFrames);result.put("playback_frame_tolerance",4096);
            result.put("direct_playback_support",support);result.put("passed",false);
            if((support & (AudioManager.DIRECT_PLAYBACK_OFFLOAD_SUPPORTED|AudioManager.DIRECT_PLAYBACK_OFFLOAD_GAPLESS_SUPPORTED))==0){
                result.put("status","offload_not_supported");return;
            }
            extractor.selectTrack(0);ByteArrayOutputStream compressed=new ByteArrayOutputStream();
            ByteBuffer packet=ByteBuffer.allocateDirect(262144);int packets=0;
            while(true){packet.clear();int size=extractor.readSampleData(packet,0);if(size<0)break;
                if(size>packet.capacity() || compressed.size()+size>4194304)throw new IOException("Compressed diagnostic exceeds bounds");
                byte[] bytes=new byte[size];packet.position(0);packet.get(bytes);compressed.write(bytes);packets++;extractor.advance();}
            byte[] bytes=compressed.toByteArray();ByteBuffer data=ByteBuffer.allocateDirect(bytes.length);data.put(bytes).flip();
            track=new AudioTrack.Builder().setAudioAttributes(attributes).setAudioFormat(format)
                    .setTransferMode(AudioTrack.MODE_STREAM).setBufferSizeInBytes(65536).setOffloadedPlayback(true).build();
            result.put("track_state",track.getState());result.put("offloaded_playback",track.isOffloadedPlayback());
            if(!track.isOffloadedPlayback() || track.getState()!=AudioTrack.STATE_INITIALIZED)
                throw new IllegalStateException("Forced offloaded track was not initialized");
            track.registerStreamEventCallback(callbacks,callback);registered=true;
            track.setVolume(.2f);track.play();long start=SystemClock.elapsedRealtime();
            int written=0,zeroWrites=0;long maxFrames=0;JSONArray timestamps=new JSONArray();boolean announced=false;
            while(data.hasRemaining()){
                if(SystemClock.elapsedRealtime()-start>20000 || tornDown.get()>0)throw new IOException("Compressed stream stalled or was torn down");
                int count=track.write(data,data.remaining(),AudioTrack.WRITE_NON_BLOCKING);
                if(count<0)throw new IOException("Compressed AudioTrack write error "+count);
                written+=count;if(count==0){zeroWrites++;Thread.sleep(10);}
                if(count>0 && !announced){System.out.println("TAB_S3_OFFLOAD_READY "+mime);System.out.flush();announced=true;}
                maxFrames=Math.max(maxFrames,Integer.toUnsignedLong(track.getPlaybackHeadPosition()));
            }
            track.setOffloadEndOfStream();
            while(completed.getCount()>0 && SystemClock.elapsedRealtime()-start<25000){
                maxFrames=Math.max(maxFrames,Integer.toUnsignedLong(track.getPlaybackHeadPosition()));
                AudioTimestamp timestamp=new AudioTimestamp();
                if(track.getTimestamp(timestamp))timestamps.put(new JSONObject().put("frame_position",timestamp.framePosition).put("nano_time",timestamp.nanoTime));
                completed.await(50,TimeUnit.MILLISECONDS);
            }
            maxFrames=Math.max(maxFrames,Integer.toUnsignedLong(track.getPlaybackHeadPosition()));
            result.put("compressed_packets",packets);result.put("compressed_bytes",bytes.length);result.put("written_bytes",written);
            result.put("zero_write_polls",zeroWrites);result.put("presentation_ended_callbacks",ended.get());
            result.put("tear_down_callbacks",tornDown.get());result.put("data_request_callbacks",requests.get());
            result.put("playback_frames_max",maxFrames);result.put("timestamps",timestamps);
            result.put("routed_device",String.valueOf(track.getRoutedDevice()));
            result.put("playback_ms",SystemClock.elapsedRealtime()-start);
            result.put("passed",written==bytes.length && packets>0 && ended.get()==1 && tornDown.get()==0
                    && maxFrames>0 && maxFrames>=referenceFrames-4096);
            result.put("limits","Forced compressed AudioTrack; host must independently observe a live compressed DSP file descriptor. No PCM fallback. Physical audibility and long playback are separate checks.");
        }finally{
            if(track!=null){if(registered)try{track.unregisterStreamEventCallback(callback);}catch(Exception ignored){}track.release();}
            callbacks.shutdownNow();extractor.release();
        }
    }

    private static void audioRoute(JSONObject result,Intent intent) throws Exception {
        final int rate=48000, samples=rate*2;short[] tone=new short[samples];
        for(int i=0;i<samples;i++)tone[i]=(short)(Math.sin(i*2*Math.PI*440/rate)*4096);
        AudioTrack track=new AudioTrack.Builder().setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build()).setAudioFormat(new AudioFormat.Builder().setSampleRate(rate).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).setEncoding(AudioFormat.ENCODING_PCM_16BIT).build()).setBufferSizeInBytes(samples*2).setTransferMode(AudioTrack.MODE_STATIC).build();
        try {result.put("track_state",track.getState());int written=track.write(tone,0,samples);result.put("samples_written",written);track.setVolume(.3f);track.play();Thread.sleep(2300);result.put("playback_frames",track.getPlaybackHeadPosition());result.put("routed_device",String.valueOf(track.getRoutedDevice()));result.put("passed",written==samples && track.getPlaybackHeadPosition()>=samples);} finally {track.release();}
        result.put("limits","Playback position proves HAL accepted samples, not that a person heard the speakers. No microphone recording in this command.");
    }
}
