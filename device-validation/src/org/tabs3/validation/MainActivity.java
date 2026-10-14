package org.tabs3.validation;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.media.AudioManager;
import android.media.ToneGenerator;
import android.os.Build;
import android.os.Bundle;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.provider.MediaStore;
import android.view.MotionEvent;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.util.concurrent.atomic.AtomicBoolean;

public final class MainActivity extends Activity implements SensorEventListener {
    private TextView result, sensorText;
    private EditText endpoint;
    private SensorManager sensors;
    private int events;
    private long lastSensorUpdate;
    private final AtomicBoolean loop = new AtomicBoolean(false);
    private ToneGenerator tone;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        column.setPadding(24, 32, 24, 24);
        ScrollView scroll = new ScrollView(this); scroll.addView(column); setContentView(scroll);
        TextView title = new TextView(this);
        title.setText(getPackageName() + "\n" + Build.MODEL + " / " + Build.VERSION.RELEASE
                + " (SDK " + Build.VERSION.SDK_INT + ")\nKernel " + System.getProperty("os.version"));
        column.addView(title);
        endpoint = new EditText(this); endpoint.setSingleLine(true);
        endpoint.setText("http://127.0.0.1:8023/payload"); column.addView(endpoint);
        result = new TextView(this); result.setTextIsSelectable(true);
        button(column, "Run network + UID accounting probe", () -> probe());
        button(column, "Start/stop 5 second loop (press Home to test background)", () -> {
            if (loop.getAndSet(!loop.get())) return;
            final String url = endpoint.getText().toString();
            new Thread(() -> {
                while (loop.get()) {
                    String value = Probe.run(getApplicationContext(), url);
                    runOnUiThread(() -> result.setText(value));
                    try { Thread.sleep(5000); } catch (InterruptedException error) { break; }
                }
            }, "TabS3ProbeLoop").start();
        });
        button(column, "Play short speaker tone (media volume)", () -> {
            if (tone == null) tone = new ToneGenerator(AudioManager.STREAM_MUSIC, 35);
            tone.startTone(ToneGenerator.TONE_PROP_BEEP, 400);
        });
        button(column, "Vibrate 150 ms", () -> {
            Vibrator vibrator = getSystemService(Vibrator.class);
            if (vibrator != null && vibrator.hasVibrator())
                vibrator.vibrate(VibrationEffect.createOneShot(150, VibrationEffect.DEFAULT_AMPLITUDE));
            else result.setText("No vibrator reported");
        });
        button(column, "Open installed camera", () -> {
            try { startActivity(new Intent(MediaStore.ACTION_IMAGE_CAPTURE)); }
            catch (Exception error) { result.setText(error.toString()); }
        });
        column.addView(result);
        TextView instruction = new TextView(this);
        instruction.setText("Touch / S-Pen pad: draw with finger and pen; pressure and tool type update below.");
        column.addView(instruction);
        column.addView(new DrawPad(), new LinearLayout.LayoutParams(-1, 420));
        sensorText = new TextView(this); column.addView(sensorText);
        sensors = getSystemService(SensorManager.class);
        StringBuilder inventory = new StringBuilder("Sensors:\n");
        for (Sensor sensor : sensors.getSensorList(Sensor.TYPE_ALL))
            inventory.append(sensor.getName()).append(" type=").append(sensor.getType()).append('\n');
        TextView listed = new TextView(this); listed.setText(inventory.toString()); column.addView(listed);
    }
    private void button(LinearLayout column, String label, Runnable action) {
        Button button = new Button(this); button.setText(label);
        button.setOnClickListener(view -> action.run()); column.addView(button);
    }
    private void probe() {
        final String url = endpoint.getText().toString();
        new Thread(() -> {
            String value = Probe.run(getApplicationContext(), url);
            runOnUiThread(() -> result.setText(value));
        }, "TabS3Probe").start();
    }
    @Override public void onResume() {
        super.onResume();
        for (int type : new int[] {Sensor.TYPE_ACCELEROMETER, Sensor.TYPE_GYROSCOPE,
                Sensor.TYPE_LIGHT, Sensor.TYPE_MAGNETIC_FIELD}) {
            Sensor sensor = sensors.getDefaultSensor(type);
            if (sensor != null) sensors.registerListener(this, sensor, SensorManager.SENSOR_DELAY_NORMAL);
        }
    }
    @Override public void onPause() { sensors.unregisterListener(this); super.onPause(); }
    @Override public void onDestroy() {
        loop.set(false); if (tone != null) tone.release(); super.onDestroy();
    }
    @Override public void onAccuracyChanged(Sensor sensor, int accuracy) {}
    @Override public void onSensorChanged(SensorEvent event) {
        events++;
        long now = android.os.SystemClock.elapsedRealtime();
        if (now - lastSensorUpdate > 500) {
            lastSensorUpdate = now;
            sensorText.setText("Sensor events=" + events + " latest=" + event.sensor.getName()
                    + " first value=" + event.values[0]);
        }
    }
    private final class DrawPad extends View {
        final Paint paint = new Paint(); final Path path = new Path();
        String detail = "No touch yet";
        DrawPad() { super(MainActivity.this); setBackgroundColor(Color.rgb(245, 245, 245)); }
        @Override protected void onDraw(Canvas canvas) {
            paint.setColor(Color.BLUE); paint.setStyle(Paint.Style.STROKE); paint.setStrokeWidth(3);
            canvas.drawPath(path, paint);
            paint.setColor(Color.BLACK); paint.setStyle(Paint.Style.FILL); paint.setTextSize(20);
            canvas.drawText(detail, 10, 30, paint);
        }
        @Override public boolean onTouchEvent(MotionEvent event) {
            getParent().requestDisallowInterceptTouchEvent(true);
            int index = event.getActionIndex();
            if (event.getActionMasked() == MotionEvent.ACTION_DOWN) path.moveTo(event.getX(index), event.getY(index));
            else path.lineTo(event.getX(index), event.getY(index));
            detail = "tool=" + event.getToolType(index) + " pressure=" + event.getPressure(index)
                    + " pointers=" + event.getPointerCount();
            invalidate();
            if (event.getActionMasked() == MotionEvent.ACTION_UP) performClick();
            return true;
        }
        @Override public boolean performClick() { super.performClick(); return true; }
    }
}
