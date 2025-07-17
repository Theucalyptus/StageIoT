package com.example.iotapp;

import static java.lang.System.exit;

import android.Manifest;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.content.pm.PackageManager;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.provider.ContactsContract;
import android.provider.Settings;
import android.util.Log;
import android.view.View;
import android.view.autofill.AutofillValue;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.EdgeToEdge;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;

import java.io.BufferedWriter;
import java.io.IOException;
import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.net.Socket;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;
import okhttp3.Response;
import okio.ByteString;
import android.annotation.SuppressLint;

import com.google.android.gms.location.FusedLocationProviderClient;
import com.google.android.gms.location.LocationServices;
import com.google.android.gms.location.Priority;
import com.google.android.gms.tasks.OnSuccessListener;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import com.google.android.gms.location.LocationRequest;
import com.google.android.gms.location.LocationCallback;
import com.google.android.gms.location.LocationResult;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedList;
import java.util.List;
import java.util.concurrent.locks.Condition;
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantLock;

public class MainActivity extends AppCompatActivity {

    Button btnConnectWifi;
    TextView tSocket;
    TextView sData;

    TextView txtStat;

    private boolean sockPossible= false;


    TextView dataView;

    TextView txtPos;

    EditText fieldIP;
    EditText fieldPort;

    Button confirm;

    private boolean isSocketConnected = false;

    private String SERVER_IP = "10.42.0.1";
    private int SERVER_PORT = 6789;

    private String SERVER_IP_def = "10.42.0.1";
    private int SERVER_PORT_def = 6789;

    private WebSocket webSocket;
    private OkHttpClient client;

    private FusedLocationProviderClient fusedLocationClient;
    private LocationCallback locationCallback;

    private SensorManager sensorManager;
    private float[] gravity = new float[3];
    private float[] geomagnetic = new float[3];
    private float lastPitch = 0f;
    private float lastRoll = 0f;
    private float lastOrientation=0f;

    Thread thPos;

    private double lastLat=0.0;
    private double lastLon=0.0;
    private double lastAlt=0.0;
    private float lastSpd= 0.0F;

    private SenderThread sender;


    private Lock lockData= new ReentrantLock();

    List<String> dataList= new LinkedList<>();

    JSONObject stat;

    private String disp_stat="";

    private String disp;



    private Lock lock = new ReentrantLock();
    private Condition dataUpdate = lock.newCondition();

    /*
        *Display the objects seen by other device.
    */

    private void displayNbor() throws JSONException {
        
        lockData.lock();
            //dataView.setText("");

            disp = "";
            for(String s: dataList) {
                List<JSONObject> obj = stringToJson(s);
                for (JSONObject o : obj) {

                    String emoji;
                    String label = null;
                    String seenby = null;
                    try {
                        label = o.has("label") ? o.getString("label") : "undefined";
                        seenby = o.has("seenby") ? o.getString("seenby") : "";
                    } catch (JSONException e) {
                        throw new RuntimeException(e);
                    }

                    switch (label) {
                        case "person":
                            emoji = "🧍";
                            break;
                        case "car":
                            emoji = "🚗";
                            break;
                        case "bicycle":
                            emoji = "🚲";
                            break;
                        case "bus":
                            emoji = "🚌";
                            break;
                        default:
                            emoji = "❓";
                            break;
                    }

                    double dist = 0;
                    String arrow = null;
                    String id = null;

                    try {
                        dist = haversine(lastLat, lastLon, (double) o.get("latitude"), (double) o.get("longitude"));
                        arrow = getArrowFromLocation(lastOrientation, lastLat, lastLon, (double) o.get("latitude"), (double) o.get("longitude"));
                        id = o.has("id") ? o.getString("id") : o.getString("device-id");
                        disp = disp + emoji + ": " + id + " | Seen by: " + seenby + " | Distance: " + String.format("%.2f", dist) + " | Dir : " + arrow + " \n";

                    } catch (JSONException e) {
                        throw new RuntimeException(e);
                    }

                }
            }

            runOnUiThread(()->{
                dataView.setText(disp);
            });

                //Log.d("AFFICHAGE", emoji);

            //}

        //}
        //String disp_stat="";
        double latence;
        double ratio_rx=0.0;
        double ratio_tx=0.0;


        if(stat!=null){
            Log.d("ICI", stat.toString());
            latence= stat.getDouble("networkLatency") * 100;
            double fMsgTx= stat.getDouble("failedMsgTX");
            double fMsgRx = stat.getDouble("failedMsgRX");
            double tMsgTx = stat.getDouble(("totalMsgTX"));
            double tMsgRx= stat.getDouble("totalMsgRX");

            ratio_rx = (tMsgRx==0.0) ? ratio_rx: 100 * (1-(fMsgRx/tMsgRx));
            ratio_tx = (tMsgTx==0.0) ? ratio_tx: 100 * (1-(fMsgTx/tMsgTx));

            disp_stat= "Net latency : "+ (int) latence + " ms | Succes Rx : " + String.format("%.2f",ratio_rx) + "% | Succes tx : " + String.format("%.2f",ratio_tx) + "%";
        }

        runOnUiThread(()->{
            txtStat.setText("Stat réseau :\n"+ disp_stat);
        });
        dataList.clear();
        lockData.unlock();

    }



    /*
        *Convert a jsonString to a List of JSONObject to be displayed.
    */
    private List<JSONObject> stringToJson(String jsonString) {
        List<JSONObject> ob= new LinkedList<>();
        List<JSONArray> lobj;
        try{
            JSONArray ar= new JSONArray(jsonString);
            JSONObject obj= ar.getJSONObject(0);
            stat= ar.getJSONObject(2);

            Log.d("STAT", "STAT_REMPLI");


            Log.d("STAT", stat.toString());
            lobj = valObj(obj);
            ob= arrayJsontoObj(lobj);

            JSONObject objet= ar.getJSONObject(1);
            Iterator<String> keys= objet.keys();
            while(keys.hasNext()){
                String key= keys.next();
                ob.add((JSONObject) objet.get(key));
            }

        } catch (JSONException e) {
            Log.e("PARSERJSON", e.getMessage());
        }

        Log.d("cast",ob.toString());
        return ob;
    }

    /*
        *Extract a List of values (JSONArray) from a JSONObject.
    */
    private List<JSONArray> valObj(JSONObject obj) throws JSONException {
        List<JSONArray> res= new LinkedList<>();
        Iterator<String> keys = obj.keys();
        while(keys.hasNext()){
            String key= keys.next();
            res.add((JSONArray) obj.get(key));
        }
        return res;
    }

    /*
        *Convert a list of JSONArray to a List of JSONObject.
     */
    private List<JSONObject> arrayJsontoObj(List<JSONArray> aobj) throws JSONException {
        List<JSONObject> res= new LinkedList<>();
        for(JSONArray a: aobj){
            for (int i = 0; i < a.length(); i++) {
                JSONObject obj = a.getJSONObject(i);
                res.add(obj);
            }
        }

        return res;
    }

    /*
     * Listener to collect the pitch and roll data of the phone, useful for the pitch and roll of the vehicule
     */
    private final SensorEventListener sensorListener = new SensorEventListener() {
        private long last = System.currentTimeMillis();

        @Override
        public void onSensorChanged(SensorEvent event) {
            if (event.sensor.getType() == Sensor.TYPE_ACCELEROMETER) {
                gravity = event.values.clone();
            } else if (event.sensor.getType() == Sensor.TYPE_MAGNETIC_FIELD) {
                geomagnetic = event.values.clone();
            }

            float R[] = new float[9];
            float I[] = new float[9];

            if (SensorManager.getRotationMatrix(R, I, gravity, geomagnetic)) {
                float[] orientation = new float[3];
                SensorManager.getOrientation(R, orientation);
                lastOrientation= (float) Math.toDegrees(orientation[0]);
                lastPitch = (float) Math.toDegrees(orientation[1]); // avant/arrière
                lastRoll = (float) Math.toDegrees(orientation[2]);  // gauche/droite
                long now = System.currentTimeMillis();
                if ((now - last) > 50) {
                    last = now;

                    lock.lock();
                    dataUpdate.signal();
                    lock.unlock();
                }

            }
        }

        @Override
        public void onAccuracyChanged(Sensor sensor, int accuracy) {
        }
    };

    @Override
    protected void onStart() {
        super.onStart();
    }

    @Override
    protected void onStop() {
        super.onStop();
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        EdgeToEdge.enable(this);
        setContentView(R.layout.activity_main);


        sensorManager = (SensorManager) getSystemService(Context.SENSOR_SERVICE);
        Sensor accelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER);
        Sensor magnetometer = sensorManager.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD);
        sensorManager.registerListener(sensorListener, accelerometer, SensorManager.SENSOR_DELAY_UI);
        sensorManager.registerListener(sensorListener, magnetometer, SensorManager.SENSOR_DELAY_UI);


        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.main), (v, insets) -> {
            Insets systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars());
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom);
            return insets;
        });


        fusedLocationClient = LocationServices.getFusedLocationProviderClient(this);

        fieldIP = findViewById(R.id.ip_adress);
        fieldPort = findViewById(R.id.port);

        fieldIP.setText("10.42.0.1");
        fieldPort.setText("6789");
        btnConnectWifi = findViewById(R.id.wifi);
        confirm = findViewById(R.id.confIP);

        confirm.setOnClickListener(v->{
            if(webSocket != null) webSocket.close(1000,null);
            String ip_temp= fieldIP.getText().toString().trim();
            SERVER_IP = ip_temp.equals("")? SERVER_IP_def : ip_temp;
            String port_temp= fieldPort.getText().toString().trim();
            SERVER_PORT = ip_temp.equals("")? SERVER_PORT_def : Integer.parseInt(port_temp);

            sockPossible=true;
            Log.d("IP", SERVER_IP);

            connectWebSocket();
        });
        tSocket= findViewById(R.id.socketConnected);
        tSocket.setText(R.string.no_co_sock);
        sData= findViewById(R.id.sendData);
        txtPos= findViewById(R.id.txtPos);
        txtStat= findViewById(R.id.txtStat);


        updatePos();

        dataView= findViewById(R.id.data_text_view);
        dataView.setText("");

        sender = new SenderThread();
        sender.start();

    }


    /*
     *Check if yhe phone is connected to the access point
     */
    private boolean checkWifiConnection() {
        ConnectivityManager connManager = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        NetworkInfo wifiInfo = connManager.getNetworkInfo(ConnectivityManager.TYPE_WIFI);

        boolean isConnected = wifiInfo != null && wifiInfo.isConnected();

        if (isConnected) {
            btnConnectWifi.setEnabled(false);
            Toast.makeText(this, "Connecté au Wi-Fi", Toast.LENGTH_SHORT).show();
            return true;

        } else {
            btnConnectWifi.setEnabled(true);
            sData.setText("");
            tSocket.setText(R.string.no_co_sock);
            Toast.makeText(this, "Non connecté au Wi-Fi", Toast.LENGTH_SHORT).show();

            btnConnectWifi.setOnClickListener(v -> {
                Intent intent = new Intent(Settings.ACTION_WIFI_SETTINGS);
                startActivity(intent);
            });

            return false;
        }
    }


    /*
     * Connect to the platform using websocket API, useful for sending all the collected data
     */
    private void connectWebSocket() {

        Context c= this;
        if (isSocketConnected) return;

        client = new OkHttpClient();

        Request request = new Request.Builder()
                .url("ws://" + SERVER_IP + ":" + SERVER_PORT)
                .build();

        webSocket = client.newWebSocket(request, new WebSocketListener() {
            @Override
            public void onOpen(@NonNull WebSocket webSocket, @NonNull Response response) {
                Log.d("WEBSOCKET", "Connecté !");
                isSocketConnected = true;
                runOnUiThread(()->{
                    tSocket.setText(R.string.co_sock);
                });

            }

            @Override
            public void onMessage(@NonNull WebSocket webSocket, @NonNull String text) {
                Log.d("WEBSOCKET", "Message reçu : " + text);
                lockData.lock();

                if (!(text.equals("null"))) {
                    dataList.add(text);
                }

                lockData.unlock();
                Log.d("DATALIST", dataList.toString());

                try {
                    displayNbor();

                } catch (JSONException e) {
                    Log.e("ERREUR_AFFICHAGE", e.getMessage());
                }
            }

            @Override
            public void onFailure(@NonNull WebSocket webSocket, @NonNull Throwable t, Response response) {
                Log.e("WEBSOCKET", "Erreur : " + t.getMessage());
                isSocketConnected = false;
                sockPossible=false;
                runOnUiThread(()->{
                    tSocket.setText(R.string.no_co_sock);
                    sData.setText("");
                });
                //exit(1);
                new Handler(Looper.getMainLooper()).post(() -> {
                    Toast.makeText(c, "WebSocket failure" , Toast.LENGTH_SHORT).show();
                });
                //Toast.makeText(c, "Websocket failure", Toast.LENGTH_SHORT).show();

            }

            @Override
            public void onClosing(@NonNull WebSocket webSocket, int code, @NonNull String reason) {
                webSocket.close(1000, null);
                runOnUiThread(()->{
                    tSocket.setText(R.string.no_co_sock);
                    sData.setText("");
                });
                isSocketConnected = false;
                sockPossible=false;
                Log.d("WEBSOCKETCLOSE", "Fermeture : " + reason);
            }
        });
    }

    private void updatePos(){
        thPos= new Thread(()->{
            try {
                while (true){
                    runOnUiThread(()->{
                        txtPos.setText("Lat : " + lastLat + " Lon : " +  lastLon + " Az : " + String.format("%.2f", lastOrientation));
                    });

                    Thread.sleep(3000);
                }
            } catch (Exception e) {
                Log.e("AFFICHAGE_POS", e.getMessage());
            }
        });

        thPos.start();
    }

    class SenderThread extends Thread {
        private boolean exit = false;
        SenderThread() {
        }

        public void run() {
            while (!this.exit) {
                lock.lock();
                try {
                    dataUpdate.await();
                    if (isSocketConnected && webSocket != null) {
                        try {

                            ZonedDateTime nowUtc = null;
                            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                                nowUtc = ZonedDateTime.now(ZoneOffset.UTC);
                            }
                            String isoTimestamp = null;
                            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                                isoTimestamp = nowUtc.format(DateTimeFormatter.ISO_OFFSET_DATE_TIME);
                            }

                            JSONObject json = new JSONObject();
                            json.put("timestamp", isoTimestamp);
                            json.put("latitude", lastLat);
                            json.put("longitude", lastLon);
                            json.put("altitude", lastAlt);
                            json.put("speed", lastSpd);
                            json.put("pitch", lastPitch);
                            json.put("roll", lastRoll);
                            json.put("azimuth", lastOrientation);


                            String message = json.toString();
                            //Log.d("WEBSOCKET", String.valueOf(webSocket.queueSize()));
                            boolean res = webSocket.send(message);

                            if (!res) {
                                Log.d("WEBSOCKET", "input buffer overflow, closing the connection !!");
                            }
                            runOnUiThread(()->{
                                sData.setText(R.string.sendD);
                            });

                            //displayNbor();

                            Log.d("WEBSOCKET", "JSON envoyé : " + message);
                        } catch (Exception e) {
                            Log.e("WEBSOCKET", "Erreur JSON : " + e.getMessage());
                        }

                    }
                } catch (InterruptedException e) {
                    Log.d("SENDPOSITION", " "+ e.getMessage());
                }
                lock.unlock();
            }
        }

        public void exit() {
            this.exit = true;
        }
    }

    /*
     * Update the location of the user, each second
     */
    private void startLocationUpdates() {
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.ACCESS_FINE_LOCATION}, 1);
            Log.i("GPS", "missing permissions");
            return;
        }

        Log.d("GPS", "launching");
        LocationRequest locationRequest = new LocationRequest.Builder(
                Priority.PRIORITY_HIGH_ACCURACY,
                1000L // Demande toutes les 5s
        ).setMaxUpdateDelayMillis(1000L).setMinUpdateDistanceMeters(0.0f).build();

        locationCallback = new LocationCallback() {
            @Override
            public void onLocationResult(@NonNull LocationResult locationResult) {
                //Log.d("GPS", "update callback");
                for (Location location : locationResult.getLocations()) {
                    lastLat = location.getLatitude();
                    lastLon = location.getLongitude();
                    lastSpd = location.getSpeed(); // m/s
                    lastAlt = location.getAltitude();
                    //Log.d("GPS UPDATE", lastLat + " | " + lastLon);
                    lock.lock();
                    dataUpdate.signal();
                    lock.unlock();
                }
            }
        };

        fusedLocationClient.requestLocationUpdates(locationRequest, locationCallback, Looper.getMainLooper());
    }

    /*
     * Free all the allocated ressources
     */
    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (locationCallback != null) {
            fusedLocationClient.removeLocationUpdates(locationCallback);
        }

        if(thPos!=null) thPos.interrupt();

    }

    /*
     * Check if the phone is still connected to the access point
     */
    @Override
    protected void onResume() {
        super.onResume();
        Log.d("main", "onResume called");
        startLocationUpdates();

        if(checkWifiConnection() && sockPossible) {

            connectWebSocket();
        }
    }

    private double haversine(double lat1, double lon1,
                            double lat2, double lon2)
    {

        double dLat = Math.toRadians(lat2 - lat1);
        double dLon = Math.toRadians(lon2 - lon1);


        lat1 = Math.toRadians(lat1);
        lat2 = Math.toRadians(lat2);


        double a = Math.pow(Math.sin(dLat / 2), 2) +
                Math.pow(Math.sin(dLon / 2), 2) *
                        Math.cos(lat1) *
                        Math.cos(lat2);
        double rad = 6371000;
        double c = 2 * Math.asin(Math.sqrt(a));
        return rad * c;
    }

    public static String getArrowFromLocation(double azimuth, double lat1, double lon1, double lat2, double lon2) {
        try {
            lat1 = Math.toRadians(lat1);
            lat2 = Math.toRadians(lat2);
            lon1 = Math.toRadians(lon1);
            lon2 = Math.toRadians(lon2);
            azimuth = Math.toRadians(azimuth);

            double tan = (lat2 - lat1) / (lon2 - lon1);
            double angle = Math.atan(tan);
            angle = lon2 < lon1 ? angle + Math.PI : angle;
            double relaAng = (Math.PI / 2 - azimuth) - angle;
            relaAng = relaAng < 0 ? relaAng + 2 * Math.PI : relaAng;

            double frac = 4 * relaAng / Math.PI;
            int d = (int) Math.round(frac);

            System.out.println("d " + azimuth + " " + angle + " " + relaAng + " " + d);

            switch (d % 8) {
                case 0: return "⬆️";
                case 1: return "↗️";
                case 2: return "➡️";
                case 3: return "↘️";
                case 4: return "⬇️";
                case 5: return "↙️";
                case 6: return "⬅️";
                case 7: return "↖️";
                default: return ""+angle;
            }
        } catch (Exception e) {
            return "exeption";
        }
    }

}