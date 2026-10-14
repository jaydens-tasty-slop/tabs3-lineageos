package org.tabs3.validation;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public final class ProbeReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        PendingResult pending = goAsync();
        String url = intent.getStringExtra("url");
        if (url == null) url = "http://127.0.0.1:8023/payload";
        final String endpoint = url;
        new Thread(() -> {
            try { Probe.run(context.getApplicationContext(), endpoint); }
            finally { pending.finish(); }
        }, "TabS3Probe").start();
    }
}
