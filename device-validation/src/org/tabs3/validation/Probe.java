package org.tabs3.validation;

import android.Manifest;
import android.content.Context;
import android.content.pm.PackageManager;
import android.net.TrafficStats;
import android.os.Process;
import android.os.SystemClock;
import android.util.Log;
import org.json.JSONObject;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.ByteArrayOutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URI;
import java.nio.charset.StandardCharsets;

public final class Probe {
    private Probe() {}
    public static String run(Context context, String endpoint) {
        JSONObject result = new JSONObject();
        int uid = Process.myUid();
        boolean internet = context.checkSelfPermission(Manifest.permission.INTERNET)
                == PackageManager.PERMISSION_GRANTED;
        long rx = TrafficStats.getUidRxBytes(uid), tx = TrafficStats.getUidTxBytes(uid);
        long start = SystemClock.elapsedRealtime();
        Socket socket = null;
        boolean success = false;
        boolean permissionDenied = false;
        int bytes = 0;
        int bodyBytes = 0;
        try {
            result.put("package", context.getPackageName());
            result.put("uid", uid);
            result.put("internet_permission", internet);
            result.put("endpoint", endpoint);
            URI uri = new URI(endpoint);
            if (!"http".equals(uri.getScheme()) || uri.getHost() == null
                    || uri.getUserInfo() != null || uri.getFragment() != null)
                throw new IllegalArgumentException("Use an http://IP:port/payload URL");
            int port = uri.getPort() < 0 ? 80 : uri.getPort();
            String path = uri.getRawPath();
            if (path == null || path.isEmpty()) path = "/payload";
            path += (uri.getRawQuery() == null ? "?" : "?" + uri.getRawQuery() + "&")
                    + "uid=" + uid + "&package=" + context.getPackageName()
                    + "&probe=" + start;
            TrafficStats.setThreadStatsTag(0x5320);
            socket = new Socket();
            TrafficStats.tagSocket(socket);
            socket.connect(new InetSocketAddress(uri.getHost(), port), 4000);
            socket.setSoTimeout(4000);
            OutputStream output = socket.getOutputStream();
            String request = "GET " + path + " HTTP/1.0\r\nHost: " + uri.getHost()
                    + "\r\nConnection: close\r\n\r\n";
            output.write(request.getBytes(StandardCharsets.US_ASCII));
            output.flush();
            InputStream input = socket.getInputStream();
            byte[] buffer = new byte[8192];
            ByteArrayOutputStream response = new ByteArrayOutputStream();
            for (int count; (count = input.read(buffer)) != -1;) {
                response.write(buffer, 0, count);
                bytes += count;
                if (bytes > 2 * 1024 * 1024) throw new IllegalStateException("Unexpected oversized payload");
            }
            byte[] data = response.toByteArray();
            int headerEnd = -1;
            for (int i = 0; i + 3 < Math.min(data.length, 8192); i++)
                if (data[i] == '\r' && data[i+1] == '\n' && data[i+2] == '\r' && data[i+3] == '\n') {
                    headerEnd = i + 4; break;
                }
            String status = new String(data, 0, Math.min(data.length, 80), StandardCharsets.US_ASCII);
            bodyBytes = headerEnd < 0 ? 0 : data.length - headerEnd;
            if (!(status.startsWith("HTTP/1.0 200") || status.startsWith("HTTP/1.1 200"))
                    || bodyBytes != 256 * 1024) throw new IllegalStateException("Incomplete HTTP payload: " + status);
            success = true;
        } catch (Exception error) {
            String detail = error.toString();
            for (Throwable cause = error.getCause(); cause != null; cause = cause.getCause())
                detail += " <- " + cause.toString();
            permissionDenied = error instanceof SecurityException || detail.contains("EACCES")
                    || detail.contains("EPERM") || detail.toLowerCase(java.util.Locale.ROOT).contains("permission denied")
                    || detail.toLowerCase(java.util.Locale.ROOT).contains("operation not permitted");
            try { result.put("error", detail); } catch (Exception ignored) {}
        } finally {
            if (socket != null) {
                try { TrafficStats.untagSocket(socket); } catch (Exception ignored) {}
                try { socket.close(); } catch (Exception ignored) {}
            }
            TrafficStats.clearThreadStatsTag();
        }
        try {
            // Android 16 defaults to a 1000 ms client TrafficStats cache. Let it expire.
            SystemClock.sleep(1500);
            long afterRx = TrafficStats.getUidRxBytes(uid), afterTx = TrafficStats.getUidTxBytes(uid);
            result.put("http_success", success);
            result.put("bytes_received_including_headers", bytes);
            result.put("body_bytes", bodyBytes);
            result.put("traffic_stats_cache_wait_ms", 1500);
            result.put("elapsed_ms", SystemClock.elapsedRealtime() - start);
            result.put("uid_rx_before", rx); result.put("uid_rx_after", afterRx);
            result.put("uid_tx_before", tx); result.put("uid_tx_after", afterTx);
            result.put("traffic_stats_available", rx >= 0 && tx >= 0 && afterRx >= 0 && afterTx >= 0);
            result.put("rx_delta", rx >= 0 && afterRx >= 0 ? afterRx - rx : -1);
            result.put("tx_delta", tx >= 0 && afterTx >= 0 ? afterTx - tx : -1);
            result.put("permission_denied", permissionDenied);
            result.put("ordinary_permission_expectation_met", internet ? success : !success && permissionDenied);
        } catch (Exception ignored) {}
        String encoded = result.toString();
        Log.i("TabS3Probe", encoded);
        return encoded;
    }
}
